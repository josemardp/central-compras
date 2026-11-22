"""Aplica correcoes versionadas (config/radar_correcoes.yaml) aos registros lidos do historico."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml

from . import caminhos

ARQ_CORRECOES = caminhos.CONFIG_DIR / "radar_correcoes.yaml"


def carregar(caminho: Path | None = None) -> list[dict[str, Any]]:
    arq = caminho or ARQ_CORRECOES
    if not arq.exists():
        return []
    return (yaml.safe_load(arq.read_text(encoding="utf-8")) or {}).get("correcoes") or []


def aplicar(registros: list[dict[str, Any]], origem: str | None, correcoes: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Devolve copia dos registros com as correcoes da `origem` aplicadas (o original nao muda)."""
    regras = [c for c in (correcoes if correcoes is not None else carregar()) if c.get("origem") == origem]
    if not regras:
        return registros
    saida: list[dict[str, Any]] = []
    for reg in registros:
        regs_do_registro = [c for c in regras if str(c.get("coletado_em")) == str(reg.get("coletado_em"))]
        if not regs_do_registro:
            saida.append(reg)
            continue
        novo = copy.deepcopy(reg)
        for c in regs_do_registro:
            mod = (novo.get("modelos") or {}).get(c.get("produto"))
            if mod is None:
                continue
            mod["melhor_preco_original"] = mod.get("melhor_preco")
            mod["melhor_preco"] = c.get("melhor_preco")
            if c.get("melhor_onde"):
                mod["melhor_onde"] = c["melhor_onde"]
            mod["corrigido"] = True
        saida.append(novo)
    return saida
