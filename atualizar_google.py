import requests
import json
import re
from datetime import datetime, timedelta
from collections import defaultdict

API_KEY      = "2a3b6cc17507c2540c6b98c651a31cd95d6b"
ARQUIVO_DASH = "index.html"
BASE_URL     = "https://connectors.windsor.ai/google_ads"

def buscar_dados(date_from, date_to):
    campos = (
        "date,campaign,device,country,"
        "clicks,spend,impressions,ctr,cpc,conversions,conversion_value"
    )
    params = {
        "api_key":   API_KEY,
        "date_from": date_from,
        "date_to":   date_to,
        "fields":    campos,
    }
    r = requests.get(BASE_URL, params=params, timeout=30)
    r.raise_for_status()
    return r.json().get("data", [])


def agregar_campanhas(registros):
    campanhas = defaultdict(lambda: {
        "cliques": 0, "gasto": 0.0, "impressoes": 0,
        "conversoes": 0, "valor_conv": 0.0
    })
    for row in registros:
        nome = row.get("campaign") or "Sem campanha"
        c = campanhas[nome]
        c["cliques"]    += int(row.get("clicks", 0) or 0)
        c["gasto"]      += float(row.get("spend", 0) or 0)
        c["impressoes"] += int(row.get("impressions", 0) or 0)
        c["conversoes"] += float(row.get("conversions", 0) or 0)
        c["valor_conv"] += float(row.get("conversion_value", 0) or 0)

    resultado = []
    for nome, m in campanhas.items():
        ctr = round(m["cliques"] / m["impressoes"] * 100, 2) if m["impressoes"] else 0
        cpc = round(m["gasto"] / m["cliques"], 2) if m["cliques"] else 0
        resultado.append({
            "nome":       nome,
            "gasto":      round(m["gasto"], 2),
            "cliques":    m["cliques"],
            "impressoes": m["impressoes"],
            "ctr":        ctr,
            "cpc":        cpc,
            "conversoes": round(m["conversoes"], 1),
            "valor_conv": round(m["valor_conv"], 2),
        })
    return sorted(resultado, key=lambda x: x["gasto"], reverse=True)


def agregar_dispositivos(registros):
    dispositivos = defaultdict(lambda: {"cliques": 0, "gasto": 0.0, "impressoes": 0})
    TRADUCAO = {"DESKTOP": "Desktop", "MOBILE": "Mobile", "TABLET": "Tablet"}
    for row in registros:
        dev = TRADUCAO.get(row.get("device", ""), row.get("device", "Outros"))
        d = dispositivos[dev]
        d["cliques"]    += int(row.get("clicks", 0) or 0)
        d["gasto"]      += float(row.get("spend", 0) or 0)
        d["impressoes"] += int(row.get("impressions", 0) or 0)
    return [
        {"dispositivo": k, "gasto": round(v["gasto"], 2),
         "cliques": v["cliques"], "impressoes": v["impressoes"]}
        for k, v in sorted(dispositivos.items(), key=lambda x: x[1]["gasto"], reverse=True)
    ]


def agregar_paises(registros):
    paises = defaultdict(lambda: {"cliques": 0, "gasto": 0.0, "conversoes": 0.0})
    for row in registros:
        pais = row.get("country") or "Desconhecido"
        p = paises[pais]
        p["cliques"]    += int(row.get("clicks", 0) or 0)
        p["gasto"]      += float(row.get("spend", 0) or 0)
        p["conversoes"] += float(row.get("conversions", 0) or 0)
    return [
        {"pais": k, "gasto": round(v["gasto"], 2),
         "cliques": v["cliques"], "conversoes": round(v["conversoes"], 1)}
        for k, v in sorted(paises.items(), key=lambda x: x[1]["gasto"], reverse=True)
    ][:10]


def atualizar_html(dados):
    with open(ARQUIVO_DASH, "r", encoding="utf-8") as f:
        html = f.read()

    json_str = json.dumps(dados, ensure_ascii=False, indent=2)
    novo_html, n = re.subn(
        r"(const DADOS_GOOGLE\s*=\s*)(\{[\s\S]*?\})(\s*;)",
        rf"\g<1>{json_str}\3",
        html
    )
    if n == 0:
        raise RuntimeError("DADOS_GOOGLE nao encontrado no HTML.")

    with open(ARQUIVO_DASH, "w", encoding="utf-8") as f:
        f.write(novo_html)
    print("index.html atualizado com dados do Google Ads.")


def main():
    hoje     = datetime.today()
    date_to  = hoje.strftime("%Y-%m-%d")
    date_from = (hoje - timedelta(days=29)).strftime("%Y-%m-%d")

    print(f"Buscando Google Ads: {date_from} a {date_to} ...")
    registros = buscar_dados(date_from, date_to)
    print(f"  {len(registros)} registros recebidos.")

    campanhas   = agregar_campanhas(registros)
    dispositivos = agregar_dispositivos(registros)
    geos        = agregar_paises(registros)

    total_gasto   = round(sum(c["gasto"] for c in campanhas), 2)
    total_cliques = sum(c["cliques"] for c in campanhas)
    total_conv    = round(sum(c["conversoes"] for c in campanhas), 1)
    total_val_conv = round(sum(c["valor_conv"] for c in campanhas), 2)
    roas = round(total_val_conv / total_gasto, 2) if total_gasto else 0

    dados = {
        "totalGasto":      total_gasto,
        "totalCliques":    total_cliques,
        "totalConversoes": total_conv,
        "totalValorConv":  total_val_conv,
        "roas":            roas,
        "campanhas":       campanhas,
        "dispositivos":    dispositivos,
        "geos":            geos,
        "idades":          [],
        "genero":          [],
        "palavrasChave":   [],
        "dataAtualizacao": hoje.strftime("%d/%m/%Y %H:%M:%S"),
        "fonte":           "Windsor.ai",
    }

    atualizar_html(dados)

    print(f"\nResumo Google Ads ({date_from} a {date_to}):")
    print(f"  Gasto total:   R$ {total_gasto:,.2f}")
    print(f"  Cliques:       {total_cliques:,}")
    print(f"  Conversoes:    {total_conv}")
    print(f"  ROAS:          {roas}x")
    print(f"  Campanhas:     {len(campanhas)}")


if __name__ == "__main__":
    main()
