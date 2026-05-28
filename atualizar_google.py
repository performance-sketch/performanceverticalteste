"""
atualizar_google.py
===================
Busca dados reais do Google Ads API e atualiza o index.html.

Coleta:
  - Campanhas: gasto, cliques, impressoes, CPC, CTR, conversoes
  - Idades: breakdown por faixa etaria
  - Paises: top 7 por gasto
  - Dispositivos: mobile/desktop/tablet
  - Genero: masculino/feminino/indefinido
  - Palavras-chave: top 20 por gasto

Execute: python atualizar_google.py

─── CREDENCIAIS ─────────────────────────────────────────────────────────────
1. DEVELOPER TOKEN → Google Ads → Ferramentas → API Center
2. OAuth2 → Google Cloud Console → Criar credencial OAuth (Desktop App)
3. Rodar gerar_token_google.py uma vez para obter REFRESH_TOKEN
──────────────────────────────────────────────────────────────────────────────
"""

import json
import re
from datetime import datetime

# ─── CONFIGURACAO ─────────────────────────────────────────────────────────────
DEVELOPER_TOKEN   = "SEU_DEVELOPER_TOKEN"
CLIENT_ID         = "SEU_CLIENT_ID"
CLIENT_SECRET     = "SEU_CLIENT_SECRET"
REFRESH_TOKEN     = "SEU_REFRESH_TOKEN"
CUSTOMER_ID       = "XXXXXXXXXX"
LOGIN_CUSTOMER_ID = ""

ARQUIVO_DASH = "index.html"
DATE_RANGE   = "LAST_30_DAYS"
# ──────────────────────────────────────────────────────────────────────────────

PAISES_GEO = {
    2076:"Brasil", 2840:"EUA", 2032:"Argentina", 2826:"Reino Unido",
    2276:"Alemanha", 2250:"Franca", 2380:"Italia", 2724:"Espanha",
    2620:"Portugal", 2858:"Uruguai", 2152:"Chile", 2170:"Colombia",
    2484:"Mexico", 2604:"Peru", 2036:"Australia", 2124:"Canada",
    2392:"Japao", 2528:"Holanda", 2756:"Suica", 2356:"India",
}


def criar_cliente():
    from google.ads.googleads.client import GoogleAdsClient
    config = {
        "developer_token": DEVELOPER_TOKEN,
        "client_id":       CLIENT_ID,
        "client_secret":   CLIENT_SECRET,
        "refresh_token":   REFRESH_TOKEN,
        "use_proto_plus":  True,
    }
    if LOGIN_CUSTOMER_ID:
        config["login_customer_id"] = LOGIN_CUSTOMER_ID
    return GoogleAdsClient.load_from_dict(config)


def executar_query(client, customer_id, query):
    svc  = client.get_service("GoogleAdsService")
    resp = svc.search_stream(customer_id=customer_id, query=query)
    linhas = []
    for batch in resp:
        linhas.extend(batch.results)
    return linhas


def buscar_campanhas(client):
    query = f"""
        SELECT
            campaign.id, campaign.name,
            metrics.cost_micros, metrics.impressions, metrics.clicks,
            metrics.average_cpc, metrics.ctr,
            metrics.conversions, metrics.conversions_value
        FROM campaign
        WHERE segments.date DURING {DATE_RANGE}
          AND campaign.status != 'REMOVED'
          AND metrics.cost_micros > 0
        ORDER BY metrics.cost_micros DESC
    """
    linhas    = executar_query(client, CUSTOMER_ID, query)
    campanhas = []
    for r in linhas:
        c, m  = r.campaign, r.metrics
        gasto = m.cost_micros / 1_000_000
        cpc   = m.average_cpc / 1_000_000 if m.average_cpc else None
        campanhas.append({
            "id":        str(c.id),
            "nome":      c.name,
            "gasto":     round(gasto, 2),
            "impressoes":int(m.impressions),
            "cliques":   int(m.clicks),
            "cpc":       round(cpc, 2) if cpc else None,
            "ctr":       round(m.ctr * 100, 2),
            "conv":      round(m.conversions, 2),
            "valorConv": round(m.conversions_value, 2),
        })
    return campanhas


