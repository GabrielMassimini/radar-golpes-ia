"""Confere o fluxo do bot exportado do n8n (n8n/radar-telegram-bot.json). Não usa API."""

import json
import re
from pathlib import Path

from radar.detector import MAX_CARACTERES

RAIZ = Path(__file__).resolve().parent.parent
ARQUIVO = RAIZ / "n8n" / "radar-telegram-bot.json"
TEXTO = ARQUIVO.read_text(encoding="utf-8")
FLUXO = json.loads(TEXTO)
NOS = {no["name"]: no for no in FLUXO["nodes"]}


def test_exportacao_nao_leva_segredos_nem_dados_de_teste():
    # Credenciais exportadas trazem só nome e id interno; o token fica no n8n.
    for no in FLUXO["nodes"]:
        for credencial in (no.get("credentials") or {}).values():
            assert set(credencial) <= {"id", "name"}
    assert not FLUXO.get("pinData")  # dados fixados teriam nome e chat da conversa de teste
    assert "instanceId" not in FLUXO.get("meta", {})
    assert not re.search(r"\d{8,10}:[\w-]{30,}", TEXTO)  # formato do token do Telegram
    assert "trycloudflare" not in TEXTO  # o endereço do túnel muda e não pertence ao fluxo


def test_fluxo_importado_comeca_desligado():
    assert FLUXO["active"] is False


def test_api_chamada_com_token_no_cabecalho_por_credencial():
    http = NOS["Analisar na API"]["parameters"]
    assert http["url"] == "https://radar-golpes-ia.vercel.app/api/analisar"
    assert http["genericAuthType"] == "httpHeaderAuth"
    assert "X-Radar-Token" not in TEXTO  # o nome do cabeçalho mora na credencial, não no fluxo


def test_falha_da_api_tem_resposta_para_o_usuario():
    assert NOS["Analisar na API"].get("onError") == "continueErrorOutput"
    saidas = FLUXO["connections"]["Analisar na API"]["main"]
    assert saidas[1][0]["node"] == "Aviso de falha"


def test_texto_enviado_respeita_o_limite_da_api():
    for nome in ("Preparar texto", "Preparar print"):
        assert f".slice(0, {MAX_CARACTERES})" in NOS[nome]["parameters"]["jsCode"]