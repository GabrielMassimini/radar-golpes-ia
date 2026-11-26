"""API do Radar de Golpes (FastAPI). Local: uvicorn api.index:app --reload

GET  /api/saude     se está no ar e qual prompt/modelo usa
POST /api/analisar  texto e/ou print -> análise
GET  /              página de demo

Privacidade: o conteúdo enviado só passa pela memória durante a análise.
Nada é gravado nem escrito em log.
"""

from __future__ import annotations

import base64
import binascii
import hmac
import os
import re
import threading
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from radar import analisar
from radar.detector import MAX_CARACTERES
from radar.modelos import MODELO_PADRAO
from radar.prompts import VERSAO_PADRAO
from radar.provedores import Imagem

PAGINA = Path(__file__).resolve().parent.parent / "public" / "index.html"

# A Vercel limita o tamanho do pedido (~4,5 MB) e o base64 aumenta a imagem em
# ~33%. Com 3 MB de imagem, o pedido inteiro cabe. A página já reduz o print antes.
MAX_IMAGEM_BYTES = 3 * 1024 * 1024
JANELA_S = 3600  # o limite da demo é por hora
LIMITE_PADRAO = 15

# Primeiros bytes de cada formato: confere que o arquivo é mesmo a imagem declarada.
_ASSINATURAS = {
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/gif": (b"GIF87a", b"GIF89a"),
    "image/webp": (b"RIFF",),  # e "WEBP" nos bytes 8 a 12, conferido abaixo
}
_DATA_URL = re.compile(r"^data:([\w/+.-]+);base64,", re.IGNORECASE)


class Pedido(BaseModel):
    texto: str = Field("", max_length=MAX_CARACTERES, description="Mensagem ou anúncio a analisar.")
    imagem_base64: str | None = Field(None, description="Print em base64 (aceita data URL).")
    imagem_media_type: str | None = Field(None, description="image/jpeg, image/png, image/webp ou image/gif.")


class LimitePorIp:
    """Janela deslizante em memória. Em serverless cada instância tem a sua, então
    é uma proteção básica: a garantia real é não ter cartão cadastrado no provedor."""

    def __init__(self) -> None:
        self.pedidos: dict[str, deque[float]] = defaultdict(deque)
        self.trava = threading.Lock()

    def permitir(self, ip: str, limite: int, agora: float) -> bool:
        with self.trava:
            if len(self.pedidos) > 10_000:  # não deixa a memória crescer sem fim
                self.pedidos = defaultdict(deque, {k: v for k, v in self.pedidos.items()
                                                   if v and agora - v[-1] < JANELA_S})
            fila = self.pedidos[ip]
            while fila and agora - fila[0] >= JANELA_S:
                fila.popleft()
            if len(fila) >= limite:
                return False
            fila.append(agora)
            return True


limite_demo = LimitePorIp()

app = FastAPI(
    title="Radar de Golpes IA",
    description="Recebe uma mensagem, anúncio ou print e devolve o risco de ser golpe, com os sinais explicados.",
    version="1.0",
)
# Sem CORS de propósito: a página é servida por esta mesma API e o n8n chama
# de servidor para servidor. Liberar CORS deixaria outros sites usarem a cota.


def _ler_imagem(dados: str, media_type: str | None) -> Imagem:
    dados = "".join(dados.split())
    achado = _DATA_URL.match(dados)
    if achado:
        media_type = achado.group(1).lower()
        dados = dados[achado.end():]
    if media_type not in _ASSINATURAS:
        raise HTTPException(400, "Formato de imagem não aceito. Use JPEG, PNG, WebP ou GIF.")
    if len(dados) > MAX_IMAGEM_BYTES * 4 // 3 + 4:  # confere antes de decodificar
        raise HTTPException(413, "Imagem maior que 3 MB.")
    try:
        bruto = base64.b64decode(dados, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(400, "A imagem não está em base64 válido.") from None
    if len(bruto) > MAX_IMAGEM_BYTES:
        raise HTTPException(413, "Imagem maior que 3 MB.")
    valida = bruto.startswith(_ASSINATURAS[media_type])
    if media_type == "image/webp":
        valida = valida and bruto[8:12] == b"WEBP"
    if not valida:
        raise HTTPException(400, f"O arquivo não parece ser uma imagem {media_type}.")
    return Imagem(media_type, dados)


def _ip(request: Request) -> str:
    # Na Vercel o IP real chega em X-Forwarded-For. A Vercel sobrescreve esse
    # cabeçalho, então o visitante não consegue falsificar o próprio IP.
    encaminhado = request.headers.get("x-forwarded-for", "")
    if encaminhado:
        return encaminhado.split(",")[0].strip()
    return request.client.host if request.client else "desconhecido"


def _token_valido(token: str | None) -> bool:
    """None se não veio token. Comparação em tempo constante: não dá para
    descobrir o token medindo quanto a resposta demora."""
    esperado = os.environ.get("RADAR_TOKEN", "")
    if token is None:
        return False
    if not esperado or not hmac.compare_digest(token.encode(), esperado.encode()):
        raise HTTPException(401, "Token inválido.")
    return True


@app.get("/api/saude")
def saude() -> dict[str, str]:
    return {
        "status": "ok",
        "versao_prompt": VERSAO_PADRAO,
        "modelo": os.environ.get("RADAR_MODELO") or MODELO_PADRAO,
    }


@app.post(
    "/api/analisar",
    responses={
        400: {"description": "Sem texto e sem imagem, ou imagem inválida."},
        401: {"description": "Token X-Radar-Token errado."},
        413: {"description": "Imagem maior que 3 MB."},
        429: {"description": "Limite de análises por hora da demo atingido."},
        502: {"description": "O modelo não conseguiu analisar (falha ou resposta fora do formato)."},
    },
)
def analisar_conteudo(
    pedido: Pedido,
    request: Request,
    x_radar_token: str | None = Header(None),
) -> dict[str, Any]:
    imagem = None
    if pedido.imagem_base64:
        imagem = _ler_imagem(pedido.imagem_base64, pedido.imagem_media_type)
    if not pedido.texto.strip() and imagem is None:
        raise HTTPException(400, "Envie um texto ou uma imagem para analisar.")

    if not _token_valido(x_radar_token):
        limite = int(os.environ.get("RADAR_LIMITE_DEMO") or LIMITE_PADRAO)
        if not limite_demo.permitir(_ip(request), limite, time.monotonic()):
            raise HTTPException(429, f"Limite de {limite} análises por hora atingido. Tente mais tarde.")

    resultado = analisar(pedido.texto, imagem=imagem)
    if resultado.analise is None:
        raise HTTPException(502, f"Não foi possível analisar agora. {resultado.meta.erro}")
    return resultado.to_dict()


@app.get("/", include_in_schema=False)
def pagina() -> FileResponse:
    if not PAGINA.is_file():
        raise HTTPException(404, "Página de demo ainda não criada.")
    return FileResponse(PAGINA)