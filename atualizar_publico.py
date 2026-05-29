import requests
import json
import re
from datetime import datetime, timedelta
from collections import defaultdict

# ── Meta Ads ──────────────────────────────────────────────────────────────────
META_ACCESS_TOKEN = "EAASW2NZCdwiwBRjZBpgb4Unpo2rqHB8iSJfZAt3BkkHB3pxrkevSo0UYx5RnF5hN7dnZCUV5yqwuPtfVUqhE3gAyOcfbLvYVhmMb5Cq1OAZBtJQ9cCRQAIce6wU7QNiX1iy11KH8tELm38U8HKTZCIgriWrUZBUdP4l60xZB4zxDgJVyZAC2bllLHsyDHnos83noLfm9SX14s0ZCmAP0iLTZBAw5OShUTb84yf4AgQCz201"
META_AD_ACCOUNT  = "act_2613909812239242"
META_BASE        = "https://graph.facebook.com/v19.0"

# ── Windsor.ai (Google Ads) ───────────────────────────────────────────────────
WINDSOR_API_KEY  = "2a3b6cc17507c2540c6b98c651a31cd95d6b"
WINDSOR_BASE     = "https://connectors.windsor.ai/google_ads"

ARQUIVO_DASH     = "index.html"


# ── Meta Ads ──────────────────────────────────────────────────────────────────

def meta_get(endpoint, params=None):
    p = {"access_token": META_ACCESS_TOKEN}
    if params:
        p.update(params)
    r = requests.get(f"{META_BASE}/{endpoint}", params=p, timeout=20)
    r.raise_for_status()
    return r.json()


def coletar_meta():
    date_preset = "last_30_days"
    campos_idade   = "age,spend,impressions,clicks"
    campos_genero  = "gender,spend,impressions,clicks"
    campos_geo     = "country,spend,impressions,clicks"
    campos_device  = "impression_device,spend,impressions,clicks"

    def buscar(breakdown, fields):
        dados = []
        params = {
            "level": "account",
            "date_preset": date_preset,
            "breakdowns": breakdown,
            "fields": fields,
            "limit": 100,
        }
        resp = meta_get(f"{META_AD_ACCOUNT}/insights", params)
        dados.extend(resp.get("data", []))
        return dados

    # Idades
    idades = []
    for row in buscar("age", campos_idade):
        idades.append({
            "faixa":     row.get("age", "?"),
            "gasto":     round(float(row.get("spend", 0)), 2),
            "impressoes": int(row.get("impressions", 0)),
            "cliques":   int(row.get("clicks", 0)),
        })

    # Genero
    GENERO_MAP = {"male": "Masculino", "female": "Feminino", "unknown": "Indefinido"}
    genero = []
    for row in buscar("gender", campos_genero):
        genero.append({
            "genero":    GENERO_MAP.get(row.get("gender", ""), row.get("gender", "?")),
            "gasto":     round(float(row.get("spend", 0)), 2),
            "impressoes": int(row.get("impressions", 0)),
            "cliques":   int(row.get("clicks", 0)),
        })

    # Geos (top 7)
    geos_raw = defaultdict(lambda: {"gasto": 0.0, "impressoes": 0, "cliques": 0})
    for row in buscar("country", campos_geo):
        pais = row.get("country", "?")
        geos_raw[pais]["gasto"]     += float(row.get("spend", 0))
        geos_raw[pais]["impressoes"] += int(row.get("impressions", 0))
        geos_raw[pais]["cliques"]   += int(row.get("clicks", 0))
    geos = [
        {"local": k, "gasto": round(v["gasto"], 2),
         "impressoes": v["impressoes"], "cliques": v["cliques"]}
        for k, v in sorted(geos_raw.items(), key=lambda x: x[1]["gasto"], reverse=True)
    ][:7]

    # Dispositivos
    DEV_MAP = {
        "mobile_app": "Mobile", "mobile_web": "Mobile",
        "desktop": "Desktop", "instagram": "Instagram", "unknown": "Outros",
    }
    devs_raw = defaultdict(lambda: {"gasto": 0.0, "impressoes": 0, "cliques": 0})
    for row in buscar("impression_device", campos_device):
        dev = DEV_MAP.get(row.get("impression_device", ""), row.get("impression_device", "Outros"))
        devs_raw[dev]["gasto"]     += float(row.get("spend", 0))
        devs_raw[dev]["impressoes"] += int(row.get("impressions", 0))
        devs_raw[dev]["cliques"]   += int(row.get("clicks", 0))
    dispositivos = [
        {"dispositivo": k, "gasto": round(v["gasto"], 2),
         "impressoes": v["impressoes"], "cliques": v["cliques"]}
        for k, v in sorted(devs_raw.items(), key=lambda x: x[1]["gasto"], reverse=True)
    ]

    return {"idades": idades, "genero": genero, "geos": geos, "dispositivos": dispositivos}


