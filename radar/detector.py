"""Detector: junta regras, prompt, provedor e validação numa chamada só.

analisar() nunca derruba quem chamou por causa do provedor: se a API falhar ou
a resposta vier fora do formato, o Resultado volta com "erro" preenchido.
"""

from __future__ import annotations

import os
import time
from dataclasses import asdict, dataclass, field
from typing import Any

from pydantic import ValidationError

from radar.modelos import MODELO_PADRAO, custo_usd, obter_modelo
from radar.prompts import VERSAO_PADRAO, carregar_prompt, montar_mensagem
from radar.provedores import ErroProvedor, Imagem, chamar_provedor
from radar.schema import Analise
from radar.sinais import Sinal, detectar_sinais, normalizar, resumo_para_prompt

MAX_CARACTERES = 6000
MAX_TENTATIVAS = 2  # a primeira + 1 nova tentativa se o formato vier inválido

SEM_TEXTO = "(Sem texto. Analise a imagem anexada.)"


@dataclass
class Meta:
    versao_prompt: str
    modelo: str
    latencia_s: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    custo_usd: float = 0.0
    tentativas: int = 0
    ancoragem: float | None = None  # % dos trechos citados que existem no texto
    erro: str | None = None


@dataclass
class Resultado:
    analise: Analise | None
    sinais_automaticos: list[Sinal] = field(default_factory=list)
    meta: Meta | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "analise": self.analise.model_dump() if self.analise else None,
            "sinais_automaticos": [asdict(s) for s in self.sinais_automaticos],
            "meta": asdict(self.meta) if self.meta else None,
        }


def _comparavel(texto: str) -> str:
    """Minúsculo, sem acento e com espaços simples, para comparar trechos."""
    return " ".join(normalizar(texto).split())


def calcular_ancoragem(analise: Analise, texto: str) -> float | None:
    """Fração (0 a 1) dos trechos citados que aparecem no texto. None se não citou nada."""
    if not analise.sinais:
        return None
    base = _comparavel(texto)
    encontrados = sum(1 for s in analise.sinais if _comparavel(s.trecho) in base)
    return round(encontrados / len(analise.sinais), 3)


def analisar(
    texto: str = "",
    imagem: Imagem | None = None,
    versao_prompt: str = VERSAO_PADRAO,
    modelo: str | None = None,
) -> Resultado:
    """Analisa um conteúdo e devolve o risco de golpe, os sinais e as medições."""
    texto = (texto or "").strip()[:MAX_CARACTERES]
    if not texto and imagem is None:
        raise ValueError("Envie um texto ou uma imagem para analisar.")

    modelo_id = modelo or os.environ.get("RADAR_MODELO") or MODELO_PADRAO
    info_modelo = obter_modelo(modelo_id)
    prompt = carregar_prompt(versao_prompt)

    sinais = detectar_sinais(texto)
    mensagem = montar_mensagem(prompt, texto or SEM_TEXTO, resumo_para_prompt(sinais))
    meta = Meta(versao_prompt=versao_prompt, modelo=modelo_id)
    analise: Analise | None = None

    inicio = time.perf_counter()
    for tentativa in range(1, MAX_TENTATIVAS + 1):
        meta.tentativas = tentativa
        try:
            resposta = chamar_provedor(info_modelo, prompt.system, mensagem, imagem)
        except ErroProvedor as erro:
            meta.erro = f"Falha no provedor: {erro}"
            break  # o SDK já repetiu; repetir de novo só gastaria cota
        meta.tokens_in += resposta.tokens_in
        meta.tokens_out += resposta.tokens_out
        try:
            analise = Analise.model_validate(resposta.dados)
            meta.erro = None
            break
        except ValidationError as erro:
            meta.erro = f"Resposta fora do formato ({erro.error_count()} problema(s))."
    meta.latencia_s = round(time.perf_counter() - inicio, 3)

    meta.custo_usd = round(custo_usd(info_modelo, meta.tokens_in, meta.tokens_out), 6)
    if analise is not None and imagem is None:
        meta.ancoragem = calcular_ancoragem(analise, texto)

    return Resultado(analise=analise, sinais_automaticos=sinais, meta=meta)