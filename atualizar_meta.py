"""
atualizar_meta.py
=================
Busca dados reais da Meta Ads API e atualiza o dashboard_completo.html.
Execute: python atualizar_meta.py

─── COMO OBTER O TOKEN ───────────────────────────────────────────────────────
1. Acesse https://business.facebook.com → Configuracoes → Usuarios do sistema
2. Crie um Usuario do Sistema Admin e gere um token com permissoes:
     ads_read, ads_management, business_management
3. Ou use o Graph API Explorer em https://developers.facebook.com/tools/explorer/
   e gere um User Token com ads_read.
4. Para token de longa duracao (nao expira em 1h):
   POST https://graph.facebook.com/oauth/access_token
     grant_type=fb_exchange_token
     client_id={APP_ID}
     client_secret={APP_SECRET}
     fb_exchange_token={TOKEN_CURTO}

─── COMO ENCONTRAR O AD ACCOUNT ID ──────────────────────────────────────────
  Meta Business Suite → Configuracoes → Contas de Anuncios → ID da Conta
  Formato: act_123456789012345
──────────────────────────────────────────────────────────────────────────────
"""

import requests
import json
import re
from datetime import datetime

# ─── CONFIGURACAO ─────────────────────────────────────────────────────────────
ACCESS_TOKEN  = "EAASW2NZCdwiwBRjZBpgb4Unpo2rqHB8iSJfZAt3BkkHB3pxrkevSo0UYx5RnF5hN7dnZCUV5yqwuPtfVUqhE3gAyOcfbLvYVhmMb5Cq1OAZBtJQ9cCRQAIce6wU7QNiX1iy11KH8tELm38U8HKTZCIgriWrUZBUdP4l60xZB4zxDgJVyZAC2bllLHsyDHnos83noLfm9SX14s0ZCmAP0iLTZBAw5OShUTb84yf4AgQCz201"
AD_ACCOUNT_ID = "act_2613909812239242"
ARQUIVO_DASH  = "dashboard_completo.html"
API_VERSION   = "v19.0"
BASE_URL      = f"https://graph.facebook.com/{API_VERSION}"

# Intervalo de datas — opcoes: last_7_days, last_14_days, last_30_days,
#   last_90_days, this_month, last_month, ou usar since/until abaixo
DATE_PRESET   = "last_30d"
# DATE_SINCE  = "2025-04-01"   # Descomente para intervalo customizado
# DATE_UNTIL  = "2025-04-30"
# ──────────────────────────────────────────────────────────────────────────────

NOMES_PAIS = {
    "BR":"Brasil","US":"EUA","AR":"Argentina","GB":"Reino Unido",
    "DE":"Alemanha","FR":"Franca","IT":"Italia","ES":"Espanha",
    "PT":"Portugal","UY":"Uruguai","CL":"Chile","CO":"Colombia","EC":"Equador",
    "MX":"Mexico","PE":"Peru","AU":"Australia","CA":"Canada",
    "JP":"Japao","CN":"China","NL":"Holanda","CH":"Suica",
}


def api_get(endpoint, params=None):
    p = {"access_token": ACCESS_TOKEN, **(params or {})}
    r = requests.get(f"{BASE_URL}/{endpoint}", params=p, timeout=30)
    if not r.ok:
        raise RuntimeError(f"Erro Meta API {r.status_code}: {r.text[:300]}")
    return r.json()


def montar_time_range():
    """Retorna dict de date_preset ou time_range para a API."""
    # Se quiser range customizado, use:
    # return {"time_range": json.dumps({"since": DATE_SINCE, "until": DATE_UNTIL})}
    return {"date_preset": DATE_PRESET}


def buscar_conjuntos():
    """Metrica por conjunto de anuncios (adset level)."""
    campos = "adset_name,campaign_name,spend,impressions,clicks,cpc,ctr,cpm,reach,actions"
    params = {
        "level": "adset",
        "fields": campos,
        "limit": 200,
        **montar_time_range(),
    }
    dados = []
    resp = api_get(f"{AD_ACCOUNT_ID}/insights", params)
    dados.extend(resp.get("data", []))
    # Paginacao
    while resp.get("paging", {}).get("next"):
        resp = requests.get(resp["paging"]["next"], timeout=30).json()
        dados.extend(resp.get("data", []))
    return dados


def buscar_idades():
    params = {
        "level": "account",
        "fields": "spend,impressions,clicks",
        "breakdowns": "age",
        "limit": 20,
        **montar_time_range(),
    }
    return api_get(f"{AD_ACCOUNT_ID}/insights", params).get("data", [])


def buscar_paises():
    params = {
        "level": "account",
        "fields": "spend,impressions,clicks",
        "breakdowns": "country",
        "limit": 50,
        **montar_time_range(),
    }
    return api_get(f"{AD_ACCOUNT_ID}/insights", params).get("data", [])


def extrair_conv(actions):
    if not actions:
        return None
    for a in actions:
        if a.get("action_type") in (
            "purchase", "omni_purchase",
            "offsite_conversion.fb_pixel_purchase",
        ):
            return float(a.get("value", 0))
    return None


