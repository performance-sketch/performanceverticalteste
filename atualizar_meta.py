"""
atualizar_meta.py
=================
Busca dados reais da Meta Ads API e atualiza o index.html.

Coleta:
  - Perfil: seguidores IG + FB, histórico de variação
  - Ads pagos: 5 períodos (d7/d14/d30/d90/max) com campanhas, idades, países, gênero, dispositivos
  - Dados diários: 365 dias para ranges customizados no dashboard
  - Testes A/B: top 2 adsets com mais de 1 anúncio ativo
  - Orgânico: top 20 posts do Instagram por impressões
  - Por anúncio: dados a nível de ad (last_30d)
  - Objetivos: objetivo de cada campanha

Execute: python atualizar_meta.py
"""

import requests
import json
import re
from datetime import datetime, timedelta
from collections import defaultdict

# ─── CONFIGURACAO ─────────────────────────────────────────────────────────────
ACCESS_TOKEN  = "EAASW2NZCdwiwBRjZBpgb4Unpo2rqHB8iSJfZAt3BkkHB3pxrkevSo0UYx5RnF5hN7dnZCUV5yqwuPtfVUqhE3gAyOcfbLvYVhmMb5Cq1OAZBtJQ9cCRQAIce6wU7QNiX1iy11KH8tELm38U8HKTZCIgriWrUZBUdP4l60xZB4zxDgJVyZAC2bllLHsyDHnos83noLfm9SX14s0ZCmAP0iLTZBAw5OShUTb84yf4AgQCz201"
AD_ACCOUNT_ID = "act_2613909812239242"
PAGE_TOKEN    = "EAASW2NZCdwiwBRhnRP1xyNqDBEZAApFHZAUL3jD9FOUwmxi0xrCCPW4vuqhEy2RlGkM9naT2aMipZAtOipJu7Kd7qkCrAos5iH65C9jSDFzcJzMp1C3vJcRauHF9YtVFxlJNq6yX4QaXJjRZAMbZCkQYeeTk4ZArF5jVlaD24Hn1waMocOEPUSfL94Ryu0u8Q1cle0ZD"
PAGE_ID       = "187791431625497"
IG_ID         = "17841404363695690"
ARQUIVO_DASH  = "index.html"
API_VERSION   = "v19.0"
BASE_URL      = f"https://graph.facebook.com/{API_VERSION}"

PERIODOS = [
    ("d7",  "last_7d"),
    ("d14", "last_14d"),
    ("d30", "last_30d"),
    ("d90", "last_90d"),
    ("max", "maximum"),
]
# ──────────────────────────────────────────────────────────────────────────────

NOMES_PAIS = {
    "BR":"Brasil","US":"EUA","AR":"Argentina","GB":"Reino Unido",
    "DE":"Alemanha","FR":"Franca","IT":"Italia","ES":"Espanha",
    "PT":"Portugal","UY":"Uruguai","CL":"Chile","CO":"Colombia","EC":"Equador",
    "MX":"Mexico","PE":"Peru","AU":"Australia","CA":"Canada",
    "JP":"Japao","CN":"China","NL":"Holanda","CH":"Suica",
}


def api_get(endpoint, params=None, token=None):
    p = {"access_token": token or ACCESS_TOKEN, **(params or {})}
    r = requests.get(f"{BASE_URL}/{endpoint}", params=p, timeout=30)
    if not r.ok:
        raise RuntimeError(f"Erro Meta API {r.status_code}: {r.text[:300]}")
    return r.json()


def buscar_perfil():
    """Busca seguidores do Instagram e Facebook."""
    try:
        ig = api_get(IG_ID, {"fields": "followers_count,media_count"}, token=PAGE_TOKEN)
        fb = api_get(PAGE_ID, {"fields": "fan_count,name"}, token=PAGE_TOKEN)
        return {
            "igFollowers":  ig.get("followers_count", 0),
            "igMedia":      ig.get("media_count", 0),
            "fbFollowers":  fb.get("fan_count", 0),
            "fbNome":       fb.get("name", ""),
        }
    except Exception as e:
        print(f"  [AVISO] Nao foi possivel buscar perfil: {e}")
        return {"igFollowers": 0, "igMedia": 0, "fbFollowers": 0, "fbNome": ""}


