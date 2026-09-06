#!/usr/bin/env python3
"""Instala a skill `central-compras` nas maquinas de agente encontradas.

Apos cada `git pull`, rode:

    python scripts/instalar_skill.py

A copia versionada em `skills/central-compras/` e a fonte da verdade:
o instalador substitui o que ja estiver em cada pasta de agente.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import uuid
from pathlib import Path


AGENTES: list[tuple[str, str]] = [
    (".codex", "Codex"),
    (".claude", "Claude Code"),
    (".antigravity", "Antigravity"),
]


def instalar(origem: Path, userprofile: Path) -> list[str]:
    """Copia a skill para cada agente encontrado. Retorna linhas de log."""
    origem = origem.resolve()
    if not (origem / "SKILL.md").is_file():
        raise ValueError(f"Fonte da skill invalida: {origem}")
    logs: list[str] = []
    for pasta_agente, nome in AGENTES:
        pai = userprofile / pasta_agente
        destino = pai / "skills" / "central-compras"
        if not pai.exists():
            logs.append(f"pulou {nome}: {pai} nao existe")
            continue
        destino.parent.mkdir(parents=True, exist_ok=True)
        if destino.is_symlink() or destino.resolve().parent != destino.parent.resolve():
            raise ValueError(f"Destino fora da pasta de skills: {destino}")
        # Prepara completamente antes de substituir a instalacao funcional.
        with tempfile.TemporaryDirectory(prefix=".central-compras-install-", dir=destino.parent) as temp:
            staging = Path(temp) / "nova"
            backup = destino.with_name(f".central-compras-backup-{uuid.uuid4().hex}")
            shutil.copytree(origem, staging)
            if destino.exists():
                destino.rename(backup)
            try:
                staging.rename(destino)
            except BaseException:
                if backup.exists():
                    backup.rename(destino)
                raise
            if backup.exists():
                # Caminho unico, resolvido no mesmo pai validado do destino.
                if backup.resolve().parent != destino.parent.resolve():
                    raise ValueError(f"Backup fora da pasta de skills: {backup}")
                shutil.rmtree(backup)
        logs.append(f"instalou {nome}: {destino}")
    return logs


def main(argv: list[str] | None = None) -> int:
    origem = Path(__file__).resolve().parents[1] / "skills" / "central-compras"
    if not origem.exists():
        print("Fonte nao encontrada: skills/central-compras/", file=sys.stderr)
        return 1

    userprofile = Path(os.environ.get("USERPROFILE", Path.home()))
    for linha in instalar(origem, userprofile):
        print(linha)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
