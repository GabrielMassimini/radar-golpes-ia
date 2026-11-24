"""Testes das métricas (evals/metricas.py) com registros pequenos feitos à mão."""

import pytest

from evals.metricas import calcular, coerente, erros, percentil, sinalizou


def _registro(rotulo, nivel=None, pontuacao=None, categoria="nenhum", dificuldade="facil",
              tags=(), aceitas=None, ancoragem=1.0, latencia=1.0, custo=0.001):
    analise = None
    if nivel is not None:
        if pontuacao is None:
            pontuacao = {"baixo": 10, "medio": 50, "alto": 90}[nivel]
        analise = {"nivel_risco": nivel, "pontuacao": pontuacao, "categoria": categoria}
    if aceitas is None:
        aceitas = ["nenhum"] if rotulo == "legitimo" else ["phishing_link"]
    return {
        "id": "x",
        "rotulo": rotulo,
        "categorias_aceitas": aceitas,
        "dificuldade": dificuldade,
        "tags": list(tags),
        "analise": analise,
        "meta": {"ancoragem": ancoragem, "latencia_s": latencia, "custo_usd": custo},
    }


# Cenário base: 4 golpes (3 pegos, 1 perdido) e 4 legítimos (1 alarme falso).
CENARIO = [
    _registro("golpe", "alto", categoria="phishing_link"),
    _registro("golpe", "alto", categoria="outro_golpe"),  # pego, mas categoria errada
    _registro("golpe", "medio", categoria="phishing_link"),
    _registro("golpe", "baixo", dificuldade="dificil"),  # deixou passar
    _registro("legitimo", "baixo"),
    _registro("legitimo", "baixo", dificuldade="dificil"),
    _registro("legitimo", "baixo"),
    _registro("legitimo", "alto", dificuldade="dificil"),  # alarme falso grave
]


def test_sinalizou_e_medio_ou_alto():
    assert [sinalizou({"nivel_risco": n}) for n in ("baixo", "medio", "alto")] == [False, True, True]


def test_matriz_de_confusao():
    m = calcular(CENARIO)
    assert (m["vp"], m["fn"], m["fp"], m["vn"]) == (3, 1, 1, 3)


def test_recall_alarme_falso_precisao_e_f1():
    m = calcular(CENARIO)
    assert m["recall_pct"] == 75.0  # 3 de 4 golpes
    assert m["alarme_falso_pct"] == 25.0  # 1 de 4 legítimos
    assert m["precisao_pct"] == 75.0  # 3 de 4 sinalizados
    assert m["f1"] == 75.0
    assert m["acuracia_pct"] == 75.0


def test_alto_em_legitimo_conta_so_o_erro_grave():
    cenario = CENARIO + [_registro("legitimo", "medio")]  # medio em legítimo não conta
    assert calcular(cenario)["alto_em_legitimo"] == 1


def test_dificeis_e_categoria():
    m = calcular(CENARIO)
    assert m["dificeis_pct"] == pytest.approx(33.3)  # acertou 1 de 3 difíceis
    assert m["categoria_correta_pct"] == pytest.approx(66.7)  # 2 de 3 golpes pegos


def test_resposta_invalida_sai_das_contas_mas_aparece_no_json_valido():
    m = calcular(CENARIO + [_registro("golpe")])  # sem análise
    assert m["json_valido_pct"] == pytest.approx(88.9)
    assert m["recall_pct"] == 75.0


def test_injection_so_conta_alto_e_invalida_nao_bloqueia():
    casos = [
        _registro("golpe", "alto", tags=["injection"]),
        _registro("golpe", "medio", tags=["injection"]),  # sinalizou, mas não bloqueou
        _registro("golpe", tags=["injection"]),  # sem análise
    ]
    assert calcular(casos)["injection_bloqueada_pct"] == pytest.approx(33.3)


def test_sem_casos_de_injection_fica_none():
    assert calcular(CENARIO)["injection_bloqueada_pct"] is None


@pytest.mark.parametrize(
    ("nivel", "pontuacao", "esperado"),
    [("baixo", 34, True), ("baixo", 35, False), ("medio", 69, True), ("alto", 65, False), ("alto", 70, True)],
)
def test_coerencia_nivel_e_pontuacao(nivel, pontuacao, esperado):
    assert coerente({"nivel_risco": nivel, "pontuacao": pontuacao}) is esperado


def test_ancoragem_ignora_casos_sem_trecho():
    casos = [_registro("golpe", "alto", ancoragem=1.0), _registro("golpe", "alto", ancoragem=0.5),
             _registro("legitimo", "baixo", ancoragem=None)]
    assert calcular(casos)["ancoragem_media_pct"] == 75.0


def test_percentis():
    valores = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    assert percentil(valores, 0.5) == 5.5
    assert percentil(valores, 0.95) == pytest.approx(9.55)
    assert percentil([], 0.5) is None


def test_custo_total_e_por_mil():
    m = calcular(CENARIO)
    assert m["custo_total_usd"] == pytest.approx(0.008)
    assert m["custo_por_mil_usd"] == pytest.approx(1.0)


def test_sem_registros_nao_quebra():
    m = calcular([])
    assert m["casos"] == 0 and m["recall_pct"] is None and m["custo_por_mil_usd"] is None


def test_erros_lista_os_que_erraram_e_os_invalidos():
    cenario = CENARIO + [_registro("golpe")]
    assert len(erros(cenario)) == 3  # golpe perdido, alarme falso e o inválido