# ── Google Ads via Windsor.ai ─────────────────────────────────────────────────

def coletar_google():
    hoje      = datetime.today()
    date_to   = hoje.strftime("%Y-%m-%d")
    date_from = (hoje - timedelta(days=29)).strftime("%Y-%m-%d")

    params = {
        "api_key":   WINDSOR_API_KEY,
        "date_from": date_from,
        "date_to":   date_to,
        "fields":    "date,campaign,device,country,clicks,spend,impressions,conversions",
    }
    r = requests.get(WINDSOR_BASE, params=params, timeout=30)
    r.raise_for_status()
    registros = r.json().get("data", [])

    # Dispositivos
    DEV_MAP = {"DESKTOP": "Desktop", "MOBILE": "Mobile", "TABLET": "Tablet"}
    devs = defaultdict(lambda: {"gasto": 0.0, "cliques": 0, "impressoes": 0, "conv": 0.0})
    for row in registros:
        dev = DEV_MAP.get(row.get("device", ""), row.get("device", "Outros"))
        devs[dev]["gasto"]     += float(row.get("spend", 0) or 0)
        devs[dev]["cliques"]   += int(row.get("clicks", 0) or 0)
        devs[dev]["impressoes"] += int(row.get("impressions", 0) or 0)
        devs[dev]["conv"]      += float(row.get("conversions", 0) or 0)
    dispositivos = [
        {"dispositivo": k, "gasto": round(v["gasto"], 2), "cliques": v["cliques"],
         "impressoes": v["impressoes"], "conv": round(v["conv"], 1)}
        for k, v in sorted(devs.items(), key=lambda x: x[1]["gasto"], reverse=True)
    ]

    # Geos (top 10)
    geos_raw = defaultdict(lambda: {"gasto": 0.0, "cliques": 0, "conv": 0.0})
    for row in registros:
        pais = row.get("country") or "Desconhecido"
        geos_raw[pais]["gasto"]  += float(row.get("spend", 0) or 0)
        geos_raw[pais]["cliques"] += int(row.get("clicks", 0) or 0)
        geos_raw[pais]["conv"]   += float(row.get("conversions", 0) or 0)
    geos = [
        {"local": k, "gasto": round(v["gasto"], 2),
         "cliques": v["cliques"], "conv": round(v["conv"], 1)}
        for k, v in sorted(geos_raw.items(), key=lambda x: x[1]["gasto"], reverse=True)
    ][:10]

    return {
        "idades":      [],
        "genero":      [],
        "geos":        geos,
        "dispositivos": dispositivos,
    }


# ── HTML update ───────────────────────────────────────────────────────────────

def atualizar_html(dados):
    with open(ARQUIVO_DASH, "r", encoding="utf-8") as f:
        html = f.read()

    json_str = json.dumps(dados, ensure_ascii=False, indent=2)
    novo_html, n = re.subn(
        r"(const DADOS_PUBLICO\s*=\s*)(\{[\s\S]*?\})(\s*;)",
        rf"\g<1>{json_str}\3",
        html
    )
    if n == 0:
        raise RuntimeError("DADOS_PUBLICO nao encontrado no HTML.")

    with open(ARQUIVO_DASH, "w", encoding="utf-8") as f:
        f.write(novo_html)
    print("index.html atualizado com dados de publico.")


def main():
    dados = {"meta": {}, "google": {}, "dataAtualizacao": ""}

    print("Coletando dados Meta Ads (publico)...")
    try:
        dados["meta"] = coletar_meta()
        print("  Meta OK")
    except Exception as e:
        print(f"  Meta ERRO: {e}")
        dados["meta"] = {"idades": [], "genero": [], "geos": [], "dispositivos": []}

    print("Coletando dados Google Ads via Windsor.ai (publico)...")
    try:
        dados["google"] = coletar_google()
        print("  Google OK")
    except Exception as e:
        print(f"  Google ERRO: {e}")
        dados["google"] = {"idades": [], "genero": [], "geos": [], "dispositivos": []}

    dados["dataAtualizacao"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    atualizar_html(dados)


if __name__ == "__main__":
    main()
