"""
atualizar_respondio.py
======================
Busca dados do Respond.io via API v2 e atualiza o index.html.

Metricas coletadas:
  - Conversas por dia (30d / 90d / historico)
  - Origem / canal das conversas
  - Funil de ciclo de vida dos contatos (New Lead > Hot Lead > Payment > Customer)
  - Status (aberta / fechada / reaberta)
  - Agentes: total de conversas por atendente
  - Tags: distribuicao de etiquetas

Como gerar o token:
  1. Acesse app.respond.io >> Settings >> Developer API
  2. Clique em "Generate API Key"
  3. Copie o token JWT e cole em ACCESS_TOKEN abaixo

Execute: python atualizar_respondio.py
"""

import requests
import json
import re
import sys
from datetime import datetime, timedelta
from collections import defaultdict

# ─── CONFIGURACAO ─────────────────────────────────────────────────────────────
ACCESS_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6Mjg0NDMsInNwYWNlSWQiOjI5ODE4OCwib3JnSWQiOjI5NDM3NiwidHlwZSI6ImFwaSIsImlhdCI6MTc3OTQ3MTc0NX0.kVCK6O588AHIdCPTESLEBFxWvX0LQrcGB2Yj6uzmqB0"
ARQUIVO_DASH   = "index.html"
BASE_URL       = "https://api.respond.io/v2"
BASE_APP_URL   = "https://app.respond.io/api/v2"   # API interna do app
SPACE_ID       = "298188"                           # extraido do JWT
# ──────────────────────────────────────────────────────────────────────────────

# Mapeamento: tipo de canal >> origem de trafego
MAPA_ORIGEM = {
    "instagram":           "Meta (Instagram)",
    "instagram_dm":        "Meta (Instagram)",
    "facebook":            "Meta (Facebook)",
    "facebook_feed":       "Meta (Facebook)",
    "facebook_messenger":  "Meta (Messenger)",
    "messenger":           "Meta (Messenger)",
    "whatsapp":            "WhatsApp",
    "whatsapp_cloud":      "WhatsApp",
    "whatsapp_business":   "WhatsApp",
    "whatsapp_cloud_api":  "WhatsApp",
    "google_business":     "Google (GBM)",
    "google_rcs":          "Google (RCS)",
    "widget":              "Site (Widget)",
    "web_widget":          "Site (Widget)",
    "livechat":            "Site (LiveChat)",
    "webchat":             "Site (Widget)",
    "sms":                 "SMS",
    "telegram":            "Telegram",
    "email":               "Email",
    "line":                "Line",
    "viber":               "Viber",
    "twitter":             "Twitter/X",
    "twitter_dm":          "Twitter/X",
    "wechat":              "WeChat",
}

ESTAGIOS_FUNIL = ["New Lead", "Hot Lead", "Payment", "Customer"]
ESTAGIO_PERDIDO = "Cold Lead"


def log(msg):
    print(msg, flush=True)


