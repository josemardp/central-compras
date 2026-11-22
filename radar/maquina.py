"""Trava de maquina oficial: so a maquina configurada coleta, envia relatorio e alerta."""

from __future__ import annotations

import os
import socket
from pathlib import Path

import yaml

from . import caminhos

ARQ = caminhos.CONFIG_DIR / "radar_maquina.yaml"


def hostname() -> str:
    return socket.gethostname()


def oficial(caminho: Path | None = None) -> str:
    arq = caminho or ARQ
    if not arq.exists():
        return ""
    return str((yaml.safe_load(arq.read_text(encoding="utf-8")) or {}).get("maquina_oficial") or "").strip()


def pode_rodar(caminho: Path | None = None) -> tuple[bool, str]:
    """(True, motivo) se esta maquina pode executar o radar. CENTRAL_COMPRAS_FORCAR_MAQUINA=1 libera uma execucao manual."""
    alvo = oficial(caminho)
    if not alvo or alvo.lower() == hostname().lower():
        return True, "maquina oficial" if alvo else "sem trava de maquina"
    if os.environ.get("CENTRAL_COMPRAS_FORCAR_MAQUINA") == "1":
        return True, f"forcado manualmente (oficial e {alvo})"
    return False, f"esta maquina ({hostname()}) nao e a oficial do radar ({alvo}); nada foi coletado nem enviado"
