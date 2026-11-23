"""Testes do provedor Claude (radar/provedores.py). Não usam API nenhuma.

O cliente Anthropic é trocado por um falso que guarda o que recebeu e devolve
uma resposta pronta, no mesmo formato do SDK.
"""

import json
import subprocess
import sys
from types import SimpleNamespace

import anthropic
import httpx2
import pytest

import radar.provedores as provedores
from radar.modelos import obter_modelo
from radar.provedores import ErroProvedor, Imagem, chamar_provedor

HAIKU = obter_modelo("claude-haiku-5-5")
DADOS = {"nivel_risco": "baixo"}


def _resposta(texto=json.dumps(DADOS), fim="end_turn", blocos_extras=()):
    blocos = [*blocos_extras, SimpleNamespace(type="text", text=texto)]
    uso = SimpleNamespace(input_tokens=120, output_tokens=300)
    return SimpleNamespace(content=blocos, stop_reason=fim, usage=uso)


@pytest.fixture
def cliente_falso(monkeypatch):
    """Troca o Anthropic por um falso. Devolve um dict com o que foi enviado."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "chave-de-teste")
    enviado = {"resposta": _resposta()}

    class Falso:
        def __init__(self, **config):
            enviado["config"] = config
            self.messages = SimpleNamespace(create=self._create)

        def _create(self, **pedido):
            enviado["pedido"] = pedido
            if isinstance(enviado["resposta"], Exception):
                raise enviado["resposta"]
            return enviado["resposta"]

    monkeypatch.setattr(anthropic, "Anthropic", Falso)
    return enviado


# --- O que é enviado --------------------------------------------------------


def test_usa_saida_estruturada_sem_limites_numericos(cliente_falso):
    chamar_provedor(HAIKU, "sistema", "mensagem")
    pedido = cliente_falso["pedido"]
    assert pedido["model"] == "claude-haiku-5-5"
    assert pedido["system"] == "sistema"
    assert pedido["messages"] == [{"role": "user", "content": "mensagem"}]
    formato = pedido["output_config"]["format"]
    assert formato["type"] == "json_schema"
    pontuacao = formato["schema"]["properties"]["pontuacao"]
    assert "minimum" not in pontuacao and "maximum" not in pontuacao
    assert pedido["output_config"]["effort"] == provedores.ESFORCO_CLAUDE


def test_nao_manda_parametros_que_o_claude_recusa(cliente_falso):
    chamar_provedor(HAIKU, "s", "m")
    assert "temperature" not in cliente_falso["pedido"]
    assert "tool_choice" not in cliente_falso["pedido"]


def test_imagem_vai_antes_do_texto_em_base64(cliente_falso):
    chamar_provedor(HAIKU, "s", "m", Imagem("image/jpeg", "AAAA"))
    imagem, texto = cliente_falso["pedido"]["messages"][0]["content"]
    assert imagem["source"] == {"type": "base64", "media_type": "image/jpeg", "data": "AAAA"}
    assert texto == {"type": "text", "text": "m"}


# --- O que volta --------------------------------------------------------------


def test_devolve_dados_e_tokens(cliente_falso):
    resposta = chamar_provedor(HAIKU, "s", "m")
    assert resposta.dados == DADOS
    assert (resposta.tokens_in, resposta.tokens_out) == (120, 300)


def test_ignora_blocos_que_nao_sao_texto(cliente_falso):
    raciocinio = SimpleNamespace(type="thinking", thinking="")
    cliente_falso["resposta"] = _resposta(blocos_extras=[raciocinio])
    assert chamar_provedor(HAIKU, "s", "m").dados == DADOS


@pytest.mark.parametrize(("fim", "trecho"), [("max_tokens", "cortada"), ("refusal", "recusou")])
def test_parada_anormal_vira_erro_do_provedor(cliente_falso, fim, trecho):
    cliente_falso["resposta"] = _resposta(fim=fim)
    with pytest.raises(ErroProvedor, match=trecho):
        chamar_provedor(HAIKU, "s", "m")


# --- Erros ----------------------------------------------------------------------


def test_sem_chave_avisa_qual_variavel_falta(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ErroProvedor, match="ANTHROPIC_API_KEY"):
        chamar_provedor(HAIKU, "s", "m")


def test_limite_de_uso_vira_erro_do_provedor(cliente_falso):
    pedido = httpx2.Request("POST", "https://exemplo.invalid")
    resposta = httpx2.Response(429, request=pedido)
    cliente_falso["resposta"] = anthropic.RateLimitError("erro", response=resposta, body=None)
    with pytest.raises(ErroProvedor, match="Limite de uso"):
        chamar_provedor(HAIKU, "s", "m")


def test_falha_de_conexao_vira_erro_do_provedor(cliente_falso):
    pedido = httpx2.Request("POST", "https://exemplo.invalid")
    cliente_falso["resposta"] = anthropic.APIConnectionError(request=pedido)
    with pytest.raises(ErroProvedor, match="Sem conexão"):
        chamar_provedor(HAIKU, "s", "m")


def test_sdk_da_anthropic_so_carrega_quando_usado():
    # Processo novo: aqui dentro os testes já importaram o anthropic.
    codigo = "import sys, radar; print('anthropic' in sys.modules)"
    saida = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True, check=True)
    assert saida.stdout.strip() == "False"