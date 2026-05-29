import subprocess
import sys
import time
from datetime import datetime

SCRIPTS = [
    ("Meta Ads",     "atualizar_meta.py"),
    ("Google Ads",   "atualizar_google.py"),
    ("Publico",      "atualizar_publico.py"),
    ("Rezdy",        "atualizar_dados.py"),
    ("Respond.io",   "atualizar_respondio.py"),
    ("Passageiros",  "atualizar_passageiros.py"),
    ("Linktree",     "atualizar_linktree.py"),
]


def rodar(nome, arquivo):
    print(f"\n{'='*50}")
    print(f"  Executando: {nome}  ({arquivo})")
    print(f"{'='*50}")
    inicio = time.time()
    resultado = subprocess.run([sys.executable, arquivo])
    duracao = round(time.time() - inicio, 1)
    ok = resultado.returncode == 0
    status = "OK" if ok else f"ERRO (codigo {resultado.returncode})"
    print(f"  [{status}]  {duracao}s")
    return ok, duracao


def main():
    inicio_total = time.time()
    agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    print("\n" + "="*50)
    print(f"  ATUALIZACAO DASHBOARD — {agora}")
    print("="*50)

    resultados = []
    for nome, arquivo in SCRIPTS:
        ok, duracao = rodar(nome, arquivo)
        resultados.append((nome, ok, duracao))

    duracao_total = round(time.time() - inicio_total, 1)

    print("\n" + "="*50)
    print("  RESUMO FINAL")
    print("="*50)
    erros = []
    for nome, ok, duracao in resultados:
        icone = "✓" if ok else "✗"
        print(f"  {icone}  {nome:<15} {duracao}s")
        if not ok:
            erros.append(nome)

    print(f"\n  Tempo total: {duracao_total}s")
    print(f"  Dashboard:   https://performance-sketch.github.io/performanceverticalteste/")

    if erros:
        print(f"\n  ATENCAO: Falha em: {', '.join(erros)}")
        print("  Verifique os tokens/credenciais nos arquivos correspondentes.")
        sys.exit(1)
    else:
        print("\n  Dashboard atualizado com sucesso!")


if __name__ == "__main__":
    main()
