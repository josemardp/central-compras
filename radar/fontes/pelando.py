"""Pelando: HTML servido sem navegador (/recentes), via JSON-LD schema.org + atributos data-* dos cards.

Evidencia (21/11/2026): o Chrome automatizado recebe "Sorry, you have been blocked" (WAF) e nao ha RSS/sitemap/API
publica documentada; a requisicao HTTP comum recebe 200 com o feed renderizado no servidor. robots.txt do site
permite tudo exceto /postar e /meus-alertas. NAO se tenta contornar o WAF: se o HTTP comum passar a ser bloqueado,
a fonte falha de forma visivel (FonteErro) e fica "instavel/erro" no relatorio de efetividade.

Fragilidade: media. Usa atributos semanticos (data-deal-id, data-inactive, data-share-title) e JSON-LD, nao as classes
CSS hasheadas; preco e loja saem do texto do card.
"""

from __future__ import annotations

import datetime as dt
import html as _html
import json
import re
from typing import Any, Callable

from ..modelos import Oferta
from .base import FonteErro, http_get, texto_visivel

URL = "https://www.pelando.com.br/recentes"
_BLOQUEIO = re.compile(r"you have been blocked|Attention Required|cf-chl|Just a moment", re.I)


def _jsonld_urls(html: str) -> dict[str, str]:
    """{titulo normalizado: url} do bloco JSON-LD (hasPart)."""
    mapa: dict[str, str] = {}
    for m in re.finditer(r'application/ld\+json"[^>]*>(.*?)</script>', html, re.S):
        try:
            d = json.loads(m.group(1))
        except ValueError:
            continue
        partes = ((d.get("mainEntity") or {}).get("hasPart") if isinstance(d, dict) else None) or []
        for p in partes:
            if isinstance(p, dict) and p.get("url") and p.get("name"):
                mapa[_norm(p["name"])] = p["url"]
    return mapa


def _norm(t: str) -> str:
    return re.sub(r"\s+", " ", _html.unescape(t or "")).strip().lower()


def _idade_minutos(texto: str) -> int | None:
    if re.search(r"\bagora\b", texto, re.I):
        return 0
    m = re.search(r"h[aá]\s*(\d+)\s*(min|h|d)\b|(?<![\w-])(\d+)\s*(min|h|d)\b(?![\w-])", texto, re.I)
    if not m:
        return None
    n = int(m.group(1) or m.group(3))
    un = (m.group(2) or m.group(4)).lower()
    return n * {"min": 1, "h": 60, "d": 1440}[un]


def _preco(txt: str) -> float | None:
    m = re.search(r"R\$\s*([\d]{1,3}(?:\.\d{3})*|\d+)(?:\s*,\s*(\d{2}))?", txt)
    if not m:
        return None
    inteiro = float(m.group(1).replace(".", ""))
    return inteiro + (int(m.group(2)) / 100 if m.group(2) else 0.0)


def parse_pagina(html: str, agora: dt.datetime | None = None) -> list[Oferta]:
    if _BLOQUEIO.search(html[:6000]) and "data-deal-id" not in html:
        raise FonteErro("Pelando bloqueou a requisicao (WAF); nao sera contornado")
    agora = agora or dt.datetime.now()
    if "data-deal-id" not in html:
        raise FonteErro("pagina sem cards data-deal-id (layout mudou?)")
    urls = _jsonld_urls(html)
    # cada card repete o id; agrupa pela primeira ocorrencia
    marcas: list[tuple[int, str]] = []
    vistos: set[str] = set()
    for m in re.finditer(r'data-deal-id="([^"]+)"', html):
        if m.group(1) not in vistos:
            vistos.add(m.group(1))
            marcas.append((m.start(), m.group(1)))
    saida: list[Oferta] = []
    for i, (pos, did) in enumerate(marcas):
        fim = marcas[i + 1][0] if i + 1 < len(marcas) else pos + 6000
        bloco = html[pos:fim]
        titulo = re.search(r'data-share-title="([^"]+)"', bloco)
        if not titulo:
            continue
        titulo_txt = _html.unescape(titulo.group(1)).strip()
        if re.search(r'data-inactive="true"', bloco):
            continue  # encerrada na propria fonte
        # O bloco comeca no MEIO da tag (data-deal-id="GUID"...): sem descartar esse resto, "894d" do GUID virava "894 dias"
        # (bug achado em 21/11/2026: item de 4 min lido como de 2,4 anos, portanto "antigo" e sem alerta).
        corpo = bloco.split(">", 1)[1] if ">" in bloco else bloco
        txt = re.sub(r"\s+", " ", texto_visivel(corpo))
        loja = re.search(r"Vendido por\s+(.+?)\s+(?:R\$|Vendido|\d+\s*°|Frete|Gr[aá]tis)", txt)
        minutos = _idade_minutos(txt)
        cupom = re.search(r"(?:cupom|c[oó]digo)\s*:?\s*([A-Z0-9]{4,20})\b", txt)
        eh_cupom_de_loja = bool(re.match(r"\s*cupom\b", titulo_txt, re.I))  # "Cupom Pague Menos - R$40 OFF": o R$ e desconto, nao preco
        saida.append(Oferta(
            fonte="pelando", canal="recentes", id_externo=did, titulo=titulo_txt, texto=txt[:400],
            url=urls.get(_norm(titulo_txt)), loja=loja.group(1).strip() if loja else None,
            preco_anunciado=None if eh_cupom_de_loja else _preco(txt),
            cupom_codigo=cupom.group(1) if cupom else None,
            publicado_em=(agora - dt.timedelta(minutes=minutos)).strftime("%Y-%m-%d %H:%M") if minutos is not None else None,
            extras={"tipo": "cupom_loja"} if eh_cupom_de_loja else {},
        ))
    return saida


def coletar(cfg: dict[str, Any], baixar: Callable[[str], str] = http_get) -> list[Oferta]:
    return parse_pagina(baixar(URL))