def headers():
    return {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def testar_conexao():
    log("Testando conexao com Respond.io...")
    try:
        r = requests.get(f"{BASE_URL}/contact/list", headers=headers(), timeout=15)
        if r.status_code in (200, 400):
            log("  Token valido (public API responde)")
            return True
        elif r.status_code == 401:
            log("  ERRO 401: Token invalido ou expirado.")
            log("  Solucao: Regenere o token em Settings >> Developer API")
            return False
        elif r.status_code == 403:
            log("  ERRO 403: Sem permissao. Verifique plano (Growth Plan+)")
            return False
        elif r.status_code == 404:
            log("  AVISO: Public API retornou 404.")
            log("  Verifique token e plano em Settings >> Developer API")
            return False
        else:
            log(f"  ERRO {r.status_code}: {r.text[:100]}")
            return False
    except Exception as e:
        log(f"  ERRO de conexao: {e}")
        return False


def post_paginado(endpoint, body_base, campo_dados, max_pags=100):
    """Faz POST com paginacao por pageToken/cursor."""
    todos = []
    body  = {**body_base, "pageSize": 100}
    pag   = 0

    while pag < max_pags:
        r = requests.post(f"{BASE_URL}/{endpoint}", headers=headers(), json=body, timeout=30)
        if not r.ok:
            log(f"  [AVISO] POST {endpoint} => {r.status_code}: {r.text[:120]}")
            break
        dado = r.json()

        # Tenta varios nomes de campo para os itens
        itens = (dado.get(campo_dados)
                 or dado.get("data")
                 or dado.get("contacts")
                 or dado.get("conversations")
                 or dado.get("results")
                 or [])
        if not itens:
            break
        todos.extend(itens)

        # Cursor/token de proxima pagina
        meta   = dado.get("meta") or {}
        cursor = (meta.get("nextPageToken")
                  or meta.get("cursor")
                  or meta.get("nextCursor")
                  or dado.get("nextPageToken")
                  or dado.get("nextCursor")
                  or dado.get("cursor"))
        if not cursor or len(itens) < body["pageSize"]:
            break
        body["pageToken"] = cursor
        pag += 1

    return todos


def get_paginado(endpoint, params_base, campo_dados, max_pags=100):
    """Faz GET com paginacao por cursor/offset."""
    todos  = []
    params = {**params_base, "limit": 100}
    pag    = 0

    while pag < max_pags:
        r = requests.get(f"{BASE_URL}/{endpoint}", headers=headers(), params=params, timeout=30)
        if not r.ok:
            log(f"  [AVISO] GET {endpoint} => {r.status_code}: {r.text[:120]}")
            break
        dado = r.json()

        itens = (dado.get(campo_dados)
                 or dado.get("data")
                 or dado.get("contacts")
                 or dado.get("conversations")
                 or dado.get("results")
                 or [])
        if not itens:
            break
        todos.extend(itens)

        meta   = dado.get("meta") or {}
        cursor = (meta.get("nextPageToken")
                  or meta.get("cursor")
                  or dado.get("nextCursor")
                  or dado.get("cursor"))
        if not cursor or len(itens) < params["limit"]:
            break
        params["cursor"] = cursor
        pag += 1

    return todos


def _get(path, params=None, base=None):
    """GET helper. Retorna None se 404/erro."""
    b = base or BASE_URL
    try:
        r = requests.get(f"{b}/{path}", headers=headers(), params=params or {}, timeout=20)
        if r.ok:
            ct = r.headers.get("content-type","")
            if "json" in ct:
                return r.json()
        return None
    except Exception:
        return None


def _post(path, body, base=None):
    """POST helper. Retorna None se erro/nao-json."""
    b = base or BASE_URL
    try:
        r = requests.post(f"{b}/{path}", headers=headers(), json=body, timeout=20)
        if r.ok:
            ct = r.headers.get("content-type","")
            if "json" in ct:
                return r.json()
        return None
    except Exception:
        return None


def buscar_canais():
    log("Buscando canais...")
    mapa = {}
    for ep in ["channels", "channel"]:
        dado = _get(ep)
        if dado:
            canais = dado.get("channels") or dado.get("data") or []
            for c in canais:
                cid  = str(c.get("id") or c.get("channelId") or "")
                tipo = (c.get("type") or c.get("channelType") or "").lower()
                nome = c.get("name") or c.get("channelName") or tipo
                if cid:
                    mapa[cid] = {
                        "tipo":   tipo,
                        "nome":   nome,
                        "origem": MAPA_ORIGEM.get(tipo, f"Outro ({tipo})" if tipo else "Desconhecido"),
                    }
            log(f"  {len(mapa)} canais via /{ep}")
            break
    if not mapa:
        log("  0 canais (endpoint nao disponivel neste plano)")
    return mapa


def buscar_conversas(dias=365):
    log(f"Buscando conversas (ultimos {dias} dias)...")
    hoje   = datetime.now()
    inicio = (hoje - timedelta(days=dias)).strftime("%Y-%m-%dT00:00:00Z")

    # Tenta todas as combinacoes conhecidas de endpoint
    tentativas = [
        # (metodo, base, path, params_ou_body)
        ("get",  BASE_URL,     "conversations",  {"createdAt[gte]": inicio, "limit": 100}),
        ("get",  BASE_URL,     "conversation",   {"createdAt[gte]": inicio, "limit": 100}),
        ("post", BASE_APP_URL, f"{SPACE_ID}/conversation/list",
            {"filter": {"search": ""}, "pageSize": 100, "sortBy": "createdAt", "sortOrder": "desc"}),
        ("post", BASE_APP_URL, "conversation/list",
            {"filter": {"search": ""}, "pageSize": 100}),
    ]
    for met, base, path, payload in tentativas:
        if met == "get":
            dado = _get(path, params=payload, base=base)
        else:
            dado = _post(path, body=payload, base=base)
        if dado:
            conv = dado.get("conversations") or dado.get("data") or dado.get("results") or []
            if conv:
                log(f"  {len(conv)} conversas via {met.upper()} /{path}")
                return conv

    log("  0 conversas (endpoints de lista nao disponiveis -- verifique plano Growth+)")
    return []


def buscar_contatos():
    log("Buscando contatos (ciclo de vida)...")

    tentativas = [
        ("get",  BASE_URL,     "contacts",       {"limit": 100}),
        ("get",  BASE_URL,     "contact",        {"limit": 100}),
        ("post", BASE_APP_URL, f"{SPACE_ID}/contact/list",
            {"filter": {"search": ""}, "pageSize": 100}),
        ("post", BASE_URL,     "contact/list",   {"filter": {"search": ""}, "pageSize": 100}),
    ]
    for met, base, path, payload in tentativas:
        if met == "get":
            dado = _get(path, params=payload, base=base)
        else:
            dado = _post(path, body=payload, base=base)
        if dado:
            conts = dado.get("contacts") or dado.get("data") or dado.get("results") or []
            if conts:
                log(f"  {len(conts)} contatos via {met.upper()} /{path}")
                return conts

    log("  0 contatos (endpoints de lista nao disponiveis -- verifique plano Growth+)")
    return []


def buscar_agentes():
    log("Buscando agentes/usuarios...")
    for ep in ["users", "user", "agents", "members"]:
        dado = _get(ep)
        if dado:
            users = dado.get("users") or dado.get("data") or dado.get("members") or []
            if users:
                log(f"  {len(users)} agentes via /{ep}")
                return users
    log("  0 agentes")
    return []


def buscar_tags():
    log("Buscando tags...")
    for ep in ["tags", "tag"]:
        dado = _get(ep)
        if dado:
            tags = dado.get("tags") or dado.get("data") or []
            if tags:
                log(f"  {len(tags)} tags")
                return tags
    log("  0 tags")
    return []


# ─── PROCESSAMENTO ────────────────────────────────────────────────────────────

def processar_ciclo_de_vida(contatos):
    contagem = defaultdict(int)
    for c in contatos:
        estagio = (c.get("lifecycle")
                   or c.get("lifecycleStage")
                   or c.get("lifecycle_stage")
                   or c.get("stage")
                   or "Sem Estagio")
        if isinstance(estagio, dict):
            estagio = estagio.get("name") or estagio.get("label") or "Sem Estagio"
        contagem[str(estagio)] += 1

    funil = []
    for nome in ESTAGIOS_FUNIL:
        funil.append({"estagio": nome, "total": contagem.get(nome, 0)})
    funil.append({"estagio": ESTAGIO_PERDIDO, "total": contagem.get(ESTAGIO_PERDIDO, 0), "perdido": True})

    outros = {k: v for k, v in contagem.items()
              if k not in ESTAGIOS_FUNIL and k != ESTAGIO_PERDIDO}
    for k, v in sorted(outros.items(), key=lambda x: -x[1]):
        funil.append({"estagio": k, "total": v, "outro": True})

    return funil, dict(contagem)


def processar_conversas(conversas, mapa_canais):
    por_dia    = defaultdict(int)
    por_origem = defaultdict(int)
    por_canal  = defaultdict(int)
    por_status = defaultdict(int)

    hoje = datetime.now()
    _30d = {(hoje - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(30)}
    _90d = {(hoje - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(90)}

    for conv in conversas:
        criado = (conv.get("createdAt") or conv.get("created_at")
                  or conv.get("startedAt") or "")
        data_str = criado[:10] if len(criado) >= 10 else ""
        if data_str:
            por_dia[data_str] += 1

        cid  = str(conv.get("channelId") or conv.get("channel_id") or "")
        cobj = conv.get("channel") or {}
        ctip = (cobj.get("type") or conv.get("channelType")
                or conv.get("channel_type") or "").lower()

        if cid and cid in mapa_canais:
            info   = mapa_canais[cid]
            origem = info["origem"]
            nchan  = info["nome"]
        elif ctip:
            origem = MAPA_ORIGEM.get(ctip, f"Outro ({ctip})")
            nchan  = ctip
        else:
            origem = "Desconhecido"
            nchan  = "Desconhecido"

        por_origem[origem] += 1
        por_canal[nchan]   += 1

        status = (conv.get("status") or conv.get("state") or "open").lower()
        por_status[status] += 1

    return {
        "totalConversas": len(conversas),
        "abertasHoje":    0,
        "porDia":   dict(sorted(por_dia.items())),
        "porDia30": {k: por_dia[k] for k in sorted(_30d) if k in por_dia},
        "porDia90": {k: por_dia[k] for k in sorted(_90d) if k in por_dia},
        "porOrigem": dict(sorted(por_origem.items(), key=lambda x: -x[1])),
        "porCanal":  dict(sorted(por_canal.items(),  key=lambda x: -x[1])),
        "porStatus": dict(por_status),
    }


def processar_agentes(agentes_raw, conversas):
    """Conta conversas por agente."""
    conv_por_agente = defaultdict(lambda: {"abertos": 0, "fechados": 0, "total": 0})
    for conv in conversas:
        aid = (str(conv.get("assigneeId") or conv.get("assignee_id") or
               (conv.get("assignee") or {}).get("id") or ""))
        if aid:
            status = (conv.get("status") or "open").lower()
            conv_por_agente[aid]["total"] += 1
            if status in ("open", "pending", "opened"):
                conv_por_agente[aid]["abertos"] += 1
            else:
                conv_por_agente[aid]["fechados"] += 1

    # Enriquece com nome do agente
    mapa_nome = {str(a.get("id") or ""): (a.get("name") or a.get("displayName")
                 or a.get("email") or "Agente")
                 for a in agentes_raw}

    resultado = []
    for aid, d in sorted(conv_por_agente.items(), key=lambda x: -x[1]["total"]):
        nome = mapa_nome.get(aid, f"Agente {aid[:6]}")
        resultado.append({"nome": nome, **d})
    return resultado


def processar_tags(tags_raw, conversas, contatos):
    """Conta uso de tags."""
    contagem = defaultdict(int)
    for obj in list(conversas) + list(contatos):
        for t in (obj.get("tags") or []):
            if isinstance(t, dict):
                nome = t.get("name") or t.get("label") or str(t.get("id", ""))
            else:
                nome = str(t)
            if nome:
                contagem[nome] += 1

    # Complementa com lista de tags da API
    for t in tags_raw:
        nome = t.get("name") or t.get("label") or ""
        if nome and nome not in contagem:
            contagem[nome] = 0

    return [{"nome": k, "total": v}
            for k, v in sorted(contagem.items(), key=lambda x: -x[1])]


# ─── ATUALIZAR HTML ────────────────────────────────────────────────────────────

def atualizar_html(dados):
    with open(ARQUIVO_DASH, encoding="utf-8") as f:
        html = f.read()

    novo_json = json.dumps(dados, ensure_ascii=False, indent=2)
    padrao    = r"(const DADOS_RESPONDIO\s*=\s*)(\{[\s\S]*?\})(\s*;)"
    novo_html, n = re.subn(padrao, lambda m: m.group(1) + novo_json + m.group(3), html)
    if n == 0:
        raise RuntimeError("DADOS_RESPONDIO nao encontrado no HTML.")

    with open(ARQUIVO_DASH, "w", encoding="utf-8") as f:
        f.write(novo_html)
    log(f"  DADOS_RESPONDIO atualizado ({len(novo_html):,} chars)")


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    log(f"\n=== Respond.io -- {datetime.now().strftime('%d/%m/%Y %H:%M')} ===\n")

    if not testar_conexao():
        log("\nSolucao de problemas:")
        log("  1. Acesse app.respond.io >> Settings >> Developer API")
        log("  2. Clique em 'Generate API Key' (ou regenere o existente)")
        log("  3. Cole o novo token em ACCESS_TOKEN neste arquivo")
        log("  4. Verifique se seu plano inclui API (Growth Plan ou superior)")
        sys.exit(1)

    log("")
    mapa_canais  = buscar_canais()
    conversas    = buscar_conversas(dias=365)
    contatos     = buscar_contatos()
    agentes_raw  = buscar_agentes()
    tags_raw     = buscar_tags()

    log("\nProcessando...")
    funil, contagem_estagios = processar_ciclo_de_vida(contatos)
    dados_conv               = processar_conversas(conversas, mapa_canais)
    dados_agentes            = processar_agentes(agentes_raw, conversas)
    dados_tags               = processar_tags(tags_raw, conversas, contatos)

    resultado = {
        "conversas":        dados_conv,
        "cicloDaVida":      funil,
        "contagemEstagios": contagem_estagios,
        "agentes":          dados_agentes,
        "tags":             dados_tags,
        "canais":           [{"nome": v["nome"], "tipo": v["tipo"], "origem": v["origem"]}
                             for v in mapa_canais.values()],
        "dataAtualizacao":  datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
    }

    # Resumo terminal
    log(f"\n  Conversas totais:  {dados_conv['totalConversas']:,}")
    log(f"  Contatos:          {len(contatos):,}")
    cv30 = sum(dados_conv.get("porDia30", {}).values())
    log(f"  Conversas (30d):   {cv30:,}")
    log(f"\n  Top origens:")
    for k, v in list(dados_conv["porOrigem"].items())[:5]:
        log(f"    {k:<30} {v:>5}")
    log(f"\n  Funil de ciclo de vida:")
    for e in funil:
        flag = " [PERDIDO]" if e.get("perdido") else ""
        log(f"    {e['estagio']:<22} {e['total']:>6}{flag}")

    log(f"\nAtualizando {ARQUIVO_DASH}...")
    atualizar_html(resultado)
    log("\nRespond.io atualizado com sucesso!")


if __name__ == "__main__":
    main()
