"""Canais de saida. Hoje: WhatsApp do Josemar pela aba compartilhada (zap-vivo, CDP 9230).

A infraestrutura (navegador sempre de pe, pareamento) e do projeto skills-pessoais/Coral.
Aqui fica so o adaptador: nenhuma credencial e copiada e nenhuma segunda sessao e aberta.
"""

from __future__ import annotations

import sys
from typing import Callable

from . import caminhos


def enviar_whatsapp(texto: str) -> tuple[bool, str]:
    """Envia ao chat proprio reutilizando o envio robusto (retentativas, texto conferido antes do Enter)."""
    raiz = str(caminhos.RAIZ)
    if raiz not in sys.path:
        sys.path.insert(0, raiz)
    from scripts import rastrear_robos_bf as rr  # import tardio: carrega Playwright so quando precisa

    return rr.enviar_whatsapp(texto)


def canal_padrao() -> Callable[[str], tuple[bool, str]]:
    return enviar_whatsapp
