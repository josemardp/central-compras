"""Telegram: canais com pagina publica (t.me/s/<usuario>). Somente leitura, sem conta, sem entrar em grupo.

Protecao de identidade: o canal so e lido se o titulo contiver o texto esperado e se o `data-post`
das mensagens pertencer ao usuario configurado. (t.me/s/promobit serve o canal de terceiros
'ofertasdecomputador', por exemplo.)
"""

from __future__ import annotations

import datetime as dt
import html as _html
import re
from typing import Any, Callable

from ..modelos import Oferta
from .base import FonteErro, http_get, preco_do_texto, texto_visivel


def _hora_local(iso: str | None) -> str | None:
    if not iso:
        return None
    try:
        d = dt.datetime.fromisoformat(iso)
        return d.astimezone().strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return None


def parse_pagina(html: str, usuario: str, titulo_contem: str) -> list[Oferta]:
    titulo = re.search(r"<title>(.*?)</title>", html, re.S)
    titulo = _html.unescape(titulo.group(1)) if titulo else ""
    if titulo_contem.lower() not in titulo.lower():
        raise FonteErro(f"identidade do canal @{usuario} nao confere: titulo '{titulo[:60]}' sem '{titulo_contem}'")
    saida: list[Oferta] = []
    blocos = re.split(r'(?=<div class="tgme_widget_message_wrap)', html)
    for b in blocos:
        post = re.search(r'data-post="([^"/]+)/(\d+)"', b)
        if not post:
            continue
        if post.group(1).lower() != usuario.lower():
            raise FonteErro(f"mensagens de @{post.group(1)} em vez de @{usuario}: canal descartado")
        corpo = re.search(r'class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', b, re.S)
        if not corpo:
            continue
        texto = texto_visivel(corpo.group(1))
        if not texto:
            continue
        links = re.findall(r'href="(https?://(?!t\.me)[^"]+)"', corpo.group(1))
        data = re.search(r'<time[^>]*datetime="([^"]+)"', b)
        saida.append(Oferta(
            fonte="telegram", canal=usuario, id_externo=post.group(2),
            titulo=texto.split("\n")[0][:200], texto=texto,
            url=links[0] if links else f"https://t.me/{usuario}/{post.group(2)}",
            preco_anunciado=preco_do_texto(texto), publicado_em=_hora_local(data.group(1) if data else None),
        ))
    return saida


def coletar(cfg: dict[str, Any], baixar: Callable[[str], str] = http_get) -> list[Oferta]:
    saida: list[Oferta] = []
    erros: list[str] = []
    canais = [c for c in cfg.get("canais") or [] if c.get("habilitado", True)]
    for c in canais:
        try:
            saida += parse_pagina(baixar(f"https://t.me/s/{c['usuario']}"), c["usuario"], c["titulo_contem"])
        except FonteErro as exc:
            erros.append(str(exc))
    if canais and not saida and erros:
        raise FonteErro("; ".join(erros)[:300])
    return saida
