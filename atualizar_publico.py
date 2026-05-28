"""
atualizar_publico.py
====================
Agrega dados de audiência de Meta Ads + Google Ads e atualiza DADOS_PUBLICO no index.html.

Coleta:
  Meta Ads:
    - Idades (d30)
    - Genero (d30)
    - Paises top 7
    - Dispositivos (device_platform)

  Google Ads:
    - Idades (age_range_view)
    - Genero (gender_view)
    - Paises (geographic_view)
    - Dispositivos (segments.device)

Execute: python atualizar_publico.py
"""

import requests
import json
import re
from datetime import datetime

# ─── CREDENCIAIS META ─────────────────────────────────────────────────────────
META_ACCESS_TOKEN = "EAASW2NZCdwiwBRjZBpgb4Unpo2rqHB8iSJfZAt3BkkHB3pxrkevSo0UYx5RnF5hN7dnZCUV5yqwuPtfVUqhE3gAyOcfbLvYVhmMb5Cq1OAZBtJQ9cCRQAIce6wU7QNiX1iy11KH8tELm38U8HKTZCIgriWrUZBUdP4l60xZB4zxDgJVyZAC2bllLHsyDHnos83noLfm9SX14s0ZCmAP0iLTZBAw5OShUTb84yf4AgQCz201"
META_AD_ACCOUNT   = "act_2613909812239242"
META_API_BASE     = "https://graph.facebook.com/v19.0"

# ─── CREDENCIAIS GOOGLE ───────────────────────────────────────────────────────
GOOGLE_DEVELOPER_TOKEN   = "SEU_DEVELOPER_TOKEN"
GOOGLE_CLIENT_ID         = "SEU_CLIENT_ID"
GOOGLE_CLIENT_SECRET     = "SEU_CLIENT_SECRET"
GOOGLE_REFRESH_TOKEN     = "SEU_REFRESH_TOKEN"
GOOGLE_CUSTOMER_ID       = "XXXXXXXXXX"
GOOGLE_LOGIN_CUSTOMER_ID = ""

ARQUIVO_DASH = "index.html"
DATE_RANGE   = "LAST_30_DAYS"

NOMES_PAIS = {
    "BR":"Brasil","US":"EUA","AR":"Argentina","GB":"Reino Unido",
    "DE":"Alemanha","FR":"Franca","IT":"Italia","ES":"Espanha",
    "PT":"Portugal","UY":"Uruguai","CL":"Chile","CO":"Colombia",
    "MX":"Mexico","PE":"Peru","AU":"Australia","CA":"Canada",
}

PAISES_GEO_GOOGLE = {
    2076:"Brasil", 2840:"EUA", 2032:"Argentina", 2826:"Reino Unido",
    2276:"Alemanha", 2250:"Franca", 2380:"Italia", 2724:"Espanha",
    2620:"Portugal", 2858:"Uruguai", 2152:"Chile", 2170:"Colombia",
    2484:"Mexico", 2604:"Peru", 2036:"Australia", 2124:"Canada",
}


# ─── META HELPERS ─────────────────────────────────────────────────────────────

def meta_get(endpoint, params=None):
    p = {"access_token": META_ACCESS_TOKEN, **(params or {})}
    r = requests.get(f"{META_API_BASE}/{endpoint}", params=p, timeout=30)
    if not r.ok:
        raise RuntimeError(f"Meta API {r.status_code}: {r.text[:200]}")
    return r.json()


def meta_breakdown(breakdown, date_preset="last_30d"):
    params = {
        "level": "account",
        "fields": "spend,impressions,clicks",
        "breakdowns": breakdown,
        "date_preset": date_preset,
        "limit": 50,
    }
    try:
        return meta_get(f"{META_AD_ACCOUNT}/insights", params).get("data", [])
    except Exception as e:
        print(f"  [AVISO] Meta breakdown {breakdown}: {e}")
        return []