def buscar_conjuntos(date_params):
    campos = "campaign_id,campaign_name,spend,impressions,clicks,cpc,ctr,cpm,reach,actions"
    params = {"level": "campaign", "fields": campos, "limit": 200, **date_params}
    dados = []
    try:
        resp = api_get(f"{AD_ACCOUNT_ID}/insights", params)
        dados.extend(resp.get("data", []))
        while resp.get("paging", {}).get("next"):
            resp = requests.get(resp["paging"]["next"], timeout=30).json()
            dados.extend(resp.get("data", []))
    except Exception as e:
        print(f"  [AVISO] buscar_conjuntos: {e}")
    return dados


def buscar_idades(date_params):
    params = {
        "level": "account", "fields": "spend,impressions,clicks",
        "breakdowns": "age", "limit": 20, **date_params,
    }
    try:
        return api_get(f"{AD_ACCOUNT_ID}/insights", params).get("data", [])
    except Exception as e:
        print(f"  [AVISO] buscar_idades: {e}")
        return []


def buscar_paises(date_params):
    params = {
        "level": "account", "fields": "spend,impressions,clicks",
        "breakdowns": "country", "limit": 50, **date_params,
    }
    try:
        return api_get(f"{AD_ACCOUNT_ID}/insights", params).get("data", [])
    except Exception as e:
        print(f"  [AVISO] buscar_paises: {e}")
        return []


def buscar_genero(date_params):
    """Breakdown por genero para o periodo informado."""
    params = {
        "level": "account", "fields": "spend,impressions,clicks",
        "breakdowns": "gender", "limit": 10, **date_params,
    }
    try:
        raw = api_get(f"{AD_ACCOUNT_ID}/insights", params).get("data", [])
        return [{"genero":    r.get("gender", "?"),
                 "gasto":     round(float(r.get("spend") or 0), 2),
                 "impressoes":int(r.get("impressions") or 0),
                 "cliques":   int(r.get("clicks") or 0)} for r in raw]
    except Exception as e:
        print(f"  [AVISO] buscar_genero: {e}")
        return []


def buscar_dispositivos(date_params):
    """Breakdown por plataforma/dispositivo."""
    params = {
        "level": "account", "fields": "spend,impressions,clicks",
        "breakdowns": "device_platform", "limit": 20, **date_params,
    }
    try:
        raw = api_get(f"{AD_ACCOUNT_ID}/insights", params).get("data", [])
        return [{"dispositivo": r.get("device_platform", "?"),
                 "gasto":      round(float(r.get("spend") or 0), 2),
                 "impressoes": int(r.get("impressions") or 0),
                 "cliques":    int(r.get("clicks") or 0)} for r in raw]
    except Exception as e:
        print(f"  [AVISO] buscar_dispositivos: {e}")
        return []


def buscar_objetivo_campanha():
    """Retorna dict {campaign_id: objetivo} para todas as campanhas."""
    try:
        resp = api_get(f"{AD_ACCOUNT_ID}/campaigns", {
            "fields": "id,objective", "limit": 200
        })
        return {c["id"]: c.get("objective", "") for c in resp.get("data", [])}
    except Exception as e:
        print(f"  [AVISO] buscar_objetivo_campanha: {e}")
        return {}


def buscar_posts_organicos(limit=20):
    """Busca posts organicos do Instagram com metricas de alcance e engajamento."""
    campos = "id,caption,media_type,timestamp,like_count,comments_count,permalink,media_url,thumbnail_url"
    try:
        resp = api_get(f"{IG_ID}/media", {"fields": campos, "limit": min(limit, 50)}, token=PAGE_TOKEN)
        posts = resp.get("data", [])
        resultado = []
        for p in posts[:limit]:
            item = {
                "id":         p.get("id"),
                "tipo":       p.get("media_type", "IMAGE"),
                "legenda":    (p.get("caption") or "")[:120],
                "data":       p.get("timestamp", "")[:10],
                "likes":      p.get("like_count", 0),
                "comentarios":p.get("comments_count", 0),
                "url":        p.get("permalink", ""),
                "thumbnail":  p.get("thumbnail_url") or p.get("media_url") or "",
                "reach":      0,
                "impressoes": 0,
            }
            try:
                ins = api_get(f"{p['id']}/insights",
                              {"metric": "reach,impressions"}, token=PAGE_TOKEN)
                for m in ins.get("data", []):
                    n = m.get("name")
                    v = (m.get("values") or [{}])[-1].get("value", 0)
                    if n == "reach":       item["reach"]      = v
                    if n == "impressions": item["impressoes"] = v
            except Exception:
                pass
            resultado.append(item)
        resultado.sort(key=lambda x: x["impressoes"], reverse=True)
        return resultado
    except Exception as e:
        print(f"  [AVISO] buscar_posts_organicos: {e}")
        return []


