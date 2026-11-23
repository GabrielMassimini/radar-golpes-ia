"""Provedores: quem responde à análise. Todos têm a mesma entrada e a mesma saída.

Entrada: system, mensagem e (opcional) uma imagem.
Saída: RespostaBruta com os dados no formato do schema e a contagem de tokens.
Quem valida os dados é o detector, não o provedor.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any

import openai
from openai import OpenAI

from radar.modelos import Modelo
from radar.schema import NOME_FERRAMENTA, json_schema
from radar.sinais import detectar_sinais


class ErroProvedor(Exception):
    """Falha ao falar com o provedor (rede, limite, chave). Cada provedor
    converte os erros do próprio SDK neste tipo, e o detector trata só ele."""


@dataclass(frozen=True)
class Imagem:
    media_type: str  # ex.: "image/png"
    dados_base64: str


@dataclass(frozen=True)
class RespostaBruta:
    dados: dict[str, Any]
    tokens_in: int
    tokens_out: int


def chamar_provedor(
    modelo: Modelo, system: str, mensagem: str, imagem: Imagem | None = None
) -> RespostaBruta:
    """Envia a análise para o provedor do modelo e devolve a resposta sem validar."""
    if modelo.provedor == "mock":
        return _chamar_mock(mensagem)
    if modelo.provedor in ("gemini", "openai"):
        return _chamar_compativel_openai(modelo, system, mensagem, imagem)
    if modelo.provedor == "anthropic":
        return _chamar_claude(modelo, system, mensagem, imagem)
    raise NotImplementedError(f"Provedor '{modelo.provedor}' ainda não foi implementado.")


# --- Gemini e OpenAI: mesmo SDK (openai), endereços diferentes -------------

# Endpoint do Gemini que entende o formato da OpenAI: aistudio.google.com/docs/openai
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

# Teto de saída. No Gemini o raciocínio interno também conta aqui.
MAX_TOKENS_SAIDA = 2048

# Raciocínio do Gemini 3.x não pode ser desligado; "low" gasta menos cota e tempo.
ESFORCO_GEMINI = "low"

TIMEOUT_S = 30
TENTATIVAS_SDK = 3  # o SDK repete sozinho em 429, 5xx e falha de conexão


def _cliente(provedor: str) -> OpenAI:
    if provedor == "gemini":
        variavel, base_url = "GEMINI_API_KEY", GEMINI_BASE_URL
    else:
        variavel, base_url = "OPENAI_API_KEY", None  # None: o SDK usa o padrão da OpenAI
    chave = os.environ.get(variavel)
    if not chave:
        raise ErroProvedor(f"Falta a chave {variavel} no .env.")
    return OpenAI(api_key=chave, base_url=base_url, timeout=TIMEOUT_S, max_retries=TENTATIVAS_SDK)


def _mensagens(system: str, mensagem: str, imagem: Imagem | None) -> list[dict[str, Any]]:
    if imagem is None:
        conteudo: Any = mensagem
    else:
        url = f"data:{imagem.media_type};base64,{imagem.dados_base64}"
        conteudo = [
            {"type": "text", "text": mensagem},
            {"type": "image_url", "image_url": {"url": url}},
        ]
    return [{"role": "system", "content": system}, {"role": "user", "content": conteudo}]


def _formato_resposta() -> dict[str, Any]:
    """Saída estruturada: o modelo só consegue responder JSON neste schema."""
    return {
        "type": "json_schema",
        "json_schema": {"name": NOME_FERRAMENTA, "strict": True, "schema": json_schema()},
    }


def _ler_json(texto: str | None) -> dict[str, Any]:
    """JSON quebrado vira {}: o detector acusa "fora do formato" e tenta de novo."""
    try:
        dados = json.loads(texto or "")
    except json.JSONDecodeError:
        return {}
    return dados if isinstance(dados, dict) else {}


def _tokens(uso: Any) -> tuple[int, int]:
    """(entrada, saída). Pelo total, para incluir o raciocínio, que é cobrado como saída."""
    if uso is None:
        return 0, 0
    entrada = uso.prompt_tokens or 0
    saida = max(uso.completion_tokens or 0, (uso.total_tokens or 0) - entrada)
    return entrada, saida


def _descrever_erro(erro: Exception, conexao: bool) -> str:
    """Mensagem curta e segura: nunca repete o corpo da resposta nem a chave."""
    if conexao:
        return "Sem conexão com o provedor (rede ou tempo esgotado)."
    status = getattr(erro, "status_code", None)
    if status == 429:
        return "Limite de uso atingido (HTTP 429). Espere um pouco e tente de novo."
    if status in (401, 403):
        return f"Chave recusada (HTTP {status}). Confira a chave no .env."
    if status is not None:
        return f"O provedor respondeu com erro (HTTP {status})."
    return f"Erro do provedor ({type(erro).__name__})."


def _chamar_compativel_openai(
    modelo: Modelo, system: str, mensagem: str, imagem: Imagem | None
) -> RespostaBruta:
    cliente = _cliente(modelo.provedor)
    extras: dict[str, Any] = {}
    if modelo.provedor == "gemini":
        extras["reasoning_effort"] = ESFORCO_GEMINI
    try:
        resposta = cliente.chat.completions.create(
            model=modelo.nome_api,
            messages=_mensagens(system, mensagem, imagem),
            response_format=_formato_resposta(),
            max_completion_tokens=MAX_TOKENS_SAIDA,
            **extras,
        )
    except openai.APIError as erro:
        conexao = isinstance(erro, openai.APIConnectionError)
        raise ErroProvedor(_descrever_erro(erro, conexao)) from erro

    escolha = resposta.choices[0]
    if escolha.finish_reason == "length":
        raise ErroProvedor(f"A resposta passou de {MAX_TOKENS_SAIDA} tokens e veio cortada.")
    entrada, saida = _tokens(resposta.usage)
    return RespostaBruta(_ler_json(escolha.message.content), entrada, saida)


# --- Claude (Anthropic): opcional --------------------------------------------

# O SDK da Anthropic é importado só aqui dentro: ele leva alguns segundos para
# carregar e atrasaria toda chamada da API, mesmo quando o modelo é o Gemini.

# Mesma escolha do Gemini: pensar pouco, porque a tarefa é curta.
ESFORCO_CLAUDE = "low"


def _cliente_anthropic() -> Any:
    import anthropic

    chave = os.environ.get("ANTHROPIC_API_KEY")
    if not chave:
        raise ErroProvedor("Falta a chave ANTHROPIC_API_KEY no .env.")
    return anthropic.Anthropic(api_key=chave, timeout=TIMEOUT_S, max_retries=TENTATIVAS_SDK)


def _mensagens_claude(mensagem: str, imagem: Imagem | None) -> list[dict[str, Any]]:
    if imagem is None:
        conteudo: Any = mensagem
    else:
        fonte = {"type": "base64", "media_type": imagem.media_type, "data": imagem.dados_base64}
        conteudo = [{"type": "image", "source": fonte}, {"type": "text", "text": mensagem}]
    return [{"role": "user", "content": conteudo}]


def _chamar_claude(
    modelo: Modelo, system: str, mensagem: str, imagem: Imagem | None
) -> RespostaBruta:
    """Saída estruturada via output_config.format (o tool_choice forçado dá erro 400
    no Sonnet/Opus 5.5). Sem temperature: os modelos atuais recusam o parâmetro."""
    import anthropic

    cliente = _cliente_anthropic()
    try:
        resposta = cliente.messages.create(
            model=modelo.nome_api,
            max_tokens=MAX_TOKENS_SAIDA,
            system=system,
            messages=_mensagens_claude(mensagem, imagem),
            output_config={
                "effort": ESFORCO_CLAUDE,
                # Sem minimum/maximum: o Claude não aceita; o Pydantic confere depois.
                "format": {"type": "json_schema", "schema": json_schema(sem_limites=True)},
            },
        )
    except anthropic.APIError as erro:
        conexao = isinstance(erro, anthropic.APIConnectionError)
        raise ErroProvedor(_descrever_erro(erro, conexao)) from erro

    if resposta.stop_reason == "max_tokens":
        raise ErroProvedor(f"A resposta passou de {MAX_TOKENS_SAIDA} tokens e veio cortada.")
    if resposta.stop_reason == "refusal":
        raise ErroProvedor("O modelo recusou analisar este conteúdo.")
    texto = "".join(bloco.text for bloco in resposta.content if bloco.type == "text")
    uso = resposta.usage
    return RespostaBruta(_ler_json(texto), uso.input_tokens, uso.output_tokens)


# --- Mock: só regras, sem IA ----------------------------------------------

# Guloso de propósito (.*): vai da PRIMEIRA abertura até o ÚLTIMO fechamento.
# Assim, um "</conteudo_analisado>" escrito dentro do conteúdo não corta o texto.
_CONTEUDO = re.compile(r"<conteudo_analisado>\s*(.*)\s*</conteudo_analisado>", re.DOTALL)

PONTOS_POR_SINAL = 35

# Que golpe cada sinal sugere. Sinais genéricos (urgência, manipular IA) ficam
# como "outro_golpe" e só decidem a categoria se não houver outro mais específico.
_CATEGORIA_DO_SINAL = {
    "link_encurtado": "phishing_link",
    "link_com_ip": "phishing_link",
    "dominio_punycode": "phishing_link",
    "tld_suspeito": "phishing_link",
    "dominio_imita_marca": "phishing_link",
    "pagamento_antecipado": "pagamento_antecipado",
    "pedido_codigo_ou_senha": "falso_suporte_ou_banco",
    "sair_da_plataforma": "falso_intermediario",
    "urgencia_ou_ameaca": "outro_golpe",
    "troca_de_numero": "falso_parente_ou_conhecido",
    "promessa_ganho_facil": "investimento_falso",
    "premio_ou_restituicao": "premio_ou_restituicao_falsa",
    "comprovante_ou_intermediario": "comprovante_falso",
    "tentativa_manipular_ia": "outro_golpe",
}

_RECOMENDACAO = {
    "baixo": "Nenhum sinal automático, mas isso não garante segurança. Desconfie de qualquer pedido de pagamento ou de código.",
    "medio": "Confira por um canal oficial antes de pagar, clicar ou responder.",
    "alto": "Não pague, não clique e não passe códigos. Procure a empresa ou a pessoa por um canal oficial.",
}


def _extrair_conteudo(mensagem: str) -> str:
    achado = _CONTEUDO.search(mensagem)
    return achado.group(1) if achado else mensagem


def _nivel(pontuacao: int) -> str:
    if pontuacao >= 70:
        return "alto"
    if pontuacao >= 35:
        return "medio"
    return "baixo"


def _categoria(ids: list[str]) -> str:
    categorias = [_CATEGORIA_DO_SINAL.get(i, "outro_golpe") for i in ids]
    especificas = [c for c in categorias if c != "outro_golpe"]
    if especificas:
        return especificas[0]
    return categorias[0] if categorias else "nenhum"


def _chamar_mock(mensagem: str) -> RespostaBruta:
    sinais = detectar_sinais(_extrair_conteudo(mensagem))
    # Conta TIPOS de sinal: a mesma regra casando em dois pontos do texto
    # mostra as duas evidências, mas não vale pontos em dobro.
    tipos = {s.id for s in sinais}
    pontuacao = min(100, PONTOS_POR_SINAL * len(tipos))
    nivel = _nivel(pontuacao)

    if sinais:
        explicacao = (
            f"Análise feita só com regras automáticas, sem IA. "
            f"Foram encontrados {len(tipos)} tipo(s) de sinal comum(ns) em golpes."
        )
    else:
        explicacao = "Análise feita só com regras automáticas, sem IA. Nenhum sinal conhecido foi encontrado."

    dados = {
        "nivel_risco": nivel,
        "pontuacao": pontuacao,
        "categoria": _categoria([s.id for s in sinais]),
        "sinais": [{"sinal": s.descricao, "trecho": s.evidencia, "peso": "medio"} for s in sinais],
        "explicacao": explicacao,
        "recomendacao": _RECOMENDACAO[nivel],
        "confianca": "baixa",  # regra não entende contexto
    }
    return RespostaBruta(dados, tokens_in=0, tokens_out=0)