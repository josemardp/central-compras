"""Ambiente limpo para teste.

Copiar `base-conhecimento/` do repositorio real para dentro do teste faz o
teste herdar marcas, lojas e licoes de verdade, com as datas de verdade. Um
teste de reaproveitamento montado assim passou no dia em que foi escrito e
passou a falhar no dia seguinte, quando aquelas entradas viraram "anteriores"
ao projeto recem-criado.

Teste le fonte de teste. Nada do repositorio real entra.
"""

import shutil
import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


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


class RepoTestCase(unittest.TestCase):
    """CLI real no processo de teste, com todas as fontes isoladas."""

    def setUp(self):
        from scripts import central_compras as cc
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        self.root = Path(stack.enter_context(tempfile.TemporaryDirectory()))
        montar(self.root)
        directories = {
            key: getattr(cc, key).relative_to(cc.ROOT)
            for key in ("ROOT", "CONFIG", "PROJETOS", "PRODUTOS", "TEMPLATES",
                        "BASE", "VEREDITOS", "DASHBOARD")
        }
        for key, directory in directories.items():
            stack.enter_context(patch.object(cc, key, self.root / directory))
        stack.enter_context(patch.object(cc, "_PREFS_CACHE", {}))

    def cli(self, *argv):
        from scripts import central_compras as cc
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            cc.main(list(argv))
        return output.getvalue()

    def project(self, name="auditoria", category="fone", value=400):
        from scripts import central_compras as cc
        self.cli("novo-projeto", name, "--categoria", category,
                 "--valor-estimado", str(value))
        return cc.PROJETOS / f"{cc.today()[:4]}-{cc.slugify(name)}"

    def product(self, project, pid="candidato"):
        self.cli("novo-produto", str(project), pid, "--produto-id", pid,
                 "--marca", "Marca A", "--requisito", "uso=true")

    def quote(self, project, pid="candidato", *extra):
        self.cli("cotar", str(project), "--produto-id", pid, "--loja", "Amazon",
                 "--vendedor", "V", "--vendedor-tipo", "oficial", "--preco", "200",
                 "--nota", "4.8", "--avaliacoes", "1000", "--frete-prazo-dias", "2",
                 "--garantia-tipo", "nacional", "--garantia-meses", "12",
                 "--link", "https://example.invalid/item", "--fonte", "web", *extra)
