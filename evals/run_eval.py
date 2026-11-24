"""Roda o dataset em cada combinação versão × modelo e gera o relatório.

    python -m evals.run_eval --versoes v1,v2,v3 --modelos gemini-3.5-flash-lite
    python -m evals.run_eval --versoes v3 --modelos regras        # baseline, sem API
    python -m evals.run_eval --tag injection                      # só um grupo de casos
    python -m evals.run_eval --dataset dificil                    # conjunto difícil, relatado à parte

Os resultados brutos vão para evals/resultados/<data-hora>/ (fora do Git):
um .jsonl por combinação, resumo.json e relatorio.md.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any

from evals.metricas import calcular, erros
from radar import analisar
from radar.modelos import MODELO_PADRAO, obter_modelo
from radar.prompts import VERSAO_PADRAO

PASTA = Path(__file__).resolve().parent
DATASETS = {"principal": PASTA / "dataset.jsonl", "dificil": PASTA / "dataset_dificil.jsonl"}
DATASET = DATASETS["principal"]
PASTA_RESULTADOS = PASTA / "resultados"

RPM_PADRAO = 14  # um a menos que o limite grátis (15), por margem
ESPERA_429_S = 60  # o limite por minuto zera em até 1 minuto
TENTATIVAS_429 = 3
TAG_VAZAMENTO = "parecido_com_exemplo"

# Trocáveis nos testes, para não esperar de verdade.
dormir = time.sleep
relogio = time.monotonic


class Ritmo:
    """Garante um intervalo mínimo entre o INÍCIO de chamadas, mesmo em paralelo."""

    def __init__(self, rpm: float | None):
        self.intervalo = 60 / rpm if rpm else 0.0
        self.proxima = 0.0
        self.trava = threading.Lock()

    def esperar(self) -> None:
        if not self.intervalo:
            return
        with self.trava:
            agora = relogio()
            if agora < self.proxima:
                dormir(self.proxima - agora)
                agora = self.proxima
            self.proxima = agora + self.intervalo


def carregar_dataset(arquivo: Path = DATASET) -> list[dict[str, Any]]:
    linhas = arquivo.read_text(encoding="utf-8").splitlines()
    return [json.loads(linha) for linha in linhas if linha.strip()]


def filtrar(casos: list[dict[str, Any]], tag: str | None = None, limite: int | None = None):
    """--tag aceita uma tag, uma dificuldade ou um canal."""
    if tag:
        casos = [c for c in casos if tag in c["tags"] or tag in (c["dificuldade"], c["canal"])]
    return casos[:limite] if limite else casos


def avaliar_caso(caso: dict[str, Any], versao: str, modelo: str, ritmo: Ritmo) -> dict[str, Any]:
    """Analisa um caso. No erro 429 espera o limite zerar e tenta de novo."""
    for tentativa in range(1, TENTATIVAS_429 + 1):
        ritmo.esperar()
        resultado = analisar(caso["texto"], versao_prompt=versao, modelo=modelo).to_dict()
        erro = resultado["meta"]["erro"] or ""
        if "429" not in erro or tentativa == TENTATIVAS_429:
            break
        dormir(ESPERA_429_S)
    return {
        **caso,
        "versao": versao,
        "modelo": modelo,
        "analise": resultado["analise"],
        "sinais_automaticos": [s["id"] for s in resultado["sinais_automaticos"]],
        "meta": resultado["meta"],
    }


def rodar_combinacao(casos, versao: str, modelo: str, ritmo: Ritmo, paralelo: int) -> list[dict[str, Any]]:
    print(f"{versao} × {modelo}: ", end="", flush=True)

    def um(caso):
        registro = avaliar_caso(caso, versao, modelo, ritmo)
        print("." if registro["analise"] else "x", end="", flush=True)
        return registro

    with ThreadPoolExecutor(max_workers=paralelo) as executor:
        registros = list(executor.map(um, casos))  # map mantém a ordem do dataset
    print()
    return registros


def _nome(versao: str, modelo: str) -> str:
    return f"{versao}__{modelo.replace(':', '-')}"


def resumir(registros: list[dict[str, Any]]) -> dict[str, Any]:
    resumo = {"todos": calcular(registros)}
    if any(TAG_VAZAMENTO in r["tags"] for r in registros):
        resumo["sem_parecidos"] = calcular([r for r in registros if TAG_VAZAMENTO not in r["tags"]])
    return resumo


# --- Relatório ----------------------------------------------------------------


def _pct(valor) -> str:
    return "-" if valor is None else f"{valor:.1f}%"


def _num(valor, casas: int = 2) -> str:
    return "-" if valor is None else f"{valor:.{casas}f}"


def _celula(texto: Any, maximo: int) -> str:
    texto = " ".join(str(texto or "").split()).replace("|", "/")
    return texto if len(texto) <= maximo else texto[: maximo - 1] + "…"


def montar_relatorio(resultados: dict[str, dict[str, Any]], data: str, dataset: str = "principal") -> str:
    """resultados: {nome da combinação: {"registros": [...], "resumo": {...}}}."""
    linhas = [
        "# Relatório de avaliação",
        "",
        f"Dataset: **{dataset}**. Gerado em {data}. \"Sinalizado\" = nível medio ou alto. Percentuais sobre as respostas válidas, "
        "exceto JSON válido e injection (sobre todos os casos).",
        "",
        "## Resumo",
        "",
        "| Combinação | Casos | JSON válido | Acurácia | Recall | Alarme falso | Alto em legítimo "
        "| Difíceis | Injection | Categoria | Coerência | Ancoragem | p50 (s) | p95 (s) | US$/1.000 |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for nome, dados in resultados.items():
        m = dados["resumo"]["todos"]
        linhas.append(
            f"| {nome} | {m['casos']} | {_pct(m['json_valido_pct'])} | {_pct(m['acuracia_pct'])} "
            f"| {_pct(m['recall_pct'])} | {_pct(m['alarme_falso_pct'])} | {m['alto_em_legitimo']} "
            f"| {_pct(m['dificeis_pct'])} | {_pct(m['injection_bloqueada_pct'])} "
            f"| {_pct(m['categoria_correta_pct'])} | {_pct(m['coerencia_pct'])} "
            f"| {_pct(m['ancoragem_media_pct'])} | {_num(m['latencia_p50_s'])} | {_num(m['latencia_p95_s'])} "
            f"| {_num(m['custo_por_mil_usd'], 4)} |"
        )

    com_vazamento = {n: d for n, d in resultados.items() if "sem_parecidos" in d["resumo"]}
    if com_vazamento:
        linhas += [
            "",
            "## Sem os casos parecidos com os exemplos do prompt",
            "",
            f"Os casos com a tag `{TAG_VAZAMENTO}` são quase cópias dos exemplos que o v3 traz no prompt. "
            "Se a diferença for grande, o v3 estava acertando por ter visto a resposta.",
            "",
            "| Combinação | Casos | Acurácia | Recall | Alarme falso | Difíceis |",
            "|---|---|---|---|---|---|",
        ]
        for nome, dados in com_vazamento.items():
            m = dados["resumo"]["sem_parecidos"]
            linhas.append(
                f"| {nome} | {m['casos']} | {_pct(m['acuracia_pct'])} | {_pct(m['recall_pct'])} "
                f"| {_pct(m['alarme_falso_pct'])} | {_pct(m['dificeis_pct'])} |"
            )

    for nome, dados in resultados.items():
        m = dados["resumo"]["todos"]
        linhas += [
            "",
            f"## {nome}",
            "",
            "| | Sinalizou | Não sinalizou |",
            "|---|---|---|",
            f"| **Golpe** | {m['vp']} | {m['fn']} |",
            f"| **Legítimo** | {m['fp']} | {m['vn']} |",
            "",
        ]
        errados = erros(dados["registros"])
        if not errados:
            linhas.append("Nenhum erro.")
            continue
        linhas += [
            "| Caso | Rótulo | Previsto | Dificuldade | Texto | Explicação do modelo |",
            "|---|---|---|---|---|---|",
        ]
        for r in errados:
            a = r["analise"]
            previsto = f"{a['nivel_risco']} ({a['pontuacao']})" if a else f"erro: {r['meta']['erro']}"
            explicacao = a["explicacao"] if a else ""
            linhas.append(
                f"| {r['id']} | {r['rotulo']} | {_celula(previsto, 60)} | {r['dificuldade']} "
                f"| {_celula(r['texto'], 110)} | {_celula(explicacao, 160)} |"
            )
    return "\n".join(linhas)


# --- Execução -------------------------------------------------------------------


def executar(
    versoes: list[str],
    modelos: list[str],
    paralelo: int = 2,
    limite: int | None = None,
    tag: str | None = None,
    rpm: float = RPM_PADRAO,
    pasta_saida: Path | None = None,
    dataset: str = "principal",
) -> Path:
    casos = filtrar(carregar_dataset(DATASETS[dataset]), tag, limite)
    if not casos:
        raise SystemExit("Nenhum caso para rodar com esse filtro.")

    agora = datetime.now()
    pasta = pasta_saida or PASTA_RESULTADOS / f"{agora:%Y-%m-%d_%H%M%S}_{dataset}"
    pasta.mkdir(parents=True, exist_ok=True)

    chamadas = sum(len(casos) for m in modelos if obter_modelo(m).provedor != "mock") * len(versoes)
    if chamadas:
        print(f"{chamadas} chamadas de API, no mínimo ~{chamadas * 60 / rpm / 60:.0f} min no ritmo de {rpm:g}/min.")

    resultados: dict[str, dict[str, Any]] = {}
    for modelo in modelos:
        usa_api = obter_modelo(modelo).provedor != "mock"
        ritmo = Ritmo(rpm if usa_api else None)  # um ritmo por modelo: a cota é por modelo
        for versao in versoes:
            registros = rodar_combinacao(casos, versao, modelo, ritmo, paralelo)
            nome = _nome(versao, modelo)
            linhas = [json.dumps(r, ensure_ascii=False) for r in registros]
            (pasta / f"{nome}.jsonl").write_text("\n".join(linhas), encoding="utf-8")
            resultados[nome] = {"registros": registros, "resumo": resumir(registros)}

    resumo = {nome: dados["resumo"] for nome, dados in resultados.items()}
    (pasta / "resumo.json").write_text(json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8")
    relatorio = montar_relatorio(resultados, agora.strftime("%d/%m/%Y %H:%M"), dataset)
    (pasta / "relatorio.md").write_text(relatorio, encoding="utf-8")
    return pasta


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m evals.run_eval")
    parser.add_argument("--versoes", default=VERSAO_PADRAO, help="ex.: v1,v2,v3")
    parser.add_argument("--modelos", default=MODELO_PADRAO, help="ex.: regras,gemini-3.5-flash-lite")
    parser.add_argument("--paralelo", type=int, default=2, help="chamadas ao mesmo tempo (padrão 2)")
    parser.add_argument("--limite", type=int, help="roda só os N primeiros casos")
    parser.add_argument("--tag", help="filtra por tag, dificuldade ou canal")
    parser.add_argument("--rpm", type=float, default=RPM_PADRAO, help="chamadas por minuto (padrão 14)")
    parser.add_argument("--dataset", choices=sorted(DATASETS), default="principal")
    args = parser.parse_args()

    sys.stdout.reconfigure(encoding="utf-8")
    pasta = executar(
        versoes=[v.strip() for v in args.versoes.split(",") if v.strip()],
        modelos=[m.strip() for m in args.modelos.split(",") if m.strip()],
        paralelo=args.paralelo,
        limite=args.limite,
        tag=args.tag,
        rpm=args.rpm,
        dataset=args.dataset,
    )
    print(f"Relatório: {pasta / 'relatorio.md'}")


if __name__ == "__main__":
    main()