def coletar_meta():
    print("  Coletando dados Meta (idades, gênero, paises, dispositivos)...")
    idades_raw = meta_breakdown("age")
    genero_raw = meta_breakdown("gender")
    paises_raw = meta_breakdown("country")
    disp_raw   = meta_breakdown("device_platform")

    ORDEM_FAIXAS = ["13-17","18-24","25-34","35-44","45-54","55-64","65+"]
    idades_map = {}
    for r in idades_raw:
        f = r.get("age","?")
        if f not in idades_map:
            idades_map[f] = {"faixa": f, "gasto": 0.0, "impressoes": 0, "cliques": 0}
        idades_map[f]["gasto"]      += float(r.get("spend") or 0)
        idades_map[f]["impressoes"] += int(r.get("impressions") or 0)
        idades_map[f]["cliques"]    += int(r.get("clicks") or 0)
    idades = [{"faixa": f, "gasto": round(idades_map[f]["gasto"],2),
               "impressoes": idades_map[f]["impressoes"],
               "cliques": idades_map[f]["cliques"]}
              for f in ORDEM_FAIXAS if f in idades_map]

    genero = [{"genero": r.get("gender","?"),
               "gasto":      round(float(r.get("spend") or 0), 2),
               "impressoes": int(r.get("impressions") or 0),
               "cliques":    int(r.get("clicks") or 0)}
              for r in genero_raw if float(r.get("spend") or 0) > 0]

    geos_map = {}
    for r in paises_raw:
        cod  = r.get("country","?")
        nome = NOMES_PAIS.get(cod, cod)
        g    = float(r.get("spend") or 0)
        if g <= 0: continue
        if nome not in geos_map:
            geos_map[nome] = {"local": nome, "gasto": 0.0, "impressoes": 0, "cliques": 0}
        geos_map[nome]["gasto"]      += g
        geos_map[nome]["impressoes"] += int(r.get("impressions") or 0)
        geos_map[nome]["cliques"]    += int(r.get("clicks") or 0)
    geos = sorted([{"local": d["local"], "gasto": round(d["gasto"],2),
                    "impressoes": d["impressoes"], "cliques": d["cliques"]}
                   for d in geos_map.values()], key=lambda x: x["gasto"], reverse=True)[:7]

    dispositivos = [{"dispositivo": r.get("device_platform","?"),
                     "gasto":      round(float(r.get("spend") or 0), 2),
                     "impressoes": int(r.get("impressions") or 0),
                     "cliques":    int(r.get("clicks") or 0)}
                    for r in disp_raw if float(r.get("spend") or 0) > 0]
    dispositivos.sort(key=lambda x: x["gasto"], reverse=True)

    return {"idades": idades, "genero": genero, "geos": geos, "dispositivos": dispositivos}


# ─── GOOGLE HELPERS ───────────────────────────────────────────────────────────

def criar_cliente_google():
    from google.ads.googleads.client import GoogleAdsClient
    config = {
        "developer_token": GOOGLE_DEVELOPER_TOKEN,
        "client_id":       GOOGLE_CLIENT_ID,
        "client_secret":   GOOGLE_CLIENT_SECRET,
        "refresh_token":   GOOGLE_REFRESH_TOKEN,
        "use_proto_plus":  True,
    }
    if GOOGLE_LOGIN_CUSTOMER_ID:
        config["login_customer_id"] = GOOGLE_LOGIN_CUSTOMER_ID
    return GoogleAdsClient.load_from_dict(config)


def executar_query(client, query):
    svc  = client.get_service("GoogleAdsService")
    resp = svc.search_stream(customer_id=GOOGLE_CUSTOMER_ID, query=query)
    linhas = []
    for batch in resp:
        linhas.extend(batch.results)
    return linhas