def buscar_por_anuncio(date_preset="last_30d"):
    """Busca dados a nivel de anuncio para o periodo informado."""
    campos = ("ad_id,ad_name,adset_id,adset_name,campaign_id,campaign_name,"
              "spend,impressions,clicks,ctr,cpc,reach,actions")
    params = {"level": "ad", "fields": campos, "date_preset": date_preset, "limit": 500}
    dados = []
    try:
        resp = api_get(f"{AD_ACCOUNT_ID}/insights", params)
        dados.extend(resp.get("data", []))
        while resp.get("paging", {}).get("next"):
            resp = requests.get(resp["paging"]["next"], timeout=30).json()
            dados.extend(resp.get("data", []))
    except Exception as e:
        print(f"  [AVISO] buscar_por_anuncio: {e}")
    resultado = []
    for a in dados:
        spend = float(a.get("spend") or 0)
        if spend <= 0:
            continue
        msg = _extrair_msg_dia(a.get("actions", []))
        resultado.append({
            "adId":      a.get("ad_id", ""),
            "nome":      a.get("ad_name", ""),
            "adsetId":   a.get("adset_id", ""),
            "adsetNome": a.get("adset_name", ""),
            "campId":    a.get("campaign_id", ""),
            "campNome":  a.get("campaign_name", ""),
            "gasto":     round(spend, 2),
            "impressoes":int(a.get("impressions") or 0),
            "cliques":   int(a.get("clicks") or 0),
            "ctr":       round(float(a.get("ctr") or 0), 3),
            "cpc":       round(float(a.get("cpc") or 0), 3) if a.get("cpc") else None,
            "alcance":   int(a.get("reach") or 0),
            "mensagens": msg,
        })
    resultado.sort(key=lambda x: x["gasto"], reverse=True)
    return resultado


_MSG_ACTIONS = {
    "onsite_conversion.total_messaging_connection":        "conexoes",
    "onsite_conversion.messaging_first_reply":             "firstReply",
    "onsite_conversion.messaging_conversation_started_7d": "conversas",
}


def _extrair_msg_dia(actions):
    out = {"conexoes": 0, "firstReply": 0, "conversas": 0}
    for a in (actions or []):
        chave = _MSG_ACTIONS.get(a.get("action_type"))
        if chave:
            out[chave] += int(float(a.get("value", 0)))
    return out


def buscar_diario():
    """Totais diarios dos ultimos 365 dias para suportar ranges customizados."""
    hoje   = datetime.now()
    inicio = hoje - timedelta(days=365)
    params = {
        "level": "account",
        "fields": "spend,impressions,clicks,actions",
        "time_range": json.dumps({
            "since": inicio.strftime("%Y-%m-%d"),
            "until": hoje.strftime("%Y-%m-%d"),
        }),
        "time_increment": 1,
        "limit": 500,
    }
    dados = []
    try:
        resp = api_get(f"{AD_ACCOUNT_ID}/insights", params)
        dados.extend(resp.get("data", []))
        while resp.get("paging", {}).get("next"):
            resp = requests.get(resp["paging"]["next"], timeout=30).json()
            dados.extend(resp.get("data", []))
    except Exception as e:
        print(f"  [AVISO] buscar_diario: {e}")
        return []

    result = []
    for d in dados:
        if float(d.get("spend") or 0) <= 0:
            continue
        msg = _extrair_msg_dia(d.get("actions", []))
        result.append({
            "data":       d["date_start"],
            "gasto":      round(float(d.get("spend") or 0), 2),
            "impressoes": int(d.get("impressions") or 0),
            "cliques":    int(d.get("clicks") or 0),
            "mensagens":  msg,
        })
    return result


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


