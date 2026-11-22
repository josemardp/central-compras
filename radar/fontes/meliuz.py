"""Meliuz: cupons por loja, lidos do texto publico da pagina (codigo + regras). Sao cupons de LOJA, nao de produto."""

from __future__ import annotations

import datetime as dt
import re
from typing import Any, Callable

from .. import cupons
from ..modelos import Oferta
from .base import FonteErro, FonteErroRede, http_get, texto_visivel

URL = "https://www.meliuz.com.br/desconto/{slug}"

_BLOCO = re.compile(
    r"(?P<curto>\d{1,3}\s*%|R\$\s?[\d.]+)\s*›\s*Regras\s+(?P<titulo>.+?)\s+(?P<cod>[A-Z0-9]{4,25})\s+Ver cupom\s+(?P=cod)\s+"
    r"(?P<desc>.+?)(?=\s+(?:\d{1,3}\s*%|R\$\s?[\d.]+)\s*›\s*Regras|\Z)",
    re.S,
)
_ATUALIZADO = re.compile(r"Atualizado em (\d{2})/(\d{2})/(\d{4}),? às(?:\s|&nbsp;|\xa0)*(\d{2})h(\d{2})")


def parse_pagina(html: str, loja: str) -> list[Oferta]:
    txt = re.sub(r"\s+", " ", texto_visivel(html).replace("\xa0", " "))
    m_at = _ATUALIZADO.search(txt)
    atualizado = f"{m_at.group(3)}-{m_at.group(2)}-{m_at.group(1)} {m_at.group(4)}:{m_at.group(5)}" if m_at else None
    saida: list[Oferta] = []
    for m in _BLOCO.finditer(txt):
        cod = m.group("cod")
        if cupons.PLACEHOLDER.search(cod):
            continue  # "ATIVENOLINK", "RESGATEAQUI": a pagina usa isso no lugar de um codigo real
        saida.append(Oferta(
            fonte="meliuz", canal=f"cupom_loja:{loja}", id_externo=f"{loja}:{cod}",
            titulo=f"{loja}: {m.group('titulo').strip()} ({m.group('curto').strip()})",
            texto=f"{m.group('titulo').strip()}. {m.group('desc').strip()[:400]}",
            cupom_codigo=cod, loja=loja, publicado_em=atualizado, extras={"tipo": "cupom_loja", "atualizado_pagina": atualizado},
        ))
    return saida


def coletar(cfg: dict[str, Any], baixar: Callable[[str], str] = http_get) -> list[Oferta]:
    saida: list[Oferta] = []
    erros: list[str] = []
    lojas = cfg.get("lojas") or {}
    for loja, slug in lojas.items():
        try:
            saida += parse_pagina(baixar(URL.format(slug=slug)), loja)
        except FonteErroRede as exc:
            erros.append(str(exc)[:100])
            break  # sem rede: as outras lojas falhariam igual
        except Exception as exc:  # noqa: BLE001 - uma loja fora do ar nao derruba as outras
            erros.append(f"{loja}: {str(exc)[:80]}")
    # Zero itens SO e "vazia" se nenhuma loja deu erro; se todas falharam, e FALHA do coletor (nao ausencia de cupons).
    if not saida and erros:
        raise FonteErro("; ".join(erros)[:300])
    return saida
