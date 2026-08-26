import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CliWorkflowTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="central-compras-test-"))
        for name in [
            "README.md",
            ".gitignore",
            "requirements.txt",
            "config",
            "templates",
            "base-conhecimento",
            "scripts",
        ]:
            src = ROOT / name
            dst = self.tmpdir / name
            if src.is_dir():
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, "scripts/central_compras.py", *args],
            cwd=self.tmpdir,
            text=True,
            capture_output=True,
            check=True,
        )

    def test_purchase_process_from_briefing_to_decision(self):
        self.run_cli(
            "novo-projeto",
            "fone chamadas teste",
            "--categoria",
            "fone",
            "--valor-estimado",
            "400",
            "--preco-teto",
            "600",
        )
        project = "projetos/2026-fone-chamadas-teste"
        self.run_cli(
            "anotar",
            project,
            "--etapa",
            "modelo",
            "--decisao",
            "Pesquisar headphone over-ear",
            "--porque",
            "Prioridade e chamada longa com conforto.",
        )
        self.run_cli(
            "novo-produto",
            project,
            "QCY H3",
            "--marca",
            "QCY",
            "--categoria",
            "fone",
            "--atributo",
            "tipo=headphone",
            "--atributo",
            "conexao=bluetooth",
            "--requisito",
            "chamadas=true",
        )
        self.run_cli(
            "novo-produto",
            project,
            "QCY X",
            "--marca",
            "QCY",
            "--categoria",
            "fone",
            "--produto-id",
            "qcy-x",
        )
        self.run_cli(
            "cotar",
            project,
            "--produto-id",
            "qcy-h3",
            "--loja",
            "Amazon",
            "--vendedor",
            "Loja oficial",
            "--vendedor-tipo",
            "oficial",
            "--preco",
            "299",
            "--frete",
            "0",
            "--frete-prazo-dias",
            "3",
            "--nota",
            "4.6",
            "--avaliacoes",
            "1200",
            "--garantia-meses",
            "12",
            "--garantia-tipo",
            "nacional",
            "--fonte",
            "manual",
        )
        self.run_cli(
            "cotar",
            project,
            "--produto-id",
            "qcy-x",
            "--loja",
            "Marketplace",
            "--vendedor",
            "Vendedor X",
            "--vendedor-tipo",
            "terceiro",
            "--preco",
            "199",
            "--nota",
            "4.1",
            "--avaliacoes",
            "50",
            "--garantia-tipo",
            "nenhuma",
            "--fonte",
            "web",
        )
        self.run_cli(
            "promover-cotacao",
            project,
            "--produto-id",
            "qcy-x",
            "--preco",
            "189",
            "--frete",
            "10",
            "--nota",
            "4.4",
            "--avaliacoes",
            "200",
            "--garantia-meses",
            "12",
            "--garantia-tipo",
            "vendedor",
        )
        self.run_cli("descartar", "--produto-id", "qcy-x", "--projeto", project, "--porque", "Microfone sem confiabilidade.")
        self.run_cli("ranking", project)
        self.run_cli(
            "decidir",
            project,
            "--produto-id",
            "qcy-h3",
            "--porque",
            "Cotacao manual confirmada e atende chamadas.",
            "--comprado",
        )
        resumo = self.run_cli("resumo", project)
        status = self.run_cli("status", project)

        ranking = (self.tmpdir / project / "ranking.md").read_text(encoding="utf-8")
        processo = (self.tmpdir / project / "processo.md").read_text(encoding="utf-8")
        decisao = (self.tmpdir / project / "decisao.md").read_text(encoding="utf-8")
        vereditos = list((self.tmpdir / "vereditos").glob("*qcy-h3.md"))

        self.assertIn("QCY H3", ranking)
        self.assertIn("qualidade", ranking)
        self.assertIn("Pesquisar headphone over-ear", processo)
        self.assertIn("Descartado qcy-x", processo)
        self.assertIn("Cotacao manual confirmada", decisao)
        self.assertIn("Escolhido: QCY H3", resumo.stdout)
        self.assertIn("Estado: comprado", status.stdout)
        self.assertTrue(vereditos)


if __name__ == "__main__":
    unittest.main()