def processar(conjuntos_raw, idades_raw, paises_raw):
    campanhas = []
    total_gasto = total_impressoes = total_cliques = 0.0

    for c in conjuntos_raw:
        gasto      = float(c.get("spend") or 0)
        impressoes = int(c.get("impressions") or 0)
        cliques    = int(c.get("clicks") or 0)
        # CTR: Meta API retorna como percentual (ex: "1.88" = 1.88%)
        ctr_raw    = float(c.get("ctr") or 0)
        cpc_raw    = float(c.get("cpc") or 0) if c.get("cpc") else (gasto/cliques if cliques else None)
        cpm_raw    = float(c.get("cpm") or 0) if c.get("cpm") else None
        alcance    = int(c.get("reach") or 0) if c.get("reach") else None
        conv       = extrair_conv(c.get("actions"))
        nome       = c.get("adset_name") or c.get("campaign_name") or "Desconhecido"

        campanhas.append({
            "nome":       nome,
            "gasto":      round(gasto, 2),
            "impressoes": impressoes,
            "cliques":    cliques,
            "cpc":        round(cpc_raw, 2) if cpc_raw else None,
            "ctr":        round(ctr_raw, 2),     # percentual: 1.88 = 1.88%
            "cpm":        round(cpm_raw, 2) if cpm_raw else None,
            "alcance":    alcance,
            "conv":       round(conv, 1) if conv is not None else None,
        })
        total_gasto      += gasto
        total_impressoes += impressoes
        total_cliques    += cliques

    campanhas.sort(key=lambda x: x["gasto"], reverse=True)

    # Idades
    ORDEM_FAIXAS = ["13-17","18-24","25-34","35-44","45-54","55-64","65+"]
    idades_map = {}
    for i in idades_raw:
        faixa = i.get("age", "Desconhecido")
        if faixa not in idades_map:
            idades_map[faixa] = {"faixa": faixa, "gasto": 0, "impressoes": 0, "cliques": 0}
        idades_map[faixa]["gasto"]      += float(i.get("spend") or 0)
        idades_map[faixa]["impressoes"] += int(i.get("impressions") or 0)
        idades_map[faixa]["cliques"]    += int(i.get("clicks") or 0)

    idades = []
    for f in ORDEM_FAIXAS:
        if f in idades_map:
            d = idades_map[f]
            idades.append({
                "faixa":      f,
                "gasto":      round(d["gasto"], 2),
                "impressoes": d["impressoes"],
                "cliques":    d["cliques"],
            })

    # Paises — agrupar e pegar top 7
    geos_map = {}
    for p in paises_raw:
        codigo = p.get("country", "??")
        nome   = NOMES_PAIS.get(codigo, codigo)
        gasto  = float(p.get("spend") or 0)
        if gasto <= 0:
            continue
        if nome not in geos_map:
            geos_map[nome] = {"local": nome, "gasto": 0.0, "impressoes": 0, "cliques": 0}
        geos_map[nome]["gasto"]      += gasto
        geos_map[nome]["impressoes"] += int(p.get("impressions") or 0)
        geos_map[nome]["cliques"]    += int(p.get("clicks") or 0)

    geos = sorted(geos_map.values(), key=lambda x: x["gasto"], reverse=True)[:7]
    for g in geos:
        g["gasto"] = round(g["gasto"], 2)

    cpc_medio = round(total_gasto / total_cliques, 3) if total_cliques else 0

    return {
        "totalGasto":      round(total_gasto, 2),
        "totalImpressoes": int(total_impressoes),
        "totalCliques":    int(total_cliques),
        "cpcMedio":        cpc_medio,
        "campanhas":       campanhas,
        "idades":          idades,
        "geos":            geos,
    }


def atualizar_html(dados):
    with open(ARQUIVO_DASH, encoding="utf-8") as f:
        html = f.read()

    novo_json = json.dumps(dados, ensure_ascii=False, indent=2)
    padrao = r"(const DADOS_META\s*=\s*)(\{[\s\S]*?\})(\s*;)"
    novo_html, n = re.subn(padrao, lambda m: m.group(1) + novo_json + m.group(3), html)
    if n == 0:
        raise RuntimeError("DADOS_META nao encontrado no HTML")

    with open(ARQUIVO_DASH, "w", encoding="utf-8") as f:
        f.write(novo_html)
    print(f"  DADOS_META atualizado ({len(novo_html):,} chars)")


def main():
    print(f"\n=== Meta Ads — {datetime.now().strftime('%d/%m/%Y %H:%M')} ===\n")

    if ACCESS_TOKEN == "SEU_TOKEN_AQUI":
        print("  ATENCAO: Configure ACCESS_TOKEN e AD_ACCOUNT_ID neste arquivo antes de executar.")
        return

    print("Buscando conjuntos de anuncios...")
    conjuntos = buscar_conjuntos()
    print(f"  {len(conjuntos)} conjuntos")

    print("Buscando faixas etarias...")
    idades = buscar_idades()
    print(f"  {len(idades)} faixas")

    print("Buscando paises...")
    paises = buscar_paises()
    print(f"  {len(paises)} paises")

    print("\nProcessando...")
    dados = processar(conjuntos, idades, paises)
    print(f"  Gasto total:  R$ {dados['totalGasto']:,.2f}")
    print(f"  Impressoes:   {dados['totalImpressoes']:,}")
    print(f"  Cliques:      {dados['totalCliques']:,}")
    print(f"  Campanhas:    {len(dados['campanhas'])}")

    print(f"\nAtualizando {ARQUIVO_DASH}...")
    atualizar_html(dados)
    print("\nMeta Ads atualizado com sucesso!")


if __name__ == "__main__":
    main()