def coletar_google(client):
    print("  Coletando dados Google (idades, gênero, paises, dispositivos)...")

    # Idades
    FAIXAS = {
        "AGE_RANGE_18_24":"18-24","AGE_RANGE_25_34":"25-34",
        "AGE_RANGE_35_44":"35-44","AGE_RANGE_45_54":"45-54",
        "AGE_RANGE_55_64":"55-64","AGE_RANGE_65_UP":"65+",
    }
    idades_agg = {}
    try:
        rows = executar_query(client, f"""
            SELECT ad_group_criterion.age_range.type,
                   metrics.cost_micros, metrics.clicks, metrics.conversions
            FROM age_range_view
            WHERE segments.date DURING {DATE_RANGE} AND metrics.cost_micros > 0
        """)
        for r in rows:
            f = FAIXAS.get(r.ad_group_criterion.age_range.type_.name)
            if not f: continue
            m = r.metrics
            if f not in idades_agg:
                idades_agg[f] = {"faixa": f, "gasto": 0.0, "cliques": 0, "conv": 0.0}
            idades_agg[f]["gasto"]  += m.cost_micros / 1_000_000
            idades_agg[f]["cliques"]+= int(m.clicks)
            idades_agg[f]["conv"]   += m.conversions
    except Exception as e:
        print(f"    [AVISO] Google idades: {e}")

    idades = [{"faixa": f, "gasto": round(d["gasto"],2),
               "cliques": d["cliques"], "conv": round(d["conv"],2)}
              for f in ["18-24","25-34","35-44","45-54","55-64","65+"]
              if f in idades_agg for d in [idades_agg[f]]]

    # Gênero
    GENEROS = {"GENDER_MALE":"Masculino","GENDER_FEMALE":"Feminino","GENDER_UNDETERMINED":"Indefinido"}
    genero_agg = {}
    try:
        rows = executar_query(client, f"""
            SELECT ad_group_criterion.gender.type,
                   metrics.cost_micros, metrics.clicks, metrics.conversions
            FROM gender_view
            WHERE segments.date DURING {DATE_RANGE} AND metrics.cost_micros > 0
        """)
        for r in rows:
            g = GENEROS.get(r.ad_group_criterion.gender.type_.name, "Outro")
            m = r.metrics
            if g not in genero_agg:
                genero_agg[g] = {"genero": g, "gasto": 0.0, "cliques": 0, "conv": 0.0}
            genero_agg[g]["gasto"]  += m.cost_micros / 1_000_000
            genero_agg[g]["cliques"]+= int(m.clicks)
            genero_agg[g]["conv"]   += m.conversions
    except Exception as e:
        print(f"    [AVISO] Google genero: {e}")

    genero = [{"genero": d["genero"], "gasto": round(d["gasto"],2),
               "cliques": d["cliques"], "conv": round(d["conv"],2)}
              for d in sorted(genero_agg.values(), key=lambda x: x["gasto"], reverse=True)]

    # Países
    geos_agg = {}
    try:
        rows = executar_query(client, f"""
            SELECT geographic_view.country_criterion_id,
                   metrics.cost_micros, metrics.clicks, metrics.conversions
            FROM geographic_view
            WHERE segments.date DURING {DATE_RANGE}
              AND geographic_view.location_type = 'LOCATION_OF_PRESENCE'
              AND metrics.cost_micros > 0
            ORDER BY metrics.cost_micros DESC LIMIT 50
        """)
        for r in rows:
            nome = PAISES_GEO_GOOGLE.get(r.geographic_view.country_criterion_id, "Outro")
            m    = r.metrics
            if nome not in geos_agg:
                geos_agg[nome] = {"local": nome, "gasto": 0.0, "cliques": 0, "conv": 0.0}
            geos_agg[nome]["gasto"]  += m.cost_micros / 1_000_000
            geos_agg[nome]["cliques"]+= int(m.clicks)
            geos_agg[nome]["conv"]   += m.conversions
    except Exception as e:
        print(f"    [AVISO] Google paises: {e}")

    geos = [{"local": d["local"], "gasto": round(d["gasto"],2),
             "cliques": d["cliques"], "conv": round(d["conv"],2)}
            for d in sorted(geos_agg.values(), key=lambda x: x["gasto"], reverse=True)[:7]]

    # Dispositivos
    disp_agg = {}
    try:
        rows = executar_query(client, f"""
            SELECT segments.device,
                   metrics.cost_micros, metrics.clicks,
                   metrics.impressions, metrics.conversions
            FROM campaign
            WHERE segments.date DURING {DATE_RANGE} AND metrics.cost_micros > 0
        """)
        for r in rows:
            disp = r.segments.device.name
            m    = r.metrics
            if disp not in disp_agg:
                disp_agg[disp] = {"dispositivo": disp, "gasto": 0.0,
                                  "cliques": 0, "impressoes": 0, "conv": 0.0}
            disp_agg[disp]["gasto"]     += m.cost_micros / 1_000_000
            disp_agg[disp]["cliques"]   += int(m.clicks)
            disp_agg[disp]["impressoes"]+= int(m.impressions)
            disp_agg[disp]["conv"]      += m.conversions
    except Exception as e:
        print(f"    [AVISO] Google dispositivos: {e}")

    dispositivos = [{"dispositivo": d["dispositivo"], "gasto": round(d["gasto"],2),
                     "cliques": d["cliques"], "impressoes": d["impressoes"],
                     "conv": round(d["conv"],2)}
                    for d in sorted(disp_agg.values(), key=lambda x: x["gasto"], reverse=True)]

    return {"idades": idades, "genero": genero, "geos": geos, "dispositivos": dispositivos}


# ─── ATUALIZAR HTML ────────────────────────────────────────────────────────────

def atualizar_html(dados):
    with open(ARQUIVO_DASH, encoding="utf-8") as f:
        html = f.read()

    novo_json = json.dumps(dados, ensure_ascii=False, indent=2)
    padrao    = r"(const DADOS_PUBLICO\s*=\s*)(\{[\s\S]*?\})(\s*;)"
    novo_html, n = re.subn(padrao, lambda m: m.group(1) + novo_json + m.group(3), html)
    if n == 0:
        raise RuntimeError("DADOS_PUBLICO nao encontrado no HTML")

    with open(ARQUIVO_DASH, "w", encoding="utf-8") as f:
        f.write(novo_html)
    print(f"  DADOS_PUBLICO atualizado ({len(novo_html):,} chars)")


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    print(f"\n=== Publico-alvo — {datetime.now().strftime('%d/%m/%Y %H:%M')} ===\n")

    resultado = {"meta": {}, "google": {}, "dataAtualizacao": ""}

    # Meta (sempre disponível)
    try:
        print("Coletando Meta Ads...")
        resultado["meta"] = coletar_meta()
        print(f"  OK — {len(resultado['meta'].get('idades',[]))} faixas etarias, "
              f"{len(resultado['meta'].get('geos',[]))} paises")
    except Exception as e:
        print(f"  ERRO Meta: {e}")

    # Google (requer credenciais configuradas)
    if GOOGLE_DEVELOPER_TOKEN == "SEU_DEVELOPER_TOKEN":
        print("Google Ads: credenciais nao configuradas — pulando")
    else:
        try:
            print("Coletando Google Ads...")
            client = criar_cliente_google()
            resultado["google"] = coletar_google(client)
            print(f"  OK — {len(resultado['google'].get('idades',[]))} faixas etarias")
        except Exception as e:
            print(f"  ERRO Google: {e}")

    resultado["dataAtualizacao"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    print(f"\nAtualizando {ARQUIVO_DASH}...")
    atualizar_html(resultado)
    print("\nPublico-alvo atualizado com sucesso!")


if __name__ == "__main__":
    main()
