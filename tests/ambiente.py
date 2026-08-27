"""Ambiente limpo para teste.

Copiar `base-conhecimento/` do repositorio real para dentro do teste faz o
teste herdar marcas, lojas e licoes de verdade, com as datas de verdade. Um
teste de reaproveitamento montado assim passou no dia em que foi escrito e
passou a falhar no dia seguinte, quando aquelas entradas viraram "anteriores"
ao projeto recem-criado.

Teste le fonte de teste. Nada do repositorio real entra.
"""

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

#: Copiado do repositorio: e configuracao e template, nao dado acumulado.
CONFIGURACAO = ["config", "templates", "scripts"]


def montar(destino: Path, extras: list[str] | None = None) -> Path:
    """Monta um repositorio de teste com config real e base de conhecimento vazia."""
    for nome in CONFIGURACAO + (extras or []):
        origem = ROOT / nome
        if not origem.exists():
            continue
        if origem.is_dir():
            shutil.copytree(origem, destino / nome, ignore=shutil.ignore_patterns("__pycache__"))
        else:
            shutil.copy2(origem, destino / nome)

    base = destino / "base-conhecimento"
    (base / "marcas").mkdir(parents=True, exist_ok=True)
    (base / "lojas").mkdir(parents=True, exist_ok=True)
    (base / "licoes.md").write_text("# Licoes\n\n", encoding="utf-8", newline="\n")
    return destino
