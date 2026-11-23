"""Testes do detector (radar/detector.py) e do leitor de .env. Não usam API nenhuma.

O provedor real é trocado por versões falsas (monkeypatch) para simular
respostas boas, respostas fora do formato e falhas de rede.
"""

import os

import pytest

import radar.detector as detector
from radar import carregar_env
from radar.detector import MAX_CARACTERES, analisar
from radar.provedores import ErroProvedor, Imagem, RespostaBruta

GOLPE = "URGENTE! Sua conta será bloqueada. Acesse banco-seguranca.top/login"

VALIDO = {
    "nivel_risco": "alto",
    "pontuacao": 90,
    "categoria": "phishing_link",
    "sinais": [
        {"sinal": "Link falso", "trecho": "banco-seguranca.top/login", "peso": "alto"},
        {"sinal": "Inventado", "trecho": "frase que não está no texto", "peso": "baixo"},
    ],
    "explicacao": "O link imita um banco.",
    "recomendacao": "Não clique.",
    "confianca": "alta",
}


def _provedor_falso(monkeypatch, respostas):
    """Troca o provedor: cada chamada devolve (ou levanta) o próximo item da lista."""
    chamadas = []

    def falso(modelo, system, mensagem, imagem=None):
        chamadas.append(mensagem)
        item = respostas[len(chamadas) - 1]
        if isinstance(item, Exception):
            raise item
        return RespostaBruta(item, tokens_in=1000, tokens_out=200)

    monkeypatch.setattr(detector, "chamar_provedor", falso)
    return chamadas


# --- Fluxo completo com o mock --------------------------------------------


def test_fluxo_completo_com_mock():
    resultado = analisar(GOLPE, modelo="mock")
    assert resultado.analise.nivel_risco == "alto"
    assert resultado.meta.tentativas == 1
    assert resultado.meta.erro is None
    assert resultado.meta.custo_usd == 0.0
    assert resultado.meta.ancoragem == 1.0  # o mock cita trechos reais
    assert {s.id for s in resultado.sinais_automaticos} >= {"tld_suspeito"}


def test_to_dict_tem_o_formato_combinado():
    dados = analisar(GOLPE, modelo="mock").to_dict()
    assert set(dados) == {"analise", "sinais_automaticos", "meta"}
    assert set(dados["meta"]) == {
        "versao_prompt", "modelo", "latencia_s", "tokens_in", "tokens_out",
        "custo_usd", "tentativas", "ancoragem", "erro",
    }


def test_usa_o_modelo_do_ambiente(monkeypatch):
    monkeypatch.setenv("RADAR_MODELO", "regras")
    assert analisar(GOLPE).meta.modelo == "regras"


# --- Entrada ----------------------------------------------------------------


def test_sem_texto_e_sem_imagem_da_erro():
    with pytest.raises(ValueError):
        analisar("   ", modelo="mock")


def test_corta_texto_muito_longo(monkeypatch):
    chamadas = _provedor_falso(monkeypatch, [VALIDO])
    analisar("a" * (MAX_CARACTERES + 500), modelo="mock")
    assert chamadas[0].count("a") <= MAX_CARACTERES + 50  # template tem poucos "a"


def test_so_imagem_avisa_que_nao_tem_texto(monkeypatch):
    chamadas = _provedor_falso(monkeypatch, [VALIDO])
    resultado = analisar("", imagem=Imagem("image/png", "AAAA"), modelo="mock")
    assert detector.SEM_TEXTO in chamadas[0]
    assert resultado.meta.ancoragem is None  # com imagem não dá para conferir trechos


# --- Nova tentativa e erros ---------------------------------------------------


def test_formato_invalido_tenta_de_novo_e_soma_tokens(monkeypatch):
    chamadas = _provedor_falso(monkeypatch, [{"nivel_risco": "altissimo"}, VALIDO])
    resultado = analisar(GOLPE, modelo="claude-haiku-5-5")
    assert len(chamadas) == 2
    assert resultado.meta.tentativas == 2
    assert resultado.meta.erro is None
    assert (resultado.meta.tokens_in, resultado.meta.tokens_out) == (2000, 400)
    assert resultado.meta.custo_usd > 0


def test_formato_invalido_duas_vezes_devolve_erro(monkeypatch):
    _provedor_falso(monkeypatch, [{}, {}])
    resultado = analisar(GOLPE, modelo="mock")
    assert resultado.analise is None
    assert resultado.meta.tentativas == 2
    assert "fora do formato" in resultado.meta.erro


def test_falha_do_provedor_nao_tenta_de_novo(monkeypatch):
    chamadas = _provedor_falso(monkeypatch, [ErroProvedor("limite atingido"), VALIDO])
    resultado = analisar(GOLPE, modelo="mock")
    assert len(chamadas) == 1
    assert resultado.analise is None
    assert "limite atingido" in resultado.meta.erro


def test_bug_de_programacao_nao_fica_escondido(monkeypatch):
    _provedor_falso(monkeypatch, [KeyError("bug")])
    with pytest.raises(KeyError):
        analisar(GOLPE, modelo="mock")


# --- Ancoragem ------------------------------------------------------------------


def test_ancoragem_pega_trecho_inventado(monkeypatch):
    _provedor_falso(monkeypatch, [VALIDO])  # 1 trecho real + 1 inventado
    assert analisar(GOLPE, modelo="mock").meta.ancoragem == 0.5


def test_ancoragem_ignora_acento_maiusculas_e_espacos(monkeypatch):
    resposta = {**VALIDO, "sinais": [{"sinal": "x", "trecho": "sua  CONTA sera bloqueada", "peso": "medio"}]}
    _provedor_falso(monkeypatch, [resposta])
    assert analisar(GOLPE, modelo="mock").meta.ancoragem == 1.0


def test_sem_sinais_citados_ancoragem_e_none(monkeypatch):
    _provedor_falso(monkeypatch, [{**VALIDO, "sinais": []}])
    assert analisar(GOLPE, modelo="mock").meta.ancoragem is None


# --- Leitor de .env -------------------------------------------------------------


def test_carregar_env_le_chaves_e_ignora_comentarios(tmp_path, monkeypatch):
    for chave in ("RADAR_TESTE_A", "RADAR_TESTE_B", "RADAR_TESTE_VAZIA"):
        monkeypatch.delenv(chave, raising=False)
    arquivo = tmp_path / ".env"
    arquivo.write_text(
        "# comentário\n\nRADAR_TESTE_A=1\nRADAR_TESTE_B=\"com aspas\"\nRADAR_TESTE_VAZIA=\n",
        encoding="utf-8",
    )
    carregar_env(arquivo)
    assert os.environ["RADAR_TESTE_A"] == "1"
    assert os.environ["RADAR_TESTE_B"] == "com aspas"
    assert "RADAR_TESTE_VAZIA" not in os.environ
    for chave in ("RADAR_TESTE_A", "RADAR_TESTE_B"):
        monkeypatch.delenv(chave)


def test_carregar_env_nao_sobrescreve_variavel_existente(tmp_path, monkeypatch):
    monkeypatch.setenv("RADAR_TESTE_A", "do painel")
    arquivo = tmp_path / ".env"
    arquivo.write_text("RADAR_TESTE_A=do arquivo", encoding="utf-8")
    carregar_env(arquivo)
    assert os.environ["RADAR_TESTE_A"] == "do painel"


def test_carregar_env_sem_arquivo_nao_faz_nada(tmp_path):
    carregar_env(tmp_path / "nao-existe.env")