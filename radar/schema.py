"""Contrato de saída: o formato que TODO provedor de LLM precisa devolver.

O mesmo schema serve para validar a resposta (Pydantic) e para dizer ao modelo
qual formato usar (JSON Schema). As descrições dos campos também funcionam como
instrução para o modelo.
"""

from __future__ import annotations

import copy
from typing import Any, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field

# Nome da "ferramenta" que o modelo é obrigado a chamar (provedores com tool use).
NOME_FERRAMENTA = "registrar_analise"

NivelRisco = Literal["baixo", "medio", "alto"]
Peso = Literal["baixo", "medio", "alto"]
Confianca = Literal["baixa", "media", "alta"]

Categoria = Literal[
    "pagamento_antecipado",
    "comprovante_falso",
    "falso_intermediario",
    "phishing_link",
    "falso_parente_ou_conhecido",
    "falso_suporte_ou_banco",
    "falsa_venda_preco_baixo",
    "falso_aluguel_imovel",
    "falsa_vaga_emprego",
    "investimento_falso",
    "premio_ou_restituicao_falsa",
    "outro_golpe",
    "nenhum",
]
CATEGORIAS: tuple[str, ...] = get_args(Categoria)


class SinalEncontrado(BaseModel):
    """Um sinal de golpe que o modelo encontrou, com a prova."""

    model_config = ConfigDict(extra="forbid")

    sinal: str = Field(description="Nome curto do sinal, em português simples.")
    trecho: str = Field(
        description="Cópia EXATA de um trecho do conteúdo analisado, sem reescrever nem resumir."
    )
    peso: Peso = Field(description="Quanto este sinal pesa na suspeita de golpe.")


class Analise(BaseModel):
    """Resultado da análise de um conteúdo."""

    model_config = ConfigDict(extra="forbid")

    nivel_risco: NivelRisco = Field(description="Risco de ser golpe.")
    pontuacao: int = Field(
        ge=0,
        le=100,
        description="Risco de 0 a 100 (baixo ≈ 0–34, medio ≈ 35–69, alto ≈ 70–100).",
    )
    categoria: Categoria = Field(description="Tipo de golpe. Use 'nenhum' se for legítimo.")
    sinais: list[SinalEncontrado] = Field(
        description="Sinais encontrados. Lista vazia se não houver nenhum."
    )
    explicacao: str = Field(description="Explicação em 2 a 3 frases simples, para leigos.")
    recomendacao: str = Field(description="O que a pessoa deve fazer agora (ação prática).")
    confianca: Confianca = Field(description="Quão seguro o modelo está da própria análise.")


def json_schema(*, sem_limites: bool = False) -> dict[str, Any]:
    """JSON Schema da Analise no modo estrito, pronto para mandar ao provedor.

    - resolve as referências internas ($ref/$defs), colocando tudo no lugar;
    - remove os "title" que o Pydantic gera (só ocupam tokens);
    - em cada objeto: additionalProperties=false e todos os campos obrigatórios;
    - sem_limites=True remove minimum/maximum (alguns provedores não aceitam).
    """
    bruto = Analise.model_json_schema()
    definicoes = bruto.pop("$defs", {})

    def limpar(no: Any) -> Any:
        if isinstance(no, list):
            return [limpar(item) for item in no]
        if not isinstance(no, dict):
            return no
        if "$ref" in no:
            nome = no["$ref"].split("/")[-1]
            return limpar(copy.deepcopy(definicoes[nome]))

        limpo: dict[str, Any] = {}
        for chave, valor in no.items():
            if chave == "title":
                continue
            if sem_limites and chave in ("minimum", "maximum"):
                continue
            if chave == "properties":
                # Aqui as chaves são NOMES de campos, não palavras do schema.
                limpo[chave] = {nome: limpar(sub) for nome, sub in valor.items()}
            else:
                limpo[chave] = limpar(valor)

        if limpo.get("type") == "object":
            limpo["additionalProperties"] = False
            limpo["required"] = list(limpo.get("properties", {}))
        return limpo

    return limpar(bruto)