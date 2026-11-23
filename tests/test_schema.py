"""Testes do contrato de saída (radar/schema.py). Não usam API nenhuma."""

import json

import pytest
from pydantic import ValidationError

from radar.schema import CATEGORIAS, Analise, json_schema

EXEMPLO = {
    "nivel_risco": "alto",
    "pontuacao": 90,
    "categoria": "phishing_link",
    "sinais": [
        {
            "sinal": "Link que imita banco",
            "trecho": "banco-seguranca.top/login",
            "peso": "alto",
        }
    ],
    "explicacao": "O link não é do banco. Ele imita o nome para roubar sua senha.",
    "recomendacao": "Não clique. Abra o aplicativo do banco direto pelo celular.",
    "confianca": "alta",
}


def _objetos(no):
    """Percorre o schema e devolve todo pedaço que descreve um objeto."""
    if isinstance(no, dict):
        if no.get("type") == "object":
            yield no
        for valor in no.values():
            yield from _objetos(valor)
    elif isinstance(no, list):
        for item in no:
            yield from _objetos(item)


def test_exemplo_valido_passa():
    analise = Analise.model_validate(EXEMPLO)
    assert analise.sinais[0].peso == "alto"


def test_rejeita_campo_que_nao_existe():
    with pytest.raises(ValidationError):
        Analise.model_validate({**EXEMPLO, "veredito": "golpe"})


def test_rejeita_campo_faltando():
    incompleto = {k: v for k, v in EXEMPLO.items() if k != "recomendacao"}
    with pytest.raises(ValidationError):
        Analise.model_validate(incompleto)


def test_rejeita_valor_fora_da_lista():
    with pytest.raises(ValidationError):
        Analise.model_validate({**EXEMPLO, "nivel_risco": "altissimo"})


def test_rejeita_pontuacao_fora_de_0_a_100():
    with pytest.raises(ValidationError):
        Analise.model_validate({**EXEMPLO, "pontuacao": 150})


def test_categorias_incluem_legitimo():
    assert "nenhum" in CATEGORIAS
    assert len(CATEGORIAS) == 13


def test_schema_estrito_em_todos_os_objetos():
    objetos = list(_objetos(json_schema()))
    assert len(objetos) == 2  # Analise e SinalEncontrado
    for objeto in objetos:
        assert objeto["additionalProperties"] is False
        assert objeto["required"] == list(objeto["properties"])


def test_schema_sem_referencias_nem_titulos():
    texto = json.dumps(json_schema())
    assert "$ref" not in texto
    assert "$defs" not in texto
    assert '"title"' not in texto


def test_schema_mantem_descricoes_para_o_modelo():
    schema = json_schema()
    assert "EXATA" in schema["properties"]["sinais"]["items"]["properties"]["trecho"]["description"]


def test_sem_limites_remove_minimo_e_maximo():
    com = json_schema()["properties"]["pontuacao"]
    sem = json_schema(sem_limites=True)["properties"]["pontuacao"]
    assert com["minimum"] == 0 and com["maximum"] == 100
    assert "minimum" not in sem and "maximum" not in sem