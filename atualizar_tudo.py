"""
atualizar_tudo.py
=================
Orquestrador principal — atualiza todos os dados do dashboard de uma vez.

Ordem de execução:
  1. Meta Ads        (atualizar_meta.py)
  2. Google Ads      (atualizar_google.py)
  3. Publico-alvo    (atualizar_publico.py)
  4. Rezdy           (atualizar_dados.py)
  5. Respond.io      (atualizar_respondio.py)
  6. Passageiros     (atualizar_passageiros.py)

Execute: python atualizar_tudo.py
"""

import subprocess
import sys
import time
from datetime import datetime

SCRIPTS = [
    ("Meta Ads",        "atualizar_meta.py"),
    ("Google Ads",      "atualizar_google.py"),
    ("Publico-alvo",    "atualizar_publico.py"),
    ("Rezdy",           "atualizar_dados.py"),
    ("Respond.io",      "atualizar_respondio.py"),
    ("Passageiros",     "atualizar_passageiros.py"),
]

SEP = "=" * 58


def rodar(nome, script):
    print(f"\n{SEP}")
    print(f"  {nome} ({script})")
    print(SEP)
    t0     = time.time()
    result = subprocess.run([sys.executable, script], capture_output=False)
    dur    = round(time.time() - t0, 1)
    ok     = result.returncode == 0
    if not ok:
        print(f"\n  [AVISO] {script} encerrou com codigo {result.returncode}")
    return ok, dur


def main():
    inicio = datetime.now()
    print(f"\n{SEP}")
    print(f"  CENTRAL DE PERFORMANCE — Atualização Completa")
    print(f"  {inicio.strftime('%d/%m/%Y %H:%M:%S')}")
    print(SEP)

    resultados = []
    for nome, script in SCRIPTS:
        ok, dur = rodar(nome, script)
        resultados.append((nome, script, ok, dur))

    fim     = datetime.now()
    duracao = round((fim - inicio).total_seconds(), 1)

    print(f"\n{SEP}")
    print(f"  RESUMO FINAL")
    print(SEP)
    for nome, script, ok, dur in resultados:
        status = "OK" if ok else "ERRO"
        print(f"  {status:<6}  {nome:<20} {dur:>5}s   ({script})")
    print(f"\n  Duração total: {duracao}s")
    print(f"  Concluído:     {fim.strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"\n  Dashboard: https://performance-sketch.github.io/performanceverticalteste")
    print(f"{SEP}\n")

    erros = [n for n, _, ok, _ in resultados if not ok]
    if erros:
        print(f"  Scripts com erro: {', '.join(erros)}")
        print("  Verifique tokens/credenciais nos respectivos arquivos.\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
