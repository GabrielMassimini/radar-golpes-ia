"""Carrega os prompts versionados (prompts/vN/system.md e user.md) e monta a mensagem.

O prompt fica fora do código: cada versão é uma pasta, e o Git mostra a
diferença entre elas. O user.md usa {conteudo} e, se quiser, {sinais}.
Toda versão põe o {conteudo} dentro de <conteudo_analisado>...</conteudo_analisado>,
para separar o texto do usuário das instruções.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

PASTA_PROMPTS = Path(__file__).resolve().parent.parent / "prompts"

# Versão que a API usa. As outras ficam para comparação (prompts/CHANGELOG.md).
VERSAO_PADRAO = "v3"

# Só "v" + número: impede pedir "../../.env" e ler outros arquivos.
_FORMATO_VERSAO = re.compile(r"v\d+")

# Os dois espaços que o template pode ter. Trocados numa passada só.
_ESPACOS = re.compile(r"\{(conteudo|sinais)\}")

# O conteúdo do usuário sempre fica entre marcações, separado das instruções.
_MOLDURA = re.compile(r"<conteudo_analisado>\s*\{conteudo\}\s*</conteudo_analisado>")

# Marcações que o template usa. Se aparecerem no texto do usuário (até com
# espaços ou maiúsculas), viram colchetes: assim o conteúdo não consegue
# "fechar" a marcação e fingir que o resto é instrução.
_MARCACOES = re.compile(r"<\s*(/?)\s*(conteudo_analisado|sinais_automaticos)\s*>", re.IGNORECASE)


@dataclass(frozen=True)
class Prompt:
    versao: str
    system: str
    user: str  # template com {conteudo} e, opcionalmente, {sinais}


def versoes_disponiveis(pasta: Path = PASTA_PROMPTS) -> list[str]:
    """Versões que existem na pasta, em ordem numérica (v1, v2, ..., v10)."""
    versoes = [
        item.name
        for item in pasta.iterdir()
        if item.is_dir() and _FORMATO_VERSAO.fullmatch(item.name)
    ]
    return sorted(versoes, key=lambda nome: int(nome[1:]))


@lru_cache(maxsize=None)
def carregar_prompt(versao: str = VERSAO_PADRAO, pasta: Path = PASTA_PROMPTS) -> Prompt:
    """Lê system.md e user.md da versão pedida."""
    if not _FORMATO_VERSAO.fullmatch(versao):
        raise ValueError(f"Versão de prompt inválida: '{versao}'. Use o formato v1, v2, v3...")

    pasta_versao = pasta / versao
    if not pasta_versao.is_dir():
        disponiveis = ", ".join(versoes_disponiveis(pasta)) or "nenhuma"
        raise ValueError(f"Versão '{versao}' não existe. Disponíveis: {disponiveis}.")

    system = (pasta_versao / "system.md").read_text(encoding="utf-8").strip()
    user = (pasta_versao / "user.md").read_text(encoding="utf-8").strip()
    if not _MOLDURA.search(user):
        raise ValueError(
            f"O user.md da versão '{versao}' precisa ter o espaço {{conteudo}} "
            "dentro de <conteudo_analisado>...</conteudo_analisado>."
        )
    return Prompt(versao, system, user)


def montar_mensagem(prompt: Prompt, conteudo: str, sinais: str = "") -> str:
    """Encaixa o conteúdo e o resumo dos sinais no template.

    Não usa str.format(): o conteúdo pode ter {chaves}. A troca é feita numa
    passada só, então nada que vem do usuário é substituído de novo.
    """
    valores = {"conteudo": neutralizar(conteudo), "sinais": neutralizar(sinais)}
    return _ESPACOS.sub(lambda m: valores[m.group(1)], prompt.user)


def neutralizar(texto: str) -> str:
    """Troca <conteudo_analisado>, </sinais_automaticos> etc. por [conteudo_analisado]..."""
    return _MARCACOES.sub(lambda m: f"[{m.group(1)}{m.group(2).lower()}]", texto)