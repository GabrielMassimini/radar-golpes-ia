"""Testes do run_eval (evals/run_eval.py). Só o mock: não usam API nenhuma."""

import json

import pytest

import evals.run_eval as run_eval
from evals.run_eval import Ritmo, avaliar_caso, carregar_dataset, executar, filtrar
from radar.detector import Meta, Resultado

CASOS = carregar_dataset()


def test_dataset_carrega_os_61_casos():
    assert len(CASOS) == 61


@pytest.mark.parametrize(("tag", "esperado"), [("injection", 3), ("dificil", 20), ("email", 5)])
def test_filtro_aceita_tag_dificuldade_e_canal(tag, esperado):
    assert len(filtrar(CASOS, tag)) == esperado


def test_limite():
    assert [c["id"] for c in filtrar(CASOS, limite=2)] == ["c001", "c002"]


def test_ritmo_espaca_as_chamadas(monkeypatch):
    agora = [100.0]
    esperas = []

    def dormir(segundos):
        esperas.append(round(segundos, 2))
        agora[0] += segundos

    monkeypatch.setattr(run_eval, "relogio", lambda: agora[0])
    monkeypatch.setattr(run_eval, "dormir", dormir)
    ritmo = Ritmo(rpm=12)  # 1 a cada 5 s
    for _ in range(3):
        ritmo.esperar()
    assert esperas == [5.0, 5.0]  # a primeira não espera


def test_ritmo_sem_limite_nao_espera(monkeypatch):
    monkeypatch.setattr(run_eval, "dormir", lambda s: pytest.fail("não devia esperar"))
    Ritmo(rpm=None).esperar()


def test_erro_429_espera_e_tenta_de_novo(monkeypatch):
    respostas = iter(["Limite de uso atingido (HTTP 429).", None])
    esperas = []

    def falso_analisar(texto, versao_prompt, modelo):
        return Resultado(analise=None, meta=Meta(versao_prompt, modelo, erro=next(respostas)))

    monkeypatch.setattr(run_eval, "analisar", falso_analisar)
    monkeypatch.setattr(run_eval, "dormir", esperas.append)
    registro = avaliar_caso(CASOS[0], "v3", "gemini-3.5-flash-lite", Ritmo(None))
    assert esperas == [run_eval.ESPERA_429_S]
    assert registro["meta"]["erro"] is None


def test_execucao_completa_com_regras(tmp_path, capsys):
    pasta = executar(["v3"], ["regras"], limite=5, pasta_saida=tmp_path)
    assert {p.name for p in pasta.iterdir()} == {"v3__regras.jsonl", "resumo.json", "relatorio.md"}

    registros = [json.loads(l) for l in (pasta / "v3__regras.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [r["id"] for r in registros] == ["c001", "c002", "c003", "c004", "c005"]  # ordem mantida
    assert all(r["analise"] for r in registros)

    resumo = json.loads((pasta / "resumo.json").read_text(encoding="utf-8"))
    assert resumo["v3__regras"]["todos"]["casos"] == 5
    assert "sem_parecidos" in resumo["v3__regras"]  # c002 tem a tag de vazamento

    relatorio = (pasta / "relatorio.md").read_text(encoding="utf-8")
    assert "| v3__regras | 5 |" in relatorio
    assert "Sem os casos parecidos" in relatorio
    assert "....." in capsys.readouterr().out  # progresso: um ponto por caso


def test_regras_nao_anunciam_chamadas_de_api(tmp_path, capsys):
    executar(["v3"], ["regras"], limite=1, pasta_saida=tmp_path)
    assert "chamadas de API" not in capsys.readouterr().out


def test_dataset_dificil_tem_relatorio_proprio(tmp_path):
    pasta = executar(["v3"], ["regras"], limite=2, pasta_saida=tmp_path, dataset="dificil")
    relatorio = (pasta / "relatorio.md").read_text(encoding="utf-8")
    assert "Dataset: **dificil**" in relatorio
    assert "| v3__regras | 2 |" in relatorio