def processar(conjuntos_raw, idades_raw, paises_raw, objetivos=None):
    campanhas = []
    total_gasto = total_impressoes = total_cliques = 0.0

    for c in conjuntos_raw:
        gasto      = float(c.get("spend") or 0)
        impressoes = int(c.get("impressions") or 0)
        cliques    = int(c.get("clicks") or 0)
        ctr_raw    = float(c.get("ctr") or 0)
        cpc_raw    = float(c.get("cpc") or 0) if c.get("cpc") else (gasto/cliques if cliques else None)
        cpm_raw    = float(c.get("cpm") or 0) if c.get("cpm") else None
        alcance    = int(c.get("reach") or 0) if c.get("reach") else None
        conv       = extrair_conv(c.get("actions"))
        nome       = c.get("campaign_name") or "Desconhecido"
        camp_id    = c.get("campaign_id") or c.get("id") or ""

        campanhas.append({
            "id":         camp_id,
            "nome":       nome,
            "objetivo":   (objetivos or {}).get(camp_id, ""),
            "gasto":      round(gasto, 2),
            "impressoes": impressoes,
            "cliques":    cliques,
            "cpc":        round(cpc_raw, 2) if cpc_raw else None,
            "ctr":        round(ctr_raw, 2),
            "cpm":        round(cpm_raw, 2) if cpm_raw else None,
            "alcance":    alcance,
            "conv":       round(conv, 1) if conv is not None else None,
        })
        total_gasto      += gasto
        total_impressoes += impressoes
        total_cliques    += cliques

    campanhas.sort(key=lambda x: x["gasto"], reverse=True)

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

    msg = {"conexoes": 0, "firstReply": 0, "conversas": 0, "bloqueios": 0}
    MSG_KEYS = {
        "onsite_conversion.total_messaging_connection":        "conexoes",
        "onsite_conversion.messaging_first_reply":             "firstReply",
        "onsite_conversion.messaging_conversation_started_7d": "conversas",
        "onsite_conversion.messaging_block":                   "bloqueios",
    }
    for c in conjuntos_raw:
        for a in (c.get("actions") or []):
            chave = MSG_KEYS.get(a.get("action_type", ""))
            if chave:
                msg[chave] += float(a.get("value", 0) or 0)

    return {
        "totalGasto":      round(total_gasto, 2),
        "totalImpressoes": int(total_impressoes),
        "totalCliques":    int(total_cliques),
        "cpcMedio":        cpc_medio,
        "campanhas":       campanhas,
        "idades":          idades,
        "geos":            geos,
        "mensagens": {
            "conexoes":   int(msg["conexoes"]),
            "firstReply": int(msg["firstReply"]),
            "conversas":  int(msg["conversas"]),
            "bloqueios":  int(msg["bloqueios"]),
        },
    }


HISTORICO_ARQUIVO = "perfil_historico.json"
DIAS_POR_PERIODO  = {"d7": 7, "d14": 14, "d30": 30, "d90": 90}


def buscar_anterior_ads(dias):
    hoje = datetime.now()
    fim  = (hoje - timedelta(days=dias)).strftime("%Y-%m-%d")
    ini  = (hoje - timedelta(days=dias * 2)).strftime("%Y-%m-%d")
    params = {
        "level": "account",
        "fields": "spend,impressions,clicks,actions",
        "time_range": json.dumps({"since": ini, "until": fim}),
        "limit": 1,
    }
    try:
        resp = api_get(f"{AD_ACCOUNT_ID}/insights", params)
        row = (resp.get("data") or [{}])[0]
    except Exception as e:
        print(f"  [AVISO] buscar_anterior_ads: {e}")
        row = {}
    msg = {"conexoes": 0, "firstReply": 0, "conversas": 0}
    for a in (row.get("actions") or []):
        at = a.get("action_type", "")
        v  = float(a.get("value", 0) or 0)
        if at == "onsite_conversion.total_messaging_connection":   msg["conexoes"]   = int(v)
        elif at == "onsite_conversion.messaging_first_reply":      msg["firstReply"] = int(v)
        elif at == "onsite_conversion.messaging_conversation_started_7d": msg["conversas"] = int(v)
    return {
        "gasto":      round(float(row.get("spend") or 0), 2),
        "impressoes": int(row.get("impressions") or 0),
        "cliques":    int(row.get("clicks") or 0),
        "mensagens":  msg,
    }


