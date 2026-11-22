"""Promobit: ofertas recentes e paginas de loja, lidas do JSON publico embutido na pagina (__NEXT_DATA__)."""

from __future__ import annotations

import json
import re
from typing import Any, Callable

from ..modelos import Oferta
from .base import FonteErro, FonteErroRede, http_get

BASE = "https://www.promobit.com.br"


def _next_data(html: str) -> dict[str, Any]:
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        raise FonteErro("pagina sem __NEXT_DATA__ (layout mudou ou bloqueio)")
    return json.loads(m.group(1)).get("props", {}).get("pageProps", {})


def _data(v: str | None) -> str | None:
    """'2026-11-20T15:30:59-0300' -> '2026-11-20 15:30' (a fonte ja informa no fuso local)."""
    return v[:10] + " " + v[11:16] if v and len(v) >= 16 else None


def parse_oferta(o: dict[str, Any], canal: str) -> Oferta | None:
    if not o.get("offerId") or not o.get("offerTitle"):
        return None
    preco = o.get("offerPrice")
    cupom = o.get("offerCoupon")
    return Oferta(
        fonte="promobit",
        canal=canal,
        id_externo=str(o["offerId"]),
        titulo=str(o["offerTitle"]),
        url=f"{BASE}/oferta/{o['offerSlug']}/" if o.get("offerSlug") else None,
        loja=o.get("storeName"),
        preco_anunciado=float(preco) if isinstance(preco, (int, float)) and preco > 0 else None,
        cupom_codigo=str(cupom) if cupom else None,
        publicado_em=_data(o.get("offerPublished")),
        extras={
            "curtidas": o.get("offerLikes"), "comentarios": o.get("offerComments"),
            "preco_antigo": o.get("offerOldPrice"), "status": o.get("offerStatusName"),
        },
    )


def parse_cupom_loja(c: dict[str, Any], canal: str) -> Oferta | None:
    if not c.get("couponId"):
        return None
    instr = c.get("couponInstructions") or ""
    desc = c.get("couponDiscountValue") or c.get("couponDiscount") or ""
    return Oferta(
        fonte="promobit",
        canal=f"cupom_loja:{canal}",
        id_externo=f"cupom-{c['couponId']}",
        titulo=f"{c.get('storeName', '')}: {desc} em {c.get('couponDiscountOn', '')}".strip(),
        texto=instr,
        loja=c.get("storeName"),
        publicado_em=_data(c.get("couponPublished")),
        verificado_em=_data(c.get("couponVerified")),
        extras={"status_fonte": c.get("couponStatusName"), "tipo": "cupom_loja"},
    )


def parse_pagina(html: str, canal: str) -> list[Oferta]:
    pp = _next_data(html)
    saida: list[Oferta] = []
    for o in (pp.get("serverOffers") or {}).get("offers") or []:
        of = parse_oferta(o, canal)
        if of:
            saida.append(of)
    for c in _lista_de_cupons(pp.get("serverCoupons")):
        of = parse_cupom_loja(c, canal)
        if of:
            saida.append(of)
    return saida


def _lista_de_cupons(bruto: Any) -> list[dict[str, Any]]:
    """Na home `serverCoupons` e lista; nas paginas de loja pode ser dict com listas dentro. So aceita dicts."""
    if isinstance(bruto, dict):
        itens: list[Any] = []
        for v in bruto.values():
            itens += v if isinstance(v, list) else [v]
    else:
        itens = list(bruto or [])
    return [c for c in itens if isinstance(c, dict)]


STATUS_INATIVOS = {"FINISHED", "EXPIRED", "REMOVED", "REJECTED", "DELETED", "CANCELED"}


def revalidar(url: str, preco_ref: float | None, baixar: Callable[[str], str] = http_get, tolerancia: float = 0.02) -> tuple[bool | None, str]:
    """Abre a pagina da oferta: ativa = status fora de STATUS_INATIVOS e preco nao pior que o do alerta (+2%).
    `None` = NAO VERIFICAVEL (a pagina nao abriu: falha de rede nao prova que a oferta acabou)."""
    try:
        so = _next_data(baixar(url)).get("serverOffer") or {}
    except (FonteErro, ValueError) as exc:
        return None, f"nao consegui reabrir a oferta: {str(exc)[:80]}"
    if not so:
        return False, "pagina da oferta sem dados (removida?)"
    status = str(so.get("offerStatusName") or "")
    if status.upper() in STATUS_INATIVOS:
        return False, f"oferta encerrada na fonte (status {status})"
    preco = so.get("offerPrice")
    if preco_ref and isinstance(preco, (int, float)) and preco > 0 and preco > preco_ref * (1 + tolerancia):
        return False, f"preco subiu de R$ {preco_ref:.2f} para R$ {preco:.2f}"
    return True, f"ativa na fonte (status {status or 'n/d'})"


def _cursor(html: str) -> str | None:
    """Cursor da proxima pagina de `serverOffers` (`?after=<cursor>`). `?page=N` NAO pagina em /promocoes/recentes/."""
    try:
        c = (_next_data(html).get("serverOffers") or {}).get("after")
    except (FonteErro, ValueError):
        return None
    return str(c) if c else None


def coletar(cfg: dict[str, Any], baixar: Callable[[str], str] = http_get) -> list[Oferta]:
    """Recentes por CURSOR (cada pagina traz 12; `?page=N` devolvia sempre os mesmos 12 = so 9 min de cobertura, bug de 21/11/2026)
    + paginas de loja (ofertas e cupons da loja)."""
    ofertas: dict[str, Oferta] = {}
    erros: list[str] = []
    rede_caiu = False
    url = f"{BASE}/promocoes/recentes/"
    for p in range(1, int(cfg.get("paginas_recentes", 5)) + 1):
        try:
            html = baixar(url)
            itens = parse_pagina(html, f"recentes-p{p}")
        except FonteErroRede as exc:
            erros.append(str(exc))
            rede_caiu = True
            break
        except FonteErro as exc:
            erros.append(str(exc))
            break  # sem pagina valida nao ha cursor para continuar
        novos = [o for o in itens if o.id_externo not in ofertas]
        for of in itens:
            ofertas.setdefault(f"{of.id_externo}", of)
        cursor = _cursor(html)
        if not cursor or not novos:
            break
        url = f"{BASE}/promocoes/recentes/?after={cursor}"
    for slug in ([] if rede_caiu else (cfg.get("lojas") or [])):
        try:
            for of in parse_pagina(baixar(f"{BASE}/promocoes/loja/{slug}/"), f"loja-{slug}"):
                ofertas.setdefault(f"{of.id_externo}", of)
        except FonteErroRede as exc:
            erros.append(str(exc))
            break  # sem rede: as outras paginas falhariam igual
        except FonteErro as exc:
            erros.append(str(exc))
    if not ofertas and erros:
        raise FonteErro("; ".join(erros)[:300])
    return list(ofertas.values())
