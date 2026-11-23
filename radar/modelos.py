"""Catálogo de modelos: provedor, nome na API e preço por milhão de tokens.

Os preços são do plano PAGO (conferidos em nov/2026). Na camada grátis do
Gemini o custo real é zero, mas o radar mostra quanto custaria em produção.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

Provedor = Literal["gemini", "anthropic", "openai", "mock"]


@dataclass(frozen=True)
class Modelo:
    id: str  # nome usado no radar (variável RADAR_MODELO, evals)
    provedor: Provedor
    nome_api: str  # nome que o provedor espera na chamada
    preco_input: float  # US$ por milhão de tokens de entrada
    preco_output: float  # US$ por milhão de tokens de saída


MODELOS: dict[str, Modelo] = {
    m.id: m
    for m in [
        # Gemini (camada grátis): ai.google.dev/gemini-api/docs/pricing
        Modelo("gemini-3.5-flash-lite", "gemini", "gemini-3.5-flash-lite", 0.30, 2.50),
        Modelo("gemini-3.1-flash-lite", "gemini", "gemini-3.1-flash-lite", 0.25, 1.50),
        # Claude (opcional, pago): platform.claude.com/docs/en/about-claude/pricing
        # Haiku: preço para prompts de até 100 mil tokens (os do radar são bem menores).
        Modelo("claude-haiku-5-5", "anthropic", "claude-haiku-5-5", 0.10, 0.50),
        Modelo("claude-sonnet-5-5", "anthropic", "claude-sonnet-5-5", 2.00, 10.00),
        Modelo("claude-opus-5-5", "anthropic", "claude-opus-5-5", 4.00, 20.00),
        # Só regras, sem IA: baseline da avaliação.
        Modelo("regras", "mock", "regras", 0.0, 0.0),
        Modelo("mock", "mock", "mock", 0.0, 0.0),
    ]
}

MODELO_PADRAO = "gemini-3.5-flash-lite"


def _preco_do_ambiente(variavel: str) -> float:
    valor = os.environ.get(variavel, "").strip()
    return float(valor) if valor else 0.0


def obter_modelo(modelo_id: str) -> Modelo:
    """Busca o modelo pelo id. "openai:<nome>" aceita qualquer modelo da OpenAI."""
    if modelo_id.startswith("openai:"):
        nome = modelo_id.removeprefix("openai:")
        if not nome:
            raise ValueError("Informe o modelo depois de 'openai:', por exemplo 'openai:gpt-5-mini'.")
        return Modelo(
            modelo_id,
            "openai",
            nome,
            _preco_do_ambiente("OPENAI_PRECO_INPUT"),
            _preco_do_ambiente("OPENAI_PRECO_OUTPUT"),
        )
    try:
        return MODELOS[modelo_id]
    except KeyError:
        conhecidos = ", ".join(sorted(MODELOS))
        raise ValueError(
            f"Modelo desconhecido: '{modelo_id}'. Use um destes: {conhecidos} ou 'openai:<modelo>'."
        ) from None


def custo_usd(modelo: Modelo, tokens_in: int, tokens_out: int) -> float:
    """Custo em US$ de uma chamada, pelo preço do plano pago."""
    return (tokens_in * modelo.preco_input + tokens_out * modelo.preco_output) / 1_000_000