def buscar_idades(client):
    query = f"""
        SELECT
            ad_group_criterion.age_range.type,
            metrics.cost_micros, metrics.clicks,
            metrics.conversions, metrics.conversions_value
        FROM age_range_view
        WHERE segments.date DURING {DATE_RANGE}
          AND metrics.cost_micros > 0
    """
    FAIXAS = {
        "AGE_RANGE_18_24":"18-24","AGE_RANGE_25_34":"25-34",
        "AGE_RANGE_35_44":"35-44","AGE_RANGE_45_54":"45-54",
        "AGE_RANGE_55_64":"55-64","AGE_RANGE_65_UP":"65+",
    }
    try:
        linhas = executar_query(client, CUSTOMER_ID, query)
    except Exception as e:
        print(f"  [AVISO] buscar_idades: {e}")
        return []
    agg = {}
    for r in linhas:
        faixa = FAIXAS.get(r.ad_group_criterion.age_range.type_.name)
        if not faixa:
            continue
        m = r.metrics
        if faixa not in agg:
            agg[faixa] = {"faixa": faixa, "gasto": 0.0, "cliques": 0, "conv": 0.0, "valorConv": 0.0}
        agg[faixa]["gasto"]    += m.cost_micros / 1_000_000
        agg[faixa]["cliques"]  += int(m.clicks)
        agg[faixa]["conv"]     += m.conversions
        agg[faixa]["valorConv"]+= m.conversions_value
    return [{"faixa": f, "gasto": round(d["gasto"],2), "cliques": d["cliques"],
             "conv": round(d["conv"],2), "valorConv": round(d["valorConv"],2)}
            for f in ["18-24","25-34","35-44","45-54","55-64","65+"] if f in agg
            for d in [agg[f]]]


def buscar_paises(client):
    query = f"""
        SELECT
            geographic_view.country_criterion_id,
            metrics.cost_micros, metrics.clicks,
            metrics.conversions, metrics.conversions_value
        FROM geographic_view
        WHERE segments.date DURING {DATE_RANGE}
          AND geographic_view.location_type = 'LOCATION_OF_PRESENCE'
          AND metrics.cost_micros > 0
        ORDER BY metrics.cost_micros DESC LIMIT 50
    """
    try:
        linhas = executar_query(client, CUSTOMER_ID, query)
    except Exception as e:
        print(f"  [AVISO] buscar_paises: {e}")
        return []
    agg = {}
    for r in linhas:
        cid  = r.geographic_view.country_criterion_id
        nome = PAISES_GEO.get(cid, f"Pais-{cid}")
        m    = r.metrics
        if nome not in agg:
            agg[nome] = {"local": nome, "gasto": 0.0, "cliques": 0, "conv": 0.0, "valorConv": 0.0}
        agg[nome]["gasto"]    += m.cost_micros / 1_000_000
        agg[nome]["cliques"]  += int(m.clicks)
        agg[nome]["conv"]     += m.conversions
        agg[nome]["valorConv"]+= m.conversions_value
    geos = sorted(agg.values(), key=lambda x: x["gasto"], reverse=True)[:7]
    for g in geos:
        g["gasto"]     = round(g["gasto"], 2)
        g["conv"]      = round(g["conv"], 2)
        g["valorConv"] = round(g["valorConv"], 2)
    return geos


def buscar_dispositivos(client):
    """Breakdown por dispositivo (MOBILE, DESKTOP, TABLET)."""
    query = f"""
        SELECT
            segments.device,
            metrics.cost_micros, metrics.clicks,
            metrics.impressions, metrics.conversions
        FROM campaign
        WHERE segments.date DURING {DATE_RANGE}
          AND metrics.cost_micros > 0
    """
    try:
        linhas = executar_query(client, CUSTOMER_ID, query)
    except Exception as e:
        print(f"  [AVISO] buscar_dispositivos: {e}")
        return []
    agg = {}
    for r in linhas:
        disp = r.segments.device.name
        m    = r.metrics
        if disp not in agg:
            agg[disp] = {"dispositivo": disp, "gasto": 0.0, "cliques": 0,
                         "impressoes": 0, "conv": 0.0}
        agg[disp]["gasto"]     += m.cost_micros / 1_000_000
        agg[disp]["cliques"]   += int(m.clicks)
        agg[disp]["impressoes"]+= int(m.impressions)
        agg[disp]["conv"]      += m.conversions
    return [{"dispositivo": d["dispositivo"], "gasto": round(d["gasto"],2),
             "cliques": d["cliques"], "impressoes": d["impressoes"],
             "conv": round(d["conv"],2)}
            for d in sorted(agg.values(), key=lambda x: x["gasto"], reverse=True)]


