"""Testes da API (api/index.py). Usam o modelo mock: não chamam IA nenhuma."""

import base64

import pytest
from fastapi.testclient import TestClient

import api.index as api
from radar.detector import Meta, Resultado

GOLPE = "URGENTE! Sua conta será bloqueada. Acesse banco-seguranca.top/login"
PNG = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 20).decode()


@pytest.fixture
def cliente(monkeypatch):
    monkeypatch.setenv("RADAR_MODELO", "mock")
    monkeypatch.setenv("RADAR_LIMITE_DEMO", "15")
    monkeypatch.delenv("RADAR_TOKEN", raising=False)
    monkeypatch.setattr(api, "limite_demo", api.LimitePorIp())  # contador zerado a cada teste
    return TestClient(api.app)


@pytest.fixture
def espiao(monkeypatch):
    """Troca a análise por uma que só guarda o que recebeu."""
    chamadas = []
    original = api.analisar

    def falso(texto, imagem=None):
        chamadas.append((texto, imagem))
        return original(texto or "x", modelo="mock")

    monkeypatch.setattr(api, "analisar", falso)
    return chamadas


# --- Básico ------------------------------------------------------------------------


def test_saude(cliente):
    resposta = cliente.get("/api/saude")
    assert resposta.status_code == 200
    assert resposta.json() == {"status": "ok", "versao_prompt": "v3", "modelo": "mock"}


def test_analisa_texto(cliente):
    resposta = cliente.post("/api/analisar", json={"texto": GOLPE})
    assert resposta.status_code == 200
    dados = resposta.json()
    assert dados["analise"]["nivel_risco"] == "alto"
    assert set(dados) == {"analise", "sinais_automaticos", "meta"}


def test_sem_texto_e_sem_imagem_da_400(cliente):
    assert cliente.post("/api/analisar", json={"texto": "   "}).status_code == 400


def test_texto_longo_demais_da_422(cliente):
    assert cliente.post("/api/analisar", json={"texto": "a" * 6001}).status_code == 422


def test_falha_do_modelo_da_502(cliente, monkeypatch):
    def falha(texto, imagem=None):
        return Resultado(analise=None, meta=Meta("v3", "mock", erro="Falha no provedor: HTTP 503."))

    monkeypatch.setattr(api, "analisar", falha)
    resposta = cliente.post("/api/analisar", json={"texto": GOLPE})
    assert resposta.status_code == 502
    assert "HTTP 503" in resposta.json()["detail"]


def test_sem_cors(cliente):
    resposta = cliente.get("/api/saude", headers={"Origin": "https://outro-site.example"})
    assert "access-control-allow-origin" not in resposta.headers


# --- Imagem ------------------------------------------------------------------------


def test_aceita_data_url(cliente, espiao):
    resposta = cliente.post("/api/analisar", json={"imagem_base64": f"data:image/png;base64,{PNG}"})
    assert resposta.status_code == 200
    _, imagem = espiao[0]
    assert (imagem.media_type, imagem.dados_base64) == ("image/png", PNG)


def test_aceita_base64_com_tipo_separado(cliente, espiao):
    corpo = {"texto": "olha esse print", "imagem_base64": PNG, "imagem_media_type": "image/png"}
    assert cliente.post("/api/analisar", json=corpo).status_code == 200
    assert espiao[0][1].media_type == "image/png"


@pytest.mark.parametrize(
    ("corpo", "status"),
    [
        ({"imagem_base64": PNG}, 400),  # sem tipo
        ({"imagem_base64": "data:image/bmp;base64," + PNG}, 400),  # formato não aceito
        ({"imagem_base64": "isso não é base64!!", "imagem_media_type": "image/png"}, 400),
        ({"imagem_base64": PNG, "imagem_media_type": "image/jpeg"}, 400),  # bytes de PNG, diz JPEG
    ],
    ids=["sem-tipo", "bmp", "base64-invalido", "tipo-falso"],
)
def test_recusa_imagem_invalida(cliente, espiao, corpo, status):
    assert cliente.post("/api/analisar", json=corpo).status_code == status
    assert espiao == []  # nada chegou à análise


def test_recusa_imagem_grande(cliente, espiao, monkeypatch):
    monkeypatch.setattr(api, "MAX_IMAGEM_BYTES", 10)
    resposta = cliente.post("/api/analisar", json={"imagem_base64": PNG, "imagem_media_type": "image/png"})
    assert resposta.status_code == 413


# --- Limite da demo e token ------------------------------------------------------------


def test_limite_por_hora_por_ip(cliente, monkeypatch):
    monkeypatch.setenv("RADAR_LIMITE_DEMO", "2")
    ip_a = {"X-Forwarded-For": "1.1.1.1"}
    assert [cliente.post("/api/analisar", json={"texto": GOLPE}, headers=ip_a).status_code
            for _ in range(3)] == [200, 200, 429]
    outro_ip = {"X-Forwarded-For": "2.2.2.2, 10.0.0.1"}
    assert cliente.post("/api/analisar", json={"texto": GOLPE}, headers=outro_ip).status_code == 200


def test_pedido_invalido_nao_gasta_o_limite(cliente, monkeypatch):
    monkeypatch.setenv("RADAR_LIMITE_DEMO", "1")
    cliente.post("/api/analisar", json={"texto": ""})
    assert cliente.post("/api/analisar", json={"texto": GOLPE}).status_code == 200


def test_token_valido_nao_tem_limite(cliente, monkeypatch):
    monkeypatch.setenv("RADAR_LIMITE_DEMO", "1")
    monkeypatch.setenv("RADAR_TOKEN", "segredo-de-teste")
    cabecalho = {"X-Radar-Token": "segredo-de-teste"}
    for _ in range(3):
        assert cliente.post("/api/analisar", json={"texto": GOLPE}, headers=cabecalho).status_code == 200


@pytest.mark.parametrize("configurado", ["segredo-de-teste", ""])
def test_token_errado_da_401(cliente, monkeypatch, configurado):
    monkeypatch.setenv("RADAR_TOKEN", configurado)
    resposta = cliente.post("/api/analisar", json={"texto": GOLPE}, headers={"X-Radar-Token": "chute"})
    assert resposta.status_code == 401


def test_janela_de_uma_hora_libera_de_novo():
    limite = api.LimitePorIp()
    assert limite.permitir("ip", 1, agora=0)
    assert not limite.permitir("ip", 1, agora=3599)
    assert limite.permitir("ip", 1, agora=3600)


def test_pagina_de_demo(cliente):
    resposta = cliente.get("/")
    assert resposta.status_code == 200
    assert "text/html" in resposta.headers["content-type"]
    assert "Radar de Golpes" in resposta.text


def test_pagina_nao_usa_innerhtml():
    # Tudo que vem da API entra como texto: nada de innerHTML (evita injeção de HTML).
    assert "innerHTML" not in api.PAGINA.read_text(encoding="utf-8")


def test_erros_documentados_no_docs(cliente):
    respostas = cliente.get("/openapi.json").json()["paths"]["/api/analisar"]["post"]["responses"]
    assert {"400", "401", "413", "429", "502"} <= set(respostas)