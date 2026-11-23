"""Testes do provedor Gemini/OpenAI (radar/provedores.py). Não usam API nenhuma.

O cliente OpenAI é trocado por um falso que guarda o que recebeu e devolve
uma resposta pronta, no mesmo formato do SDK.
"""

import json
from types import SimpleNamespace

import httpx2
import openai
import pytest

import radar.provedores as provedores
from radar.modelos import obter_modelo
from radar.provedores import ErroProvedor, Imagem, chamar_provedor

GEMINI = obter_modelo("gemini-3.5-flash-lite")
DADOS = {"nivel_risco": "baixo"}


def _resposta(conteudo=json.dumps(DADOS), fim="stop", entrada=100, saida=50, total=400):
    uso = SimpleNamespace(prompt_tokens=entrada, completion_tokens=saida, total_tokens=total)
    escolha = SimpleNamespace(finish_reason=fim, message=SimpleNamespace(content=conteudo))
    return SimpleNamespace(choices=[escolha], usage=uso)


@pytest.fixture
def cliente_falso(monkeypatch):
    """Troca o OpenAI por um falso. Devolve um dict com o que foi enviado."""
    monkeypatch.setenv("GEMINI_API_KEY", "chave-de-teste")
    monkeypatch.setenv("OPENAI_API_KEY", "chave-de-teste")
    enviado = {"resposta": _resposta()}

    class Falso:
        def __init__(self, **config):
            enviado["config"] = config
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

        def _create(self, **pedido):
            enviado["pedido"] = pedido
            if isinstance(enviado["resposta"], Exception):
                raise enviado["resposta"]
            return enviado["resposta"]

    monkeypatch.setattr(provedores, "OpenAI", Falso)
    return enviado


def _erro_http(classe, status):
    pedido = httpx2.Request("POST", "https://exemplo.invalid")
    return classe("erro", response=httpx2.Response(status, request=pedido), body=None)


# --- O que é enviado --------------------------------------------------------


def test_gemini_usa_endpoint_compativel_e_saida_estruturada(cliente_falso):
    chamar_provedor(GEMINI, "sistema", "mensagem")
    config, pedido = cliente_falso["config"], cliente_falso["pedido"]
    assert config["base_url"] == provedores.GEMINI_BASE_URL
    assert pedido["model"] == "gemini-3.5-flash-lite"
    assert pedido["messages"][0] == {"role": "system", "content": "sistema"}
    assert pedido["messages"][1] == {"role": "user", "content": "mensagem"}
    formato = pedido["response_format"]
    assert formato["type"] == "json_schema"
    assert formato["json_schema"]["strict"] is True
    assert "nivel_risco" in formato["json_schema"]["schema"]["properties"]
    assert pedido["reasoning_effort"] == provedores.ESFORCO_GEMINI
    assert pedido["max_completion_tokens"] == provedores.MAX_TOKENS_SAIDA


def test_openai_usa_endereco_padrao_e_nao_manda_esforco(cliente_falso):
    chamar_provedor(obter_modelo("openai:gpt-teste"), "s", "m")
    assert cliente_falso["config"]["base_url"] is None
    assert cliente_falso["pedido"]["model"] == "gpt-teste"
    assert "reasoning_effort" not in cliente_falso["pedido"]


def test_imagem_vai_como_data_url(cliente_falso):
    chamar_provedor(GEMINI, "s", "m", Imagem("image/png", "AAAA"))
    partes = cliente_falso["pedido"]["messages"][1]["content"]
    assert partes[0] == {"type": "text", "text": "m"}
    assert partes[1]["image_url"]["url"] == "data:image/png;base64,AAAA"


# --- O que volta --------------------------------------------------------------


def test_devolve_dados_e_conta_raciocinio_como_saida(cliente_falso):
    resposta = chamar_provedor(GEMINI, "s", "m")
    assert resposta.dados == DADOS
    assert (resposta.tokens_in, resposta.tokens_out) == (100, 300)  # 400 - 100


def test_json_quebrado_vira_dict_vazio(cliente_falso):
    cliente_falso["resposta"] = _resposta(conteudo='{"nivel_risco": ')
    assert chamar_provedor(GEMINI, "s", "m").dados == {}


def test_resposta_cortada_vira_erro_do_provedor(cliente_falso):
    cliente_falso["resposta"] = _resposta(fim="length")
    with pytest.raises(ErroProvedor, match="cortada"):
        chamar_provedor(GEMINI, "s", "m")


# --- Erros ----------------------------------------------------------------------


def test_sem_chave_avisa_qual_variavel_falta(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ErroProvedor, match="GEMINI_API_KEY"):
        chamar_provedor(GEMINI, "s", "m")


@pytest.mark.parametrize(
    ("classe", "status", "trecho"),
    [
        (openai.RateLimitError, 429, "Limite de uso"),
        (openai.AuthenticationError, 401, "Chave recusada"),
        (openai.InternalServerError, 503, "HTTP 503"),
    ],
)
def test_erros_do_sdk_viram_erro_do_provedor(cliente_falso, classe, status, trecho):
    cliente_falso["resposta"] = _erro_http(classe, status)
    with pytest.raises(ErroProvedor, match=trecho):
        chamar_provedor(GEMINI, "s", "m")


def test_falha_de_conexao_vira_erro_do_provedor(cliente_falso):
    pedido = httpx2.Request("POST", "https://exemplo.invalid")
    cliente_falso["resposta"] = openai.APIConnectionError(request=pedido)
    with pytest.raises(ErroProvedor, match="Sem conexão"):
        chamar_provedor(GEMINI, "s", "m")


def test_mensagem_de_erro_nao_vaza_a_chave(cliente_falso):
    cliente_falso["resposta"] = _erro_http(openai.AuthenticationError, 401)
    with pytest.raises(ErroProvedor) as erro:
        chamar_provedor(GEMINI, "s", "m")
    assert "chave-de-teste" not in str(erro.value)