def buscar_genero(client):
    """Breakdown por genero."""
    query = f"""
        SELECT
            ad_group_criterion.gender.type,
            metrics.cost_micros, metrics.clicks, metrics.conversions
        FROM gender_view
        WHERE segments.date DURING {DATE_RANGE}
          AND metrics.cost_micros > 0
    """
    GENEROS = {
        "GENDER_MALE":    "Masculino",
        "GENDER_FEMALE":  "Feminino",
        "GENDER_UNDETERMINED": "Indefinido",
    }
    try:
        linhas = executar_query(client, CUSTOMER_ID, query)
    except Exception as e:
        print(f"  [AVISO] buscar_genero: {e}")
        return []
    agg = {}
    for r in linhas:
        tipo = GENEROS.get(r.ad_group_criterion.gender.type_.name, "Outro")
        m    = r.metrics
        if tipo not in agg:
            agg[tipo] = {"genero": tipo, "gasto": 0.0, "cliques": 0, "conv": 0.0}
        agg[tipo]["gasto"]  += m.cost_micros / 1_000_000
        agg[tipo]["cliques"]+= int(m.clicks)
        agg[tipo]["conv"]   += m.conversions
    return [{"genero": d["genero"], "gasto": round(d["gasto"],2),
             "cliques": d["cliques"], "conv": round(d["conv"],2)}
            for d in sorted(agg.values(), key=lambda x: x["gasto"], reverse=True)]


def buscar_palavras_chave(client):
    """Top 20 keywords por gasto."""
    query = f"""
        SELECT
            ad_group_criterion.keyword.text,
            metrics.cost_micros, metrics.clicks,
            metrics.ctr, metrics.conversions
        FROM keyword_view
        WHERE segments.date DURING {DATE_RANGE}
          AND metrics.cost_micros > 0
          AND ad_group_criterion.status != 'REMOVED'
        ORDER BY metrics.cost_micros DESC LIMIT 20
    """
    try:
        linhas = executar_query(client, CUSTOMER_ID, query)
    except Exception as e:
        print(f"  [AVISO] buscar_palavras_chave: {e}")
        return []
    return [{"texto":  r.ad_group_criterion.keyword.text,
             "gasto":  round(r.metrics.cost_micros / 1_000_000, 2),
             "cliques":int(r.metrics.clicks),
             "ctr":    round(r.metrics.ctr * 100, 2),
             "conv":   round(r.metrics.conversions, 2)}
            for r in linhas]


def atualizar_html(dados):
    with open(ARQUIVO_DASH, encoding="utf-8") as f:
        html = f.read()

    novo_json = json.dumps(dados, ensure_ascii=False, indent=2)
    padrao    = r"(const DADOS_GOOGLE\s*=\s*)(\{[\s\S]*?\})(\s*;)"
    novo_html, n = re.subn(padrao, lambda m: m.group(1) + novo_json + m.group(3), html)
    if n == 0:
        raise RuntimeError("DADOS_GOOGLE nao encontrado no HTML")

    with open(ARQUIVO_DASH, "w", encoding="utf-8") as f:
        f.write(novo_html)
    print(f"  DADOS_GOOGLE atualizado ({len(novo_html):,} chars)")


def main():
    print(f"\n=== Google Ads — {datetime.now().strftime('%d/%m/%Y %H:%M')} ===\n")

    if DEVELOPER_TOKEN == "SEU_DEVELOPER_TOKEN":
        print("  ATENCAO: Configure as credenciais no topo deste arquivo.")
        print("  Veja instrucoes no cabecalho do script.")
        return

    print("Conectando ao Google Ads API...")
    client = criar_cliente()

    print("Buscando campanhas...")
    campanhas = buscar_campanhas(client)
    print(f"  {len(campanhas)} campanhas")

    print("Buscando faixas etarias...")
    idades = buscar_idades(client)

    print("Buscando paises...")
    geos = buscar_paises(client)

    print("Buscando dispositivos...")
    dispositivos = buscar_dispositivos(client)

    print("Buscando genero...")
    genero = buscar_genero(client)

    print("Buscando palavras-chave...")
    palavras_chave = buscar_palavras_chave(client)
    print(f"  {len(palavras_chave)} keywords")

    total_gasto    = sum(c["gasto"]     for c in campanhas)
    total_cliques  = sum(c["cliques"]   for c in campanhas)
    total_conv     = sum(c["conv"]      for c in campanhas)
    total_val_conv = sum(c["valorConv"] for c in campanhas)
    roas = round(total_val_conv / total_gasto, 2) if total_gasto else 0

    dados = {
        "totalGasto":      round(total_gasto, 2),
        "totalCliques":    total_cliques,
        "totalConversoes": round(total_conv, 2),
        "totalValorConv":  round(total_val_conv, 2),
        "roas":            roas,
        "campanhas":       campanhas,
        "idades":          idades,
        "geos":            geos,
        "dispositivos":    dispositivos,
        "genero":          genero,
        "palavrasChave":   palavras_chave,
        "dataAtualizacao": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
    }

    print(f"\n  Gasto: R$ {total_gasto:,.2f} | Cliques: {total_cliques:,} | Conv: {total_conv:,.1f}")
    print(f"\nAtualizando {ARQUIVO_DASH}...")
    atualizar_html(dados)
    print("\nGoogle Ads atualizado com sucesso!")


if __name__ == "__main__":
    main()
