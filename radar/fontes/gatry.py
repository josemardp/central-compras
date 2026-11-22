"""Gatry: API JSON publica `/v1/promotions` (a mesma que o site usa; permitida em robots.txt: `Allow: /v1/`).

Campos estruturados uteis: price_cents, old_price_cents, code, discount_text, valid_until, free_shipping,
requires_coupon_at_checkout, app_only, status, last_comment_body. Limite da API: 10 itens por pagina (offset).
Baixa frequencia (a cada 10 min, 4 requisicoes) e User-Agent identificavel no cliente HTTP padrao.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from typing import Any, Callable

from ..modelos import Oferta
from .base import FonteErro, FonteErroRede, http_get

API = "https://gatry.com/v1/promotions"
PAGINA = "https://gatry.com/promocoes/{id}/{slug}"
STATUS_ATIVO = {"active"}
PLACEHOLDERS = {"NOLINK", "NOAPP", "SEMCODIGO", "AUTOMATICO"}


def _hora_local(iso: str | None) -> str | None:
    if not iso:
        return None
    try:
        return dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone().strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return None


def _validade_texto(iso: str | None) -> str:
    h = _hora_local(iso)
    if not h:
        return ""
    d = dt.datetime.strptime(h, "%Y-%m-%d %H:%M")
    return f"valido ate {d:%d/%m/%Y} as {d:%H}h{d:%M}"


def _codigo_real(code: str | None) -> str | None:
    """'NO LINK' e afins sao a forma da comunidade de dizer 'sem codigo, ative no link'."""
    if not code:
        return None
    limpo = re.sub(r"\s+", "", code).upper()
    return None if limpo in PLACEHOLDERS or not re.fullmatch(r"[A-Z0-9_-]{4,25}", limpo) else limpo


def parse_item(p: dict[str, Any]) -> Oferta | None:
    if not p.get("id") or not p.get("title"):
        return None
    cents, old = p.get("price_cents"), p.get("old_price_cents")
    partes = [p.get("description") or "", p.get("discount_text") or "", _validade_texto(p.get("valid_until"))]
    if p.get("app_only"):
        partes.append("somente no app")
    if p.get("free_shipping"):
        partes.append("frete gratis")
    if p.get("requires_coupon_at_checkout"):
        partes.append("cupom aplicado no carrinho")
    comentario = (p.get("last_comment_body") or "").strip()
    codigo = _codigo_real(p.get("code"))
    cupom_de_loja = p.get("kind") == "coupon"
    return Oferta(
        fonte="gatry",
        canal="cupons" if cupom_de_loja else "promocoes",
        id_externo=str(p["id"]),
        titulo=str(p["title"]),
        texto=" ".join(x for x in partes if x).strip(),
        url=(p.get("url") or PAGINA.format(id=p["id"], slug=p.get("slug") or "")),
        loja=p.get("store_name"),
        preco_anunciado=cents / 100.0 if isinstance(cents, (int, float)) and cents > 0 else None,
        cupom_codigo=codigo,
        publicado_em=_hora_local(p.get("approved_at") or p.get("created_at")),
        comentarios=[comentario] if comentario else [],
        extras={
            "tipo": "cupom_loja" if cupom_de_loja else None, "status_fonte": p.get("status"),
            "preco_antigo": old / 100.0 if isinstance(old, (int, float)) and old > 0 else None,
            "pagina": PAGINA.format(id=p["id"], slug=p.get("slug") or ""), "comentarios_n": p.get("comment_count"),
            "app_only": bool(p.get("app_only")), "exige_cupom_no_carrinho": bool(p.get("requires_coupon_at_checkout")),
            "validade_utc": p.get("valid_until"),
        },
    )


def _pagina(baixar: Callable[[str], str], kind: str, offset: int) -> list[dict[str, Any]]:
    bruto = json.loads(baixar(f"{API}?kind={kind}&limit=10&offset={offset}&sort=approved"))
    lista = bruto.get("promotions") if isinstance(bruto, dict) else None
    if not isinstance(lista, list):
        raise FonteErro("resposta da API do Gatry sem 'promotions' (contrato mudou?)")
    return [p for p in lista if isinstance(p, dict)]


def coletar(cfg: dict[str, Any], baixar: Callable[[str], str] = http_get) -> list[Oferta]:
    paginas = int(cfg.get("paginas_promocoes", 3))
    saida: dict[str, Oferta] = {}
    erros: list[str] = []
    jobs = [("promotion", i * 10) for i in range(paginas)] + [("coupon", 0)]
    for kind, off in jobs:
        try:
            for p in _pagina(baixar, kind, off):
                if str(p.get("status")) not in STATUS_ATIVO:
                    continue
                of = parse_item(p)
                if of:
                    saida.setdefault(of.id_externo, of)
        except FonteErroRede as exc:
            erros.append(str(exc)[:100])
            break
        except (FonteErro, ValueError) as exc:
            erros.append(str(exc)[:100])
    if not saida and erros:
        raise FonteErro("; ".join(erros)[:300])
    return list(saida.values())


def revalidar(id_externo: str, preco_ref: float | None, baixar: Callable[[str], str] = http_get, tolerancia: float = 0.02) -> tuple[bool | None, str]:
    """`None` = NAO VERIFICAVEL (a API nao respondeu: falha de rede nao prova que a promocao acabou)."""
    try:
        p = json.loads(baixar(f"{API}/{id_externo}"))
    except (FonteErro, ValueError) as exc:
        return None, f"nao consegui reabrir a promocao: {str(exc)[:80]}"
    if not isinstance(p, dict) or not p.get("id"):
        return False, "promocao removida ou sem dados"
    if str(p.get("status")) not in STATUS_ATIVO:
        return False, f"promocao encerrada na fonte (status {p.get('status')})"
    if p.get("valid_until"):
        try:
            if dt.datetime.fromisoformat(p["valid_until"].replace("Z", "+00:00")) < dt.datetime.now(dt.timezone.utc):
                return False, "validade vencida na fonte"
        except ValueError:
            pass
    cents = p.get("price_cents")
    if preco_ref and isinstance(cents, (int, float)) and cents > 0 and cents / 100.0 > preco_ref * (1 + tolerancia):
        return False, f"preco subiu de R$ {preco_ref:.2f} para R$ {cents / 100.0:.2f}"
    return True, f"ativa na fonte (status {p.get('status')})"
