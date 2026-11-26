"""Confere a configuração de deploy (pyproject.toml, vercel.json). Não usa API."""

import json
import tomllib
from pathlib import Path

import radar.provedores as provedores

RAIZ = Path(__file__).resolve().parent.parent


def test_dependencias_iguais_no_requirements_e_no_pyproject():
    # A Vercel instala pelo pyproject.toml; localmente usamos o requirements.txt.
    requirements = (RAIZ / "requirements.txt").read_text(encoding="utf-8").split()
    pyproject = tomllib.loads((RAIZ / "pyproject.toml").read_text(encoding="utf-8"))
    assert sorted(pyproject["project"]["dependencies"]) == sorted(requirements)


def test_dependencias_com_versao_exata():
    requirements = (RAIZ / "requirements.txt").read_text(encoding="utf-8").split()
    assert all("==" in linha for linha in requirements)


def test_vercel_aponta_para_a_api_com_60_segundos():
    pyproject = tomllib.loads((RAIZ / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["tool"]["vercel"]["entrypoint"] == "api.index:app"
    config = json.loads((RAIZ / "vercel.json").read_text(encoding="utf-8"))
    assert config["functions"]["api/index.py"]["maxDuration"] == 60


def test_vercelignore_nao_publica_testes_nem_segredos():
    ignorados = (RAIZ / ".vercelignore").read_text(encoding="utf-8").split()
    assert {"evals/", "tests/", ".env"} <= set(ignorados)


def test_na_vercel_a_chamada_cabe_no_tempo_da_funcao(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    tempo, tentativas = provedores._limites()
    assert tempo * (tentativas + 1) < 60


def test_fora_da_vercel_usa_os_limites_normais(monkeypatch):
    monkeypatch.delenv("VERCEL", raising=False)
    assert provedores._limites() == (provedores.TIMEOUT_S, provedores.TENTATIVAS_SDK)