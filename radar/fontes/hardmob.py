"""HardMOB, forum Promocoes: lista publica de topicos (titulo no formato 'Loja - Produto - R$ preco')."""

from __future__ import annotations

import html as _html
import re
from typing import Any, Callable

from ..modelos import Oferta
from .base import http_get, preco_do_texto

URL = "https://www.hardmob.com.br/forums/407-Promocoes"
TOPICO = "https://www.hardmob.com.br/showthread.php?t={id}"


def parse_pagina(html: str) -> list[Oferta]:
    saida: list[Oferta] = []
    for m in re.finditer(r'id="thread_title_(\d+)"[^>]*>(.*?)</a>', html, re.S):
        tid = m.group(1)
        titulo = re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", m.group(2)))).strip()
        if not titulo:
            continue
        partes = [p.strip() for p in titulo.split(" - ")]
        loja = partes[0] if len(partes) >= 3 and len(partes[0]) <= 25 else None
        saida.append(Oferta(
            fonte="hardmob", id_externo=tid, titulo=titulo, url=TOPICO.format(id=tid), loja=loja,
            preco_anunciado=preco_do_texto(titulo),
        ))
    return saida


def coletar(cfg: dict[str, Any], baixar: Callable[[str], str] = http_get) -> list[Oferta]:
    return parse_pagina(baixar(URL))
