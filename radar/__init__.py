"""Radar de Golpes IA: núcleo de detecção (regras + LLM)."""

from __future__ import annotations

import os
from pathlib import Path

ARQUIVO_ENV = Path(__file__).resolve().parent.parent / ".env"


def carregar_env(caminho: Path = ARQUIVO_ENV) -> None:
    """Lê o .env (CHAVE=valor por linha) para as variáveis de ambiente.

    Nunca sobrescreve uma variável que já existe (na Vercel valem as do painel)
    e ignora linhas vazias, comentários (#) e valores em branco.
    """
    if not caminho.is_file():
        return
    for linha in caminho.read_text(encoding="utf-8-sig").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        chave = chave.strip()
        valor = valor.strip().strip('"').strip("'")
        if chave and valor and chave not in os.environ:
            os.environ[chave] = valor


carregar_env()

from radar.detector import Resultado, analisar  # noqa: E402  (depois do .env)

__all__ = ["Resultado", "analisar", "carregar_env"]