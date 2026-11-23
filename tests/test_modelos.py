"""Testes do catálogo de modelos (radar/modelos.py). Não usam API nenhuma."""

import pytest

from radar.modelos import MODELO_PADRAO, MODELOS, custo_usd, obter_modelo


def test_modelo_padrao_existe_e_e_gemini():
    assert obter_modelo(MODELO_PADRAO).provedor == "gemini"


def test_regras_e_mock_nao_custam_nada():
    for modelo_id in ("regras", "mock"):
        assert custo_usd(obter_modelo(modelo_id), 5_000, 1_000) == 0.0


def test_custo_por_milhao_de_tokens():
    haiku = obter_modelo("claude-haiku-5-5")
    # 1 milhão de entrada (US$ 0,10) + 1 milhão de saída (US$ 0,50)
    assert custo_usd(haiku, 1_000_000, 1_000_000) == pytest.approx(0.60)


def test_custo_de_uma_analise_tipica_e_fracao_de_centavo():
    gemini = obter_modelo("gemini-3.5-flash-lite")
    # ~2.000 tokens de entrada e ~400 de saída
    assert custo_usd(gemini, 2_000, 400) == pytest.approx(0.0016)


def test_openai_aceita_qualquer_modelo_e_le_preco_do_ambiente(monkeypatch):
    monkeypatch.setenv("OPENAI_PRECO_INPUT", "1.5")
    monkeypatch.setenv("OPENAI_PRECO_OUTPUT", "6")
    modelo = obter_modelo("openai:gpt-5-mini")
    assert modelo.provedor == "openai"
    assert modelo.nome_api == "gpt-5-mini"
    assert (modelo.preco_input, modelo.preco_output) == (1.5, 6.0)


def test_openai_sem_preco_no_ambiente_custa_zero(monkeypatch):
    monkeypatch.delenv("OPENAI_PRECO_INPUT", raising=False)
    monkeypatch.delenv("OPENAI_PRECO_OUTPUT", raising=False)
    assert custo_usd(obter_modelo("openai:gpt-5-mini"), 1_000, 1_000) == 0.0


def test_openai_sem_nome_da_erro():
    with pytest.raises(ValueError):
        obter_modelo("openai:")


def test_modelo_desconhecido_explica_as_opcoes():
    with pytest.raises(ValueError, match="gemini-3.5-flash-lite"):
        obter_modelo("modelo-que-nao-existe")


def test_ids_do_catalogo_batem_com_as_chaves():
    for chave, modelo in MODELOS.items():
        assert chave == modelo.id