"""
atualizar_dados.py
==================
Busca dados do Rezdy com paginacao e gera o dashboard_completo.html.
Armazena dataCriacao (booking date) e dataFulfillment (data do voo) separadamente.
Execute: python atualizar_dados.py
"""

import requests
import json
import re
from datetime import datetime, timedelta
from collections import defaultdict

# ─── CONFIGURACAO ─────────────────────────────────────────────────────────────
CHAVE_API_REZDY   = "dc7f8d97256e484b8763a983ded2ba22"
URL_BASE_REZDY    = "https://api.rezdy.com/v1"
ARQUIVO_DASHBOARD = "dashboard_completo.html"
LIMITE_TOTAL      = 1000   # total de reservas a buscar (10 chamadas de 100)
# ──────────────────────────────────────────────────────────────────────────────


def buscar_rezdy(endpoint, parametros=None):
    params = {"apiKey": CHAVE_API_REZDY, **(parametros or {})}
    resposta = requests.get(f"{URL_BASE_REZDY}/{endpoint}", params=params, timeout=20)
    resposta.raise_for_status()
    return resposta.json()


def buscar_todas_reservas():
    """Busca reservas paginando ate LIMITE_TOTAL registros."""
    todas = []
    offset = 0
    while offset < LIMITE_TOTAL:
        lote = buscar_rezdy("bookings", {"limit": 100, "offset": offset})
        reservas = lote.get("bookings", [])
        if not reservas:
            break
        todas.extend(reservas)
        print(f"  Buscando... {len(todas)} reservas ({reservas[-1].get('dateCreated','')[:10]})")
        if len(reservas) < 100:
            break
        offset += 100
    return todas


def processar_reservas(reservas):
    receita_total = sum(r.get("totalAmount", 0) for r in reservas)
    total_pago    = sum(r.get("totalPaid",   0) for r in reservas)
    total_a_pagar = sum(r.get("totalDue",    0) for r in reservas)

    contagem_status = defaultdict(int)
    for r in reservas:
        contagem_status[r.get("status", "DESCONHECIDO")] += 1

    receita_por_produto = defaultdict(float)
    for r in reservas:
        for item in r.get("items", []):
            nome = item.get("productName", "Desconhecido")
            receita_por_produto[nome] += item.get("amount", 0)

    # Reservas por dia de criacao (booking date) — ultimos 30 dias
    reservas_por_dia = defaultdict(int)
    for r in reservas:
        data = r.get("dateCreated", "")[:10]
        if data:
            reservas_por_dia[data] += 1
    ultimos_30 = dict(sorted(reservas_por_dia.items())[-30:])

    lista_tabela = []
    for r in reservas:
        itens = r.get("items", [])
        item0 = itens[0] if itens else {}

        # Data de booking (quando o cliente comprou)
        data_criacao_raw = r.get("dateCreated", "")
        data_criacao = data_criacao_raw[:10] if data_criacao_raw else ""

        # Data de fulfillment (quando o voo acontece)
        start_local = item0.get("startTimeLocal", "") or ""
        data_fulfillment = start_local[:10] if start_local else ""
        hora_fulfillment = start_local[11:16] if len(start_local) >= 16 else ""

        lista_tabela.append({
            "numeroPedido":   r.get("orderNumber"),
            "status":         r.get("status"),
            "nomeCliente":    r.get("customer", {}).get("name", "-"),
            "emailCliente":   r.get("customer", {}).get("email", "-"),
            "produto":        item0.get("productName", "-"),
            "quantidade":     item0.get("totalQuantity", 0),
            "dataCriacao":    data_criacao,        # YYYY-MM-DD booking date
            "dataFulfillment": data_fulfillment,   # YYYY-MM-DD data do voo
            "horaFulfillment": hora_fulfillment,   # HH:MM
            "valorTotal":     r.get("totalAmount", 0),
            "valorPago":      r.get("totalPaid",   0),
            "valorAPagar":    r.get("totalDue",    0),
            "moeda":          r.get("totalCurrency", "BRL"),
        })

    return {
        "total_reservas":      len(reservas),
        "receita_total":       round(receita_total, 2),
        "total_pago":          round(total_pago, 2),
        "total_a_pagar":       round(total_a_pagar, 2),
        "contagem_status":     dict(contagem_status),
        "receita_por_produto": {k: round(v, 2) for k, v in receita_por_produto.items()},
        "reservas_por_dia":    ultimos_30,
        "tabela":              lista_tabela,
    }


def processar_produtos(produtos):
    resultado = []
    for p in produtos:
        precos = [o.get("price", 0) for o in p.get("priceOptions", [])]
        resultado.append({
            "nome":           p.get("name"),
            "precoAnunciado": p.get("advertisedPrice") or (min(precos) if precos else 0),
            "moeda":          p.get("currency", "BRL"),
            "duracaoMinutos": p.get("durationMinutes", 0),
            "imagem":         (p.get("images") or [{}])[0].get("mediumSizeUrl", ""),
        })
    return resultado


def atualizar_bloco_js(html, nome_constante, novo_valor_python):
    novo_json = json.dumps(novo_valor_python, ensure_ascii=False, indent=2)
    padrao = rf"(const {nome_constante}\s*=\s*)(\{{[\s\S]*?\}}|\[[\s\S]*?\])(\s*;)"
    def substituir(match):
        return match.group(1) + novo_json + match.group(3)
    novo_html, quantidade = re.subn(padrao, substituir, html)
    if quantidade == 0:
        print(f"  [AVISO] Constante '{nome_constante}' nao encontrada no HTML.")
    return novo_html


def main():
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")
    print(f"\n=== Atualizando dashboard — {agora} ===\n")

    print(f"Buscando reservas do Rezdy (ate {LIMITE_TOTAL})...")
    reservas = buscar_todas_reservas()
    print(f"  Total: {len(reservas)} reservas encontradas.")

    print("Buscando produtos do Rezdy...")
    dados_produtos = buscar_rezdy("products", {"limit": 50})
    produtos = dados_produtos.get("products", [])
    print(f"  {len(produtos)} produtos encontrados.")

    print("\nProcessando dados...")
    resumo_rezdy   = processar_reservas(reservas)
    lista_produtos = processar_produtos(produtos)

    dados_rezdy_js = {
        "resumo":          resumo_rezdy,
        "produtos":        lista_produtos,
        "dataAtualizacao": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
    }

    print(f"Lendo {ARQUIVO_DASHBOARD}...")
    with open(ARQUIVO_DASHBOARD, "r", encoding="utf-8") as f:
        html = f.read()

    print("Atualizando dados no HTML...")
    html = atualizar_bloco_js(html, "DADOS_REZDY_LIVE", dados_rezdy_js)
    html = re.sub(
        r'(id="dataRezdy">)[^<]*(</span>)',
        rf'\g<1>{agora}\g<2>',
        html
    )

    with open(ARQUIVO_DASHBOARD, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\nDashboard atualizado com sucesso!")
    print(f"  Reservas:     {resumo_rezdy['total_reservas']}")
    print(f"  Receita total: R$ {resumo_rezdy['receita_total']:,.2f}")
    print(f"  Periodo:      {resumo_rezdy['tabela'][-1]['dataCriacao']} a {resumo_rezdy['tabela'][0]['dataCriacao']}")
    print(f"  Produtos:     {len(lista_produtos)}")
    print(f"\nAbra o arquivo: {ARQUIVO_DASHBOARD}\n")


if __name__ == "__main__":
    main()
