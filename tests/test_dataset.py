"""Confere os datasets de avaliação (evals/*.jsonl). Não usa API nenhuma.

Um caso com rótulo ou categoria errada estraga a métrica sem dar erro nenhum,
então o formato é conferido aqui, caso por caso.
"""

import json
from pathlib import Path

import pytest

from radar.schema import CATEGORIAS

PASTA = Path(__file__).resolve().parent.parent / "evals"


def _carregar(nome):
    linhas = (PASTA / nome).read_text(encoding="utf-8").splitlines()
    return [json.loads(linha) for linha in linhas if linha.strip()]


PRINCIPAL = _carregar("dataset.jsonl")
DIFICIL = _carregar("dataset_dificil.jsonl")
TODOS = PRINCIPAL + DIFICIL

CAMPOS = {"id", "texto", "rotulo", "categorias_aceitas", "canal", "dificuldade", "tags"}
CANAIS = {"anuncio", "whatsapp", "sms", "email", "rede_social"}
DIFICULDADES = {"facil", "medio", "dificil"}
TAGS = {"injection", "parecido_com_exemplo"}


@pytest.mark.parametrize(
    ("casos", "total", "golpes", "injection"),
    [(PRINCIPAL, 61, 36, 3), (DIFICIL, 20, 12, 6)],
    ids=["principal", "dificil"],
)
def test_tamanho_e_equilibrio(casos, total, golpes, injection):
    rotulos = [c["rotulo"] for c in casos]
    assert (len(casos), rotulos.count("golpe"), rotulos.count("legitimo")) == (total, golpes, total - golpes)
    assert sum("injection" in c["tags"] for c in casos) == injection


def test_ids_unicos_nos_dois_datasets():
    ids = [c["id"] for c in TODOS]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("caso", TODOS, ids=lambda c: c["id"])
def test_caso_bem_formado(caso):
    assert set(caso) == CAMPOS
    assert caso["texto"].strip()
    assert caso["canal"] in CANAIS
    assert caso["dificuldade"] in DIFICULDADES
    assert set(caso["tags"]) <= TAGS
    assert set(caso["categorias_aceitas"]) <= set(CATEGORIAS)
    if caso["rotulo"] == "legitimo":
        assert caso["categorias_aceitas"] == ["nenhum"]
    else:
        assert caso["rotulo"] == "golpe"
        assert caso["categorias_aceitas"] and "nenhum" not in caso["categorias_aceitas"]


def test_injection_sao_golpes():
    assert all(c["rotulo"] == "golpe" for c in TODOS if "injection" in c["tags"])


def test_dificil_e_todo_dificil():
    assert {c["dificuldade"] for c in DIFICIL} == {"dificil"}


def test_textos_nao_se_repetem_entre_datasets():
    assert not {c["texto"] for c in PRINCIPAL} & {c["texto"] for c in DIFICIL}


def test_marcas_trocadas_por_termos_genericos():
    textos = " ".join(c["texto"] for c in TODOS).lower()
    assert "olx" not in textos and "ambev" not in textos