def salvar_historico(perfil):
    hoje = datetime.now().strftime("%Y-%m-%d")
    try:
        with open(HISTORICO_ARQUIVO, "r", encoding="utf-8") as f:
            hist = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        hist = {}
    hist[hoje] = {"igFollowers": perfil["igFollowers"], "fbFollowers": perfil["fbFollowers"]}
    datas = sorted(hist.keys())[-365:]
    hist  = {d: hist[d] for d in datas}
    with open(HISTORICO_ARQUIVO, "w", encoding="utf-8") as f:
        json.dump(hist, f, indent=2)
    return hist


def variacao_seguidores(hist, perfil):
    hoje = datetime.now()
    resultado = {}
    for chave, dias in DIAS_POR_PERIODO.items():
        alvo = (hoje - timedelta(days=dias)).strftime("%Y-%m-%d")
        snap = None
        for d in sorted(hist.keys(), reverse=True):
            if d <= alvo:
                snap = hist[d]
                break
        if snap:
            def pct(cur, prev):
                return round((cur - prev) / prev * 100, 1) if prev > 0 else None
            resultado[chave] = {
                "ig": pct(perfil["igFollowers"], snap["igFollowers"]),
                "fb": pct(perfil["fbFollowers"], snap["fbFollowers"]),
            }
        else:
            resultado[chave] = {"ig": None, "fb": None}
    return resultado


def buscar_ab_tests(n_testes=2):
    ins_all = []
    try:
        resp = api_get(f"{AD_ACCOUNT_ID}/insights", {
            "level":       "ad",
            "fields":      "ad_id,ad_name,adset_id,adset_name,campaign_id,campaign_name,"
                           "spend,impressions,clicks,ctr,cpc,cpm,reach,actions",
            "date_preset": "last_30d",
            "limit":       500,
        })
        ins_all.extend(resp.get("data", []))
        while resp.get("paging", {}).get("next"):
            resp = requests.get(resp["paging"]["next"], timeout=30).json()
            ins_all.extend(resp.get("data", []))
    except Exception as e:
        print(f"  [AVISO] buscar_ab_tests: {e}")
        return []

    grupos = defaultdict(list)
    for row in ins_all:
        spend = float(row.get("spend") or 0)
        if spend <= 0:
            continue
        grupos[row["adset_id"]].append({
            "adId":      row["ad_id"],
            "nome":      row["ad_name"],
            "adsetId":   row["adset_id"],
            "adsetNome": row.get("adset_name", ""),
            "campNome":  row.get("campaign_name", ""),
            "spend":     round(spend, 2),
            "impressoes":int(row.get("impressions") or 0),
            "cliques":   int(row.get("clicks") or 0),
            "ctr":       round(float(row.get("ctr") or 0), 3),
            "cpc":       round(float(row.get("cpc") or 0), 3),
            "cpm":       round(float(row.get("cpm") or 0), 3),
            "alcance":   int(row.get("reach") or 0),
            "thumbnail": "",
        })

    candidatos = sorted(
        [(k, v) for k, v in grupos.items() if len(v) >= 2],
        key=lambda x: -sum(a["spend"] for a in x[1]),
    )

    top_ids = []
    for _, ads in candidatos[:n_testes]:
        ads.sort(key=lambda x: -x["spend"])
        top_ids += [a["adId"] for a in ads[:2]]

    if top_ids:
        try:
            thumb_resp = api_get("", {
                "ids":    ",".join(top_ids),
                "fields": "id,creative{thumbnail_url,image_url}",
            })
            for ad_id, ad_data in thumb_resp.items():
                cr    = ad_data.get("creative") or {}
                thumb = cr.get("thumbnail_url") or cr.get("image_url") or ""
                for _, ads in candidatos[:n_testes]:
                    for ad in ads:
                        if ad["adId"] == ad_id:
                            ad["thumbnail"] = thumb
        except Exception as e:
            print(f"  [AVISO] Thumbnails A/B: {e}")

    def score(ad):
        return (ad["ctr"] or 0) / max(ad["cpc"], 0.01)

    testes = []
    for adset_id, ads in candidatos[:n_testes]:
        ads.sort(key=lambda x: -x["spend"])
        a, b = ads[0], ads[1]
        testes.append({
            "adsetId":      adset_id,
            "adsetNome":    ads[0]["adsetNome"],
            "campNome":     ads[0]["campNome"],
            "totalAds":     len(ads),
            "a":            a,
            "b":            b,
            "vencedorCtr":  "a" if a["ctr"]   >= b["ctr"]   else "b",
            "vencedorCpc":  "a" if a["cpc"]   <= b["cpc"]   else "b",
            "vencedorGeral":"a" if score(a)   >= score(b)   else "b",
        })
    return testes


