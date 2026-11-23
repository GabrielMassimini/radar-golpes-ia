"""Analisa um texto pelo terminal: python -m radar "texto" [--modelo X] [--prompt vN]."""

import argparse
import json
import sys

from radar import analisar


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m radar", description="Analisa um texto suspeito.")
    parser.add_argument("texto", help="mensagem a analisar (entre aspas)")
    parser.add_argument("--modelo", help="id do modelo; sem isso usa RADAR_MODELO ou o padrão")
    parser.add_argument("--prompt", default=None, help="versão do prompt, ex.: v1")
    args = parser.parse_args()

    extras = {"versao_prompt": args.prompt} if args.prompt else {}
    resultado = analisar(args.texto, modelo=args.modelo, **extras)

    sys.stdout.reconfigure(encoding="utf-8")  # acentos certos no terminal do Windows
    print(json.dumps(resultado.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()