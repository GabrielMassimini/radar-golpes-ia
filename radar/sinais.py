"""Regras automáticas (sem IA) que encontram sinais objetivos de golpe.

As regras são pistas, não veredito: servem de baseline na avaliação e de
contexto para o LLM, que confirma ou descarta cada pista lendo o conteúdo.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import NamedTuple

# Quantos caracteres de contexto mostrar antes e depois do trecho encontrado.
MARGEM_EVIDENCIA = 25


@dataclass(frozen=True)
class Sinal:
    """Um sinal encontrado pelas regras.

    id: identificador curto (ex.: "link_encurtado").
    descricao: explicação em linguagem simples.
    evidencia: trecho do texto ORIGINAL que comprova o sinal.
    """

    id: str
    descricao: str
    evidencia: str


# ---------------------------------------------------------------------------
# Parte 1: normalização e recorte da evidência
# ---------------------------------------------------------------------------


def _normalizar_caractere(c: str) -> str:
    """Minúscula e sem acento. Pode devolver 0, 1 ou mais caracteres."""
    decomposto = unicodedata.normalize("NFKD", c.lower())
    return "".join(ch for ch in decomposto if not unicodedata.combining(ch))


def _normalizar_com_mapa(texto: str) -> tuple[str, list[int]]:
    """Normaliza o texto e devolve um mapa de posições.

    mapa[i] = posição, no texto original, do caractere i do texto normalizado.
    O mapa é necessário porque alguns caracteres mudam de tamanho ao
    normalizar (ex.: a ligadura "ﬁ" vira "fi"), o que deslocaria a evidência.
    """
    partes: list[str] = []
    mapa: list[int] = []
    for posicao, c in enumerate(texto):
        normalizado = _normalizar_caractere(c)
        partes.append(normalizado)
        mapa.extend([posicao] * len(normalizado))
    return "".join(partes), mapa


def normalizar(texto: str) -> str:
    """Deixa o texto em minúsculas e sem acentos: "Atenção" -> "atencao"."""
    return _normalizar_com_mapa(texto)[0]


def recortar_evidencia(
    texto: str, inicio: int, fim: int, margem: int = MARGEM_EVIDENCIA
) -> str:
    """Recorta do texto original o trecho [inicio, fim) com margem de contexto.

    Nunca corta palavras no meio: o trecho encontrado é estendido até palavras
    inteiras, e a margem é encolhida até a fronteira de palavra mais próxima.
    O resultado é sempre uma cópia exata de um pedaço do texto original.
    """
    # 1) Estende o trecho encontrado até cobrir palavras inteiras.
    while inicio > 0 and not texto[inicio - 1].isspace():
        inicio -= 1
    while fim < len(texto) and not texto[fim].isspace():
        fim += 1

    # 2) Margem à esquerda: se cair no meio de uma palavra, pula essa palavra.
    a = max(0, inicio - margem)
    if a > 0 and not texto[a - 1].isspace():
        while a < inicio and not texto[a].isspace():
            a += 1

    # 3) Margem à direita: se cair no meio de uma palavra, recua até o espaço.
    b = min(len(texto), fim + margem)
    if b < len(texto) and not texto[b].isspace():
        while b > fim and not texto[b - 1].isspace():
            b -= 1

    return texto[a:b].strip()


# ---------------------------------------------------------------------------
# Parte 2: extração de URLs
# ---------------------------------------------------------------------------

# Roda sobre o texto normalizado (minúsculo, sem acento).
_PADRAO_URL = re.compile(
    r"""
    (?<![@\w.-])                 # não começa colado em e-mail nem no meio de palavra
    (?P<esquema>https?://)?      # http:// é opcional: golpista costuma omitir
    (?P<host>
        \d{1,3}(?:\.\d{1,3}){3}  # IP, ex.: 192.168.0.1
      | (?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+   # partes do domínio: "olx-liberacao."
        [a-z][a-z0-9-]*[a-z0-9]  # final (TLD) começando com letra: evita "1.500"
    )
    (?![\w@-])                   # não termina colado em e-mail ou palavra
    (?P<porta>:\d{1,5})?
    (?P<caminho>[/?#][^\s<>"']*)?
    """,
    re.VERBOSE,
)

_PADRAO_IP = re.compile(r"\d{1,3}(?:\.\d{1,3}){3}")

# Pontuação de fim de frase que costuma grudar no link: "acesse bit.ly/abc."
_PONTUACAO_FINAL = ".,;:!?)"


class _Url(NamedTuple):
    texto: str  # como aparece no texto original
    host: str  # domínio (ou IP) normalizado, sem porta nem caminho
    inicio: int  # posição no texto original
    fim: int


def _encontrar_urls(texto: str) -> list[_Url]:
    normalizado, mapa = _normalizar_com_mapa(texto)
    urls: list[_Url] = []
    for m in _PADRAO_URL.finditer(normalizado):
        host = m.group("host")
        tem_contexto_de_link = m.group("esquema") or m.group("porta") or m.group("caminho")
        if _PADRAO_IP.fullmatch(host) and not tem_contexto_de_link:
            continue  # "1.500.000.000" solto é número, não endereço

        inicio, fim = m.start(), m.end()
        while fim > inicio and normalizado[fim - 1] in _PONTUACAO_FINAL:
            fim -= 1

        inicio_original, fim_original = mapa[inicio], mapa[fim - 1] + 1
        urls.append(
            _Url(texto[inicio_original:fim_original], host, inicio_original, fim_original)
        )
    return urls


def extrair_urls(texto: str) -> list[str]:
    """Devolve os links do texto, como foram escritos, com ou sem http://."""
    return [url.texto for url in _encontrar_urls(texto)]


# ---------------------------------------------------------------------------
# Parte 3: checagem de domínios
# ---------------------------------------------------------------------------

ENCURTADORES = {
    "bit.ly", "tinyurl.com", "cutt.ly", "is.gd", "rb.gy", "shorturl.at",
    "encurtador.com.br", "t.ly", "ow.ly", "tiny.cc", "s.id", "abre.ai",
    "encr.pw", "l1nk.dev", "bit.do", "goo.su",
}

# Finais de domínio baratos e muito usados em golpes. Não são proibidos:
# são só um sinal a mais.
TLDS_SUSPEITOS = {
    "xyz", "top", "click", "online", "site", "icu", "buzz", "live", "shop",
    "rest", "monster", "cfd", "sbs", "lol", "quest", "cyou",
}

# Marcas que golpistas costumam imitar -> domínios oficiais.
# São apenas exemplos de referência; o projeto não tem vínculo com nenhuma delas.
DOMINIOS_OFICIAIS: dict[str, tuple[str, ...]] = {
    "olx": ("olx.com.br",),
    "mercadolivre": ("mercadolivre.com.br", "mercadolivre.com", "mercadopago.com.br"),
    "mercadopago": ("mercadopago.com.br", "mercadopago.com"),
    "nubank": ("nubank.com.br",),
    "itau": ("itau.com.br",),
    "bradesco": ("bradesco.com.br",),
    "santander": ("santander.com.br",),
    "caixa": ("caixa.gov.br",),
    "bancodobrasil": ("bb.com.br",),
    "correios": ("correios.com.br",),
    "gov": ("gov.br",),
    "receita": ("gov.br",),
    "detran": ("gov.br",),
    "serasa": ("serasa.com.br",),
    "shopee": ("shopee.com.br",),
    "amazon": ("amazon.com.br", "amazon.com"),
    "magalu": ("magazineluiza.com.br", "magalu.com"),
    "ifood": ("ifood.com.br",),
    "zapimoveis": ("zapimoveis.com.br",),
    "vivareal": ("vivareal.com.br",),
    "webmotors": ("webmotors.com.br",),
    "picpay": ("picpay.com",),
    "whatsapp": ("whatsapp.com", "wa.me"),
    "instagram": ("instagram.com",),
    "netflix": ("netflix.com",),
}


def _e_dominio_ou_subdominio(host: str, dominio: str) -> bool:
    """True para "nubank.com.br" e "app.nubank.com.br"; False para
    "nubank.com.br.golpe.xyz" (quem manda no link é o FINAL do domínio)."""
    return host == dominio or host.endswith("." + dominio)


def _marca_imitada(host: str) -> tuple[str, str] | None:
    """Se o domínio usa o nome de uma marca sem ser o oficial, devolve
    (marca, domínio oficial). Ignora pontos e hífens: "nu-bank" conta."""
    compacto = host.replace(".", "").replace("-", "")
    for marca, oficiais in DOMINIOS_OFICIAIS.items():
        if marca in compacto and not any(_e_dominio_ou_subdominio(host, o) for o in oficiais):
            return marca, oficiais[0]
    return None


def _sinais_de_url(texto: str) -> list[Sinal]:
    sinais: list[Sinal] = []
    for url in _encontrar_urls(texto):
        host, evidencia = url.host, url.texto

        if any(_e_dominio_ou_subdominio(host, e) for e in ENCURTADORES):
            sinais.append(Sinal(
                "link_encurtado",
                "Link encurtado esconde o endereço real",
                evidencia,
            ))
        if _PADRAO_IP.fullmatch(host):
            sinais.append(Sinal(
                "link_com_ip",
                "Link aponta para um número de IP em vez de um site com nome",
                evidencia,
            ))
        if "xn--" in host:
            sinais.append(Sinal(
                "dominio_punycode",
                "Domínio usa letras de outros alfabetos para imitar um site conhecido",
                evidencia,
            ))
        if host.rsplit(".", 1)[-1] in TLDS_SUSPEITOS:
            sinais.append(Sinal(
                "tld_suspeito",
                "Final de domínio muito usado em golpes",
                evidencia,
            ))
        imitacao = _marca_imitada(host)
        if imitacao:
            marca, oficial = imitacao
            sinais.append(Sinal(
                "dominio_imita_marca",
                f"Domínio usa o nome '{marca}', mas não é o site oficial ({oficial})",
                evidencia,
            ))
    return sinais


# ---------------------------------------------------------------------------
# Parte 4: padrões de texto e função principal
# ---------------------------------------------------------------------------

# (id, descrição, regex). As regex rodam sobre o texto normalizado
# (minúsculo e sem acento), então "Pix ANTECIPADO" vira "pix antecipado".
PADROES_TEXTO: list[tuple[str, str, re.Pattern[str]]] = [
    (
        "pagamento_antecipado",
        "Pede pagamento, sinal ou taxa antes de a pessoa receber",
        re.compile(
            r"(pix|deposito|transferencia|pag\w*|taxa|sinal|parcela|reserva)\W+(?:\w+\W+){0,6}?"
            r"(antecipad\w*|adiantad\w*|antes d[eoa]|para reservar|pra reservar|de liberacao"
            r"|de desbloqueio|de entrega|do frete|para liberar|pra liberar)"
            r"|(sinal|taxa|adiantamento)\s+(de|do|da)\s+r\$"
        ),
    ),
    (
        "pedido_codigo_ou_senha",
        "Pede código de verificação, token ou senha",
        re.compile(
            r"(codigo|cod\.?|token)\s*(de\s+)?(verificacao|confirmacao|seguranca"
            r"|que (chegou|vai chegar|recebeu|enviamos))"
            r"|(me (passa|manda|envia|informa)\w*)\W+(?:\w+\W+){0,3}?(codigo|senha|token)"
            r"|\bsua senha\b|\b6 digitos\b"
        ),
    ),
    (
        "sair_da_plataforma",
        "Tenta levar a conversa ou o pagamento para fora da plataforma",
        re.compile(
            r"(me chama|chama|fala comigo|vamos conversar|continua\w*)\s+(no|pelo|por)\s+"
            r"(whats|zap|wpp|telegram|direct|dm)"
            r"|fora (do|da) (app|aplicativo|plataforma|site)"
            r"|(pagamento|negocio|negociar)\s+por fora"
        ),
    ),
    (
        "urgencia_ou_ameaca",
        "Cria urgência ou ameaça",
        re.compile(
            r"\burgente\b|ultimas? (horas|unidades|vagas)|so (hoje|ate hoje)|imediatamente"
            r"|sera (bloquead|cancelad|suspens)\w*"
            r"|(conta|cpf|cartao|beneficio|cnh)\s+(\w+\s+){0,2}(bloquead|suspens|cancelad|irregular)\w*"
            r"|em ate \d+\s*(min|minutos|horas)"
        ),
    ),
    (
        "troca_de_numero",
        "Alega ter trocado de número",
        re.compile(
            r"(troquei|mudei|novo) (de )?(numero|celular|telefone)"
            r"|esse e meu (numero|zap|whats) novo"
            r"|salva (esse|meu) (numero|contato)"
        ),
    ),
    (
        "promessa_ganho_facil",
        "Promete ganho alto, fácil ou garantido",
        re.compile(
            r"(renda|lucro|ganho|retorno)\s+(\w+\s+){0,2}(garantid|diari|facil|extra)\w*"
            r"|ganhe? (ate )?r\$\s?[\d.,]+\s*(por dia|por semana|diarios?)"
            r"|(dobr|tripl|multiplic)\w+ (seu|o seu) (dinheiro|investimento)"
            r"|curtir videos|avaliar produtos e ganhar"
        ),
    ),
    (
        "premio_ou_restituicao",
        "Prêmio, sorteio, restituição ou valor inesperado",
        re.compile(
            r"(voce|vc) (foi|ganhou|tem direito)"
            r"|(premio|sorteio|restituicao|valores? a receber|indenizacao|reembolso) "
            r"(disponivel|liberad|pendente|aguardando)\w*"
        ),
    ),
    (
        "comprovante_ou_intermediario",
        "Fala em comprovante, pagamento retido ou intermediário da plataforma",
        re.compile(
            r"(pagamento|valor|dinheiro) (esta |ta )?(retido|bloqueado|em analise|pendente de liberacao)"
            r"|comprovante (em anexo|segue|enviado)"
            r"|(motoboy|transportadora|frete) (da|do) (olx|plataforma|mercado ?livre|app)"
            r"|olx pay\w*|garantia da olx"
        ),
    ),
    (
        "tentativa_manipular_ia",
        "O texto tenta dar ordens a uma IA (prompt injection)",
        re.compile(
            r"ignor\w+ (as |todas as |suas )?(instrucoes|regras)"
            r"|(voce|vc) (e|agora e) um assistente"
            r"|classifi\w+ (isso |este \w+ )?como (seguro|legitimo|confiavel)"
            r"|system prompt|sem riscos? de golpe, confirme"
        ),
    ),
]

SEM_SINAIS = "Nenhum sinal automático encontrado (isso NÃO significa que é seguro)."


def _sinais_de_texto(texto: str) -> list[Sinal]:
    normalizado, mapa = _normalizar_com_mapa(texto)
    sinais: list[Sinal] = []
    for id_sinal, descricao, padrao in PADROES_TEXTO:
        for m in padrao.finditer(normalizado):
            if m.end() == m.start():
                continue
            inicio, fim = mapa[m.start()], mapa[m.end() - 1] + 1
            sinais.append(Sinal(id_sinal, descricao, recortar_evidencia(texto, inicio, fim)))
    return sinais


def detectar_sinais(texto: str) -> list[Sinal]:
    """Roda todas as regras e devolve os sinais, sem repetir (id, evidência)."""
    vistos: set[tuple[str, str]] = set()
    resultado: list[Sinal] = []
    for sinal in _sinais_de_url(texto) + _sinais_de_texto(texto):
        chave = (sinal.id, sinal.evidencia)
        if chave not in vistos:
            vistos.add(chave)
            resultado.append(sinal)
    return resultado


def resumo_para_prompt(sinais: list[Sinal]) -> str:
    """Transforma os sinais em texto para o prompt (seção <sinais_automaticos>)."""
    if not sinais:
        return SEM_SINAIS
    return "\n".join(f'- {s.id}: {s.descricao}. Trecho: "{s.evidencia}"' for s in sinais)