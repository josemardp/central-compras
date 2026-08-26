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
            "--link",
            "https://example.com/qcy-h3",
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
            "--link",
            "https://example.com/qcy-x",
        )
        self.run_cli("descartar", "--produto-id", "qcy-x", "--projeto", project, "--porque", "Microfone sem confiabilidade.")
        self.run_cli("ranking", project)
        validacao = self.run_cli("validar", project)
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
        ranking_csv = (self.tmpdir / project / "ranking.csv").read_text(encoding="utf-8")
        processo = (self.tmpdir / project / "processo.md").read_text(encoding="utf-8")
        decisao = (self.tmpdir / project / "decisao.md").read_text(encoding="utf-8")
        validacao_md = (self.tmpdir / project / "validacao.md").read_text(encoding="utf-8")
        vereditos = list((self.tmpdir / "vereditos").glob("*qcy-h3.md"))

        self.assertIn("QCY H3", ranking)
        self.assertIn("qualidade", ranking)
        self.assertIn("qcy-x", ranking_csv)
        self.assertIn("produto descartado", ranking_csv)
        self.assertIn("Pesquisar headphone over-ear", processo)
        self.assertIn("Descartado qcy-x", processo)
        self.assertIn("Cotacao manual confirmada", decisao)
        self.assertIn("Avisos:", validacao.stdout)
        self.assertIn("atributos obrigatorios ausentes", validacao_md)
        self.assertIn("Escolhido: QCY H3", resumo.stdout)
        self.assertIn("Estado: comprado", status.stdout)
        self.assertTrue(vereditos)

    def test_tco_changes_value_axis_for_car_project(self):
        self.run_cli(
            "novo-projeto",
            "carro eletrico teste",
            "--categoria",
            "carro",
            "--valor-estimado",
            "150000",
            "--preco-teto",
            "180000",
        )
        project = "projetos/2026-carro-eletrico-teste"
        self.run_cli(
            "novo-produto",
            project,
            "Carro A",
            "--marca",
            "Marca A",
            "--categoria",
            "carro",
            "--produto-id",
            "carro-a",
            "--atributo",
            "motorizacao=eletrico",
            "--atributo",
            "autonomia_km=380",
            "--atributo",
            "potencia_cv=75",
            "--atributo",
            "porta_malas_l=230",
            "--atributo",
            "garantia_bateria=8 anos",
        )
        self.run_cli(
            "novo-produto",
            project,
            "Carro B",
            "--marca",
            "Marca B",
            "--categoria",
            "carro",
            "--produto-id",
            "carro-b",
            "--atributo",
            "motorizacao=hibrido",
            "--atributo",
            "autonomia_km=900",
            "--atributo",
            "potencia_cv=120",
            "--atributo",
            "porta_malas_l=300",
            "--atributo",
            "garantia_bateria=8 anos",
        )
        for produto_id, preco, mensal, revenda in [
            ("carro-a", "150000", "300", "85000"),
            ("carro-b", "145000", "900", "70000"),
        ]:
            self.run_cli(
                "cotar",
                project,
                "--produto-id",
                produto_id,
                "--loja",
                "Concessionaria",
                "--vendedor",
                "Loja",
                "--vendedor-tipo",
                "fisica",
                "--preco",
                preco,
                "--nota",
                "4.7",
                "--avaliacoes",
                "1000",
                "--garantia-meses",
                "36",
                "--garantia-tipo",
                "nacional",
                "--fonte",
                "manual",
                "--link",
                "https://example.com/carro",
                "--custo-operacional-mensal",
                mensal,
                "--valor-revenda-estimado",
                revenda,
            )
        self.run_cli("ranking", project)
        ranking = (self.tmpdir / project / "ranking.md").read_text(encoding="utf-8")
        ranking_csv = (self.tmpdir / project / "ranking.csv").read_text(encoding="utf-8")

        self.assertLess(ranking.index("Carro A"), ranking.index("Carro B"))
        self.assertIn("TCO 60 meses", ranking)
        self.assertIn("tco_total", ranking_csv)

    def test_knowledge_base_feeds_prompt_and_reuse_report(self):
        self.run_cli(
            "novo-projeto",
            "fone conhecimento teste",
            "--categoria",
            "fone",
            "--valor-estimado",
            "300",
            "--preco-teto",
            "500",
        )
        project = "projetos/2026-fone-conhecimento-teste"
        self.run_cli(
            "novo-produto",
            project,
            "QCY H3",
            "--marca",
            "QCY",
            "--categoria",
            "fone",
            "--produto-id",
            "qcy-h3",
            "--atributo",
            "tipo=headphone",
            "--atributo",
            "conexao=bluetooth",
            "--atributo",
            "microfone=true",
            "--atributo",
            "bateria_horas=70",
            "--atributo",
            "garantia_meses=12",
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
            "--link",
            "https://example.com/qcy-h3",
        )
        self.run_cli(
            "registrar-marca",
            "QCY",
            "--categoria",
            "fone",
            "--projeto",
            project,
            "--nota",
            "8",
            "--compraria-de-novo",
            "sim",
            "--resumo",
            "Bom custo-beneficio em fones baratos.",
        )
        self.run_cli(
            "registrar-loja",
            "Amazon",
            "--categoria",
            "fone",
            "--projeto",
            project,
            "--nota",
            "9",
            "--compraria-de-novo",
            "sim",
            "--resumo",
            "Entrega e devolucao costumam reduzir risco.",
        )
        self.run_cli(
            "registrar-licao",
            "Fone para chamada precisa ter relato explicito de microfone.",
            "--categoria",
            "fone",
        )
        prompt = self.run_cli("prompt-ia", project, "--etapa", "decisao")
        reuse = self.run_cli("reaproveitamento", "--categoria", "fone")

        self.assertIn("Bom custo-beneficio", prompt.stdout)
        self.assertIn("Entrega e devolucao", prompt.stdout)
        self.assertIn("relato explicito de microfone", prompt.stdout)
        self.assertIn("Taxa:", reuse.stdout)
        self.assertTrue((self.tmpdir / "base-conhecimento" / "reaproveitamento.md").exists())

    def test_waiting_price_and_verdict_learning_flow(self):
        self.run_cli(
            "novo-projeto",
            "fone veredito teste",
            "--categoria",
            "fone",
            "--valor-estimado",
            "500",
            "--preco-teto",
            "600",
        )
        project = "projetos/2026-fone-veredito-teste"
        self.run_cli(
            "novo-produto",
            project,
            "QCY H3",
            "--marca",
            "QCY",
            "--categoria",
            "fone",
            "--produto-id",
            "qcy-h3",
            "--preco-alvo",
            "260",
            "--preco-teto",
            "330",
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
            "349",
            "--nota",
            "4.7",
            "--avaliacoes",
            "900",
            "--garantia-meses",
            "12",
            "--garantia-tipo",
            "nacional",
            "--fonte",
            "manual",
            "--link",
            "https://example.com/qcy-h3",
        )
        self.run_cli(
            "aguardar-preco",
            "--produto-id",
            "qcy-h3",
            "--projeto",
            project,
            "--preco-alvo",
            "260",
            "--preco-teto",
            "330",
            "--porque",
            "Produto aprovado, mas acima do preco alvo.",
        )
        waiting = self.run_cli("listar-aguardando-preco", "--categoria", "fone")
        waiting_md = (self.tmpdir / "base-conhecimento" / "aguardando-preco.md").read_text(encoding="utf-8")
        product_yaml = (self.tmpdir / "produtos" / "fone" / "qcy-h3" / "produto.yaml").read_text(encoding="utf-8")

        self.assertIn("Itens: 1", waiting.stdout)
        self.assertIn("Produto aprovado", waiting_md)
        self.assertIn("estado: aguardando_preco", product_yaml)

        self.run_cli(
            "decidir",
            project,
            "--produto-id",
            "qcy-h3",
            "--porque",
            "Preco aceito para testar veredito.",
            "--comprado",
        )
        verdict = next((self.tmpdir / "vereditos").glob("*qcy-h3.md"))
        self.run_cli(
            "preencher-veredito",
            str(verdict),
            "--fase",
            "d30",
            "--nota-arrependimento",
            "1",
            "--compraria-de-novo",
            "sim",
            "--resumo",
            "Chegou certo e resolveu chamadas.",
            "--licao",
            "QCY H3 foi bom para chamada quando comprado de vendedor confiavel.",
        )
        self.run_cli(
            "aprender-veredito",
            str(verdict),
            "--marca",
            "QCY",
            "--loja",
            "Amazon",
            "--categoria",
            "fone",
        )
        learned = verdict.read_text(encoding="utf-8")
        lessons = (self.tmpdir / "base-conhecimento" / "licoes.md").read_text(encoding="utf-8")
        brand = (self.tmpdir / "base-conhecimento" / "marcas" / "qcy.md").read_text(encoding="utf-8")

        self.assertIn("Aprendizado exportado", learned)
        self.assertIn("QCY H3 foi bom", lessons)
        self.assertIn("Chegou certo", brand)

    def test_dashboard_generates_local_html_pages(self):
        self.run_cli(
            "novo-projeto",
            "fone dashboard teste",
            "--categoria",
            "fone",
            "--valor-estimado",
            "350",
            "--preco-teto",
            "500",
        )
        project = "projetos/2026-fone-dashboard-teste"
        self.run_cli(
            "novo-produto",
            project,
            "QCY H3",
            "--marca",
            "QCY",
            "--categoria",
            "fone",
            "--produto-id",
            "qcy-h3",
            "--atributo",
            "tipo=headphone",
            "--atributo",
            "conexao=bluetooth",
            "--atributo",
            "microfone=true",
            "--atributo",
            "bateria_horas=70",
            "--atributo",
            "garantia_meses=12",
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
            "--link",
            "https://example.com/qcy-h3",
        )
        self.run_cli("ranking", project)
        result = self.run_cli("dashboard")

        index = self.tmpdir / "dashboard" / "index.html"
        project_page = self.tmpdir / "dashboard" / "projetos" / "2026-fone-dashboard-teste.html"
        knowledge_page = self.tmpdir / "dashboard" / "base-conhecimento.html"
        styles = self.tmpdir / "dashboard" / "assets" / "styles.css"

        self.assertIn("dashboard\\index.html", result.stdout)
        self.assertTrue(index.exists())
        self.assertTrue(project_page.exists())
        self.assertTrue(knowledge_page.exists())
        self.assertTrue(styles.exists())
        self.assertIn("Central de Compras", index.read_text(encoding="utf-8"))
        self.assertIn("Aderencia ao gate", index.read_text(encoding="utf-8"))
        self.assertIn("dias medios ate decisao", index.read_text(encoding="utf-8"))
        self.assertIn("QCY H3", project_page.read_text(encoding="utf-8"))
        self.assertIn("Base de conhecimento", knowledge_page.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