def atualizar_html(dados):
    with open(ARQUIVO_DASH, encoding="utf-8") as f:
        html = f.read()

    novo_json = json.dumps(dados, ensure_ascii=False, indent=2)
    padrao    = r"(const DADOS_META\s*=\s*)(\{[\s\S]*?\})(\s*;)"
    novo_html, n = re.subn(padrao, lambda m: m.group(1) + novo_json + m.group(3), html)
    if n == 0:
        raise RuntimeError("DADOS_META nao encontrado no HTML")

    with open(ARQUIVO_DASH, "w", encoding="utf-8") as f:
        f.write(novo_html)
    print(f"  DADOS_META atualizado ({len(novo_html):,} chars)")


def main():
    print(f"\n=== Meta Ads — {datetime.now().strftime('%d/%m/%Y %H:%M')} ===\n")

    resultado = {}

    print("Buscando perfil (Instagram + Facebook)...")
    perfil = buscar_perfil()
    hist   = salvar_historico(perfil)
    perfil["variacoes"] = variacao_seguidores(hist, perfil)
    resultado["perfil"] = perfil
    print(f"  Instagram: {perfil['igFollowers']:,} | Facebook: {perfil['fbFollowers']:,}")

    print("Buscando objetivos de campanhas...")
    objetivos = buscar_objetivo_campanha()
    print(f"  {len(objetivos)} campanhas com objetivo mapeado")

    for chave, preset in PERIODOS:
        print(f"Buscando periodo {preset}...")
        dp           = {"date_preset": preset}
        dados_periodo = processar(
            buscar_conjuntos(dp),
            buscar_idades(dp),
            buscar_paises(dp),
            objetivos=objetivos,
        )
        dias = DIAS_POR_PERIODO.get(chave)
        if dias:
            dados_periodo["anterior"] = buscar_anterior_ads(dias)
        resultado[chave] = dados_periodo
        print(f"  Gasto: R$ {dados_periodo['totalGasto']:,.2f} | "
              f"Impressoes: {dados_periodo['totalImpressoes']:,} | "
              f"Mensagens: {dados_periodo['mensagens']['conexoes']}")

    print("\nBuscando totais diarios (365 dias)...")
    resultado["diario"] = buscar_diario()
    print(f"  {len(resultado['diario'])} dias com gasto")

    print("Buscando testes A/B...")
    resultado["abTests"] = buscar_ab_tests(n_testes=2)
    print(f"  {len(resultado['abTests'])} testes")

    print("Buscando dados por anuncio (last_30d)...")
    resultado["porAnuncio"] = buscar_por_anuncio("last_30d")
    print(f"  {len(resultado['porAnuncio'])} anuncios")

    print("Buscando posts organicos do Instagram...")
    resultado["organico"] = buscar_posts_organicos(limit=20)
    print(f"  {len(resultado['organico'])} posts")

    print("Buscando genero (d30)...")
    resultado["generoD30"] = buscar_genero({"date_preset": "last_30d"})

    print("Buscando dispositivos (d30)...")
    resultado["dispositivosD30"] = buscar_dispositivos({"date_preset": "last_30d"})

    resultado["dataAtualizacao"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    print(f"\nAtualizando {ARQUIVO_DASH}...")
    atualizar_html(resultado)
    print("\nMeta Ads atualizado com sucesso!")


if __name__ == "__main__":
    main()
