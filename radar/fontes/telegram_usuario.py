"""Registro da fonte Telegram (conta do usuario). A logica fica em radar/telegram_conta.py."""

from __future__ import annotations

from typing import Any

from .. import telegram_conta
from ..modelos import Oferta


def coletar(cfg: dict[str, Any]) -> list[Oferta]:
    return telegram_conta.coletar(cfg)
