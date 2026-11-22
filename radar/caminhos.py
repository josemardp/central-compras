"""Onde ficam o codigo, a configuracao e os dados privados do radar."""

from __future__ import annotations

import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
CONFIG_DIR = RAIZ / "config"


def privado_dir() -> Path:
    """Pasta de dados privados (fora do Git). Sobrescrevivel por variavel de ambiente."""
    env = os.environ.get("CENTRAL_COMPRAS_DADOS_PRIVADOS")
    base = Path(env) if env else Path.home() / ".central-compras" / "dados-privados"
    return base


def radar_dir() -> Path:
    d = privado_dir() / "radar"
    d.mkdir(parents=True, exist_ok=True)
    return d


def db_path() -> Path:
    return radar_dir() / "radar.db"


def logs_dir() -> Path:
    d = radar_dir() / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def travas_dir() -> Path:
    d = radar_dir() / "travas"
    d.mkdir(parents=True, exist_ok=True)
    return d


def backups_dir() -> Path:
    d = radar_dir() / "backups"
    d.mkdir(parents=True, exist_ok=True)
    return d


def tracker_dir(nome: str) -> Path:
    """Pasta de um rastreador legado (estado.json + historico.jsonl): rastreador-robos etc."""
    return privado_dir() / nome
