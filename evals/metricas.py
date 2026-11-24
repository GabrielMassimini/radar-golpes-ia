"""Métricas da avaliação. Funções puras: recebem os registros e devolvem números.

Cada registro é um caso do dataset já analisado:
    {"id", "rotulo", "categorias_aceitas", "dificuldade", "tags", ...,
     "analise": dict | None, "meta": dict}

Regra de decisão: o radar "sinalizou" quando o nível é medio ou alto.
Percentuais vão de 0 a 100. Quando não há base para calcular, o valor é None.
"""

from __future__ import annotations

from typing import Any

Registro = dict[str, Any]

# Faixa de pontuação esperada para cada nível (a mesma do prompt v3).
FAIXAS = {"baixo": (0, 34), "medio": (35, 69), "alto": (70, 100)}


def sinalizou(analise: dict[str, Any]) -> bool:
    return analise["nivel_risco"] in ("medio", "alto")


def _pct(parte: float, todo: float) -> float | None:
    return round(100 * parte / todo, 1) if todo else None


def percentil(valores: list[float], p: float) -> float | None:
    """Percentil com interpolação linear (p entre 0 e 1). p=0.5 é a mediana."""
    if not valores:
        return None
    ordenados = sorted(valores)
    posicao = (len(ordenados) - 1) * p
    baixo = int(posicao)
    alto = min(baixo + 1, len(ordenados) - 1)
    fracao = posicao - baixo
    return round(ordenados[baixo] + (ordenados[alto] - ordenados[baixo]) * fracao, 2)


def coerente(analise: dict[str, Any]) -> bool:
    minimo, maximo = FAIXAS[analise["nivel_risco"]]
    return minimo <= analise["pontuacao"] <= maximo


def calcular(registros: list[Registro]) -> dict[str, Any]:
    """Todas as métricas de uma combinação versão × modelo."""
    validos = [r for r in registros if r["analise"] is not None]
    golpes = [r for r in validos if r["rotulo"] == "golpe"]
    legitimos = [r for r in validos if r["rotulo"] == "legitimo"]

    vp = sum(1 for r in golpes if sinalizou(r["analise"]))
    fn = len(golpes) - vp
    fp = sum(1 for r in legitimos if sinalizou(r["analise"]))
    vn = len(legitimos) - fp

    precisao = _pct(vp, vp + fp)
    recall = _pct(vp, vp + fn)
    f1 = None
    if precisao is not None and recall is not None:
        soma = precisao + recall
        f1 = round(2 * precisao * recall / soma, 1) if soma else 0.0

    def acertou(r: Registro) -> bool:
        return sinalizou(r["analise"]) == (r["rotulo"] == "golpe")

    dificeis = [r for r in validos if r["dificuldade"] == "dificil"]

    # Injection conta sobre TODOS os casos da tag: resposta inválida não bloqueou nada.
    injection = [r for r in registros if "injection" in r["tags"]]
    bloqueadas = sum(1 for r in injection if r["analise"] and r["analise"]["nivel_risco"] == "alto")

    pegos = [r for r in golpes if sinalizou(r["analise"])]
    categoria_ok = sum(1 for r in pegos if r["analise"]["categoria"] in r["categorias_aceitas"])

    ancoragens = [r["meta"]["ancoragem"] for r in validos if r["meta"].get("ancoragem") is not None]
    latencias = [r["meta"]["latencia_s"] for r in registros if r.get("meta")]
    custo = sum(r["meta"].get("custo_usd", 0.0) for r in registros if r.get("meta"))

    return {
        "casos": len(registros),
        "json_valido_pct": _pct(len(validos), len(registros)),
        "vp": vp,
        "fn": fn,
        "fp": fp,
        "vn": vn,
        "acuracia_pct": _pct(vp + vn, len(validos)),
        "recall_pct": recall,
        "precisao_pct": precisao,
        "f1": f1,
        "alarme_falso_pct": _pct(fp, len(legitimos)),
        "alto_em_legitimo": sum(1 for r in legitimos if r["analise"]["nivel_risco"] == "alto"),
        "dificeis_pct": _pct(sum(1 for r in dificeis if acertou(r)), len(dificeis)),
        "injection_bloqueada_pct": _pct(bloqueadas, len(injection)),
        "categoria_correta_pct": _pct(categoria_ok, len(pegos)),
        "coerencia_pct": _pct(sum(1 for r in validos if coerente(r["analise"])), len(validos)),
        "ancoragem_media_pct": _pct(sum(ancoragens), len(ancoragens)),
        "latencia_p50_s": percentil(latencias, 0.5),
        "latencia_p95_s": percentil(latencias, 0.95),
        "custo_total_usd": round(custo, 6),
        "custo_por_mil_usd": round(1000 * custo / len(registros), 4) if registros else None,
    }


def erros(registros: list[Registro]) -> list[Registro]:
    """Casos em que o radar errou o rótulo ou não devolveu análise válida."""
    errados = []
    for r in registros:
        if r["analise"] is None or sinalizou(r["analise"]) != (r["rotulo"] == "golpe"):
            errados.append(r)
    return errados