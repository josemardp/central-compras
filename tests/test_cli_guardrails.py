"""Travas de processo na linha de comando.

Cada teste aqui corresponde a um jeito de fechar uma compra mal e o sistema
deixar passar calado.
"""

import datetime as dt
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import ambiente


ROOT = Path(__file__).resolve().parents[1]
ANO = dt.date.today().year


class CliGuardrailsTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="central-compras-guard-"))
        ambiente.montar(self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def run_cli(self, *args, check=True):
        return subprocess.run(
            [sys.executable, "scripts/central_compras.py", *args],
            cwd=self.tmpdir,
            text=True,
            capture_output=True,
            check=check,
        )

    def montar_projeto_com_dois_candidatos(self):
        self.run_cli("novo-projeto", "fone guardrail", "--categoria", "fone",
                     "--valor-estimado", "400", "--preco-teto", "600")
        project = f"projetos/{ANO}-fone-guardrail"
        for produto_id, nome, preco in [("fone-a", "Fone A", "299"), ("fone-b", "Fone B", "399")]:
            self.run_cli("novo-produto", project, nome, "--marca", "MarcaX",
                         "--categoria", "fone", "--produto-id", produto_id,
                         "--requisito", "chamadas=true")
            self.run_cli("cotar", project, "--produto-id", produto_id, "--loja", "Amazon",
                         "--vendedor", "Loja oficial", "--vendedor-tipo", "oficial",
                         "--preco", preco, "--frete", "0", "--frete-prazo-dias", "3",
                         "--nota", "4.6", "--avaliacoes", "1200", "--garantia-meses", "12",
                         "--garantia-tipo", "nacional", "--fonte", "manual",
                         "--link", f"https://exemplo.com/{produto_id}")
        return project

    def test_decision_refuses_to_close_without_saying_why_the_others_lost(self):
        project = self.montar_projeto_com_dois_candidatos()
        result = self.run_cli("decidir", project, "--produto-id", "fone-a",
                              "--porque", "Mais barato e mesma nota.", check=False)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("fone-b", result.stderr)
        self.assertFalse((self.tmpdir / project / "decisao.md").read_text(encoding="utf-8").count("Fone A"))

    def test_decision_closes_when_the_loser_is_documented(self):
        project = self.montar_projeto_com_dois_candidatos()
        self.run_cli("decidir", project, "--produto-id", "fone-a",
                     "--porque", "Mais barato com a mesma nota e garantia.",
                     "--perdedores", "fone-b: R$ 100 mais caro sem ganho de garantia.",
                     "--comprado")
        decisao = (self.tmpdir / project / "decisao.md").read_text(encoding="utf-8")

        self.assertIn("Fone A", decisao)
        self.assertIn("R$ 100 mais caro", decisao)

    def test_decision_rejects_a_loser_id_that_does_not_exist(self):
        project = self.montar_projeto_com_dois_candidatos()
        result = self.run_cli("decidir", project, "--produto-id", "fone-a",
                              "--porque", "Escolha.",
                              "--perdedores", "fone-bb: id digitado errado",
                              check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("nao existe", result.stderr)

    def test_decision_blocks_a_stale_quote(self):
        project = self.montar_projeto_com_dois_candidatos()
        csv_path = self.tmpdir / project / "cotacoes.csv"
        antigo = csv_path.read_text(encoding="utf-8").replace(str(ANO) + "-", "2019-", 1)
        csv_path.write_text(antigo, encoding="utf-8", newline="")

        result = self.run_cli("decidir", project, "--produto-id", "fone-a",
                              "--porque", "Escolha.",
                              "--perdedores", "fone-b: mais caro.", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("dias", result.stderr)

        # Com a trava liberada de proposito, fecha.
        self.run_cli("decidir", project, "--produto-id", "fone-a",
                     "--porque", "Escolha.", "--perdedores", "fone-b: mais caro.",
                     "--permitir-vencida")

    def test_verdict_is_prefilled_so_learning_can_be_exported(self):
        project = self.montar_projeto_com_dois_candidatos()
        self.run_cli("decidir", project, "--produto-id", "fone-a",
                     "--porque", "Melhor custo.",
                     "--perdedores", "fone-b: mais caro.", "--comprado")
        veredito = next((self.tmpdir / "vereditos").glob("*fone-a.md"))
        texto = veredito.read_text(encoding="utf-8")

        self.assertIn("- Marca: MarcaX", texto)
        self.assertIn("- Loja: Amazon", texto)
        self.assertIn("- Categoria: fone", texto)

        # Sem --marca/--loja na linha de comando, o aprendizado ainda sai.
        self.run_cli("preencher-veredito", str(veredito), "--fase", "d30",
                     "--nota-arrependimento", "1", "--compraria-de-novo", "sim",
                     "--resumo", "Chegou certo.")
        self.run_cli("aprender-veredito", str(veredito))
        self.assertTrue((self.tmpdir / "base-conhecimento" / "marcas" / "marcax.md").exists())

    def test_history_command_exposes_the_price_series(self):
        project = self.montar_projeto_com_dois_candidatos()
        self.run_cli("cotar", project, "--produto-id", "fone-a", "--loja", "Amazon",
                     "--vendedor", "Loja oficial", "--vendedor-tipo", "oficial",
                     "--preco", "249", "--nota", "4.6", "--avaliacoes", "1200",
                     "--garantia-meses", "12", "--garantia-tipo", "nacional",
                     "--fonte", "manual", "--link", "https://exemplo.com/fone-a",
                     "--data", f"{ANO}-01-05T10:00:00")
        result = self.run_cli("historico", project, "--produto-id", "fone-a")
        historico = (self.tmpdir / project / "historico.md").read_text(encoding="utf-8")

        self.assertIn("2 obs", result.stdout)
        self.assertIn("249", historico)
        self.assertIn("299", historico)

    def test_stop_rule_is_written_into_the_briefing(self):
        self.run_cli("novo-projeto", "carro caro", "--categoria", "carro",
                     "--valor-estimado", "150000", "--preco-teto", "180000")
        briefing = (self.tmpdir / "projetos" / f"{ANO}-carro-caro" / "briefing.md").read_text(encoding="utf-8")

        self.assertIn("Faixa de valor: acima_20000", briefing)
        self.assertIn("30 dias", briefing)

    def test_migration_upgrades_an_old_csv_without_losing_data(self):
        project = self.montar_projeto_com_dois_candidatos()
        csv_path = self.tmpdir / project / "cotacoes.csv"
        linhas = csv_path.read_text(encoding="utf-8").splitlines()
        # Volta ao schema antigo, sem as colunas de TCO.
        header = linhas[0].split(",")
        manter = [i for i, c in enumerate(header) if not c.startswith("tco") and "operacional" not in c and "revenda" not in c]
        recorte = [",".join([linha.split(",")[i] for i in manter]) for linha in linhas]
        csv_path.write_text("\n".join(recorte) + "\n", encoding="utf-8", newline="")

        result = self.run_cli("migrar-cotacoes", "--projeto", project)
        depois = csv_path.read_text(encoding="utf-8")

        self.assertIn("tco_total", depois)
        self.assertIn("fone-a", depois)
        self.assertIn("fone-b", depois)
        self.assertIn("colunas adicionadas", result.stdout)

    def test_private_data_dir_lives_outside_the_repository(self):
        result = self.run_cli("dados-privados")
        destino = Path(result.stdout.splitlines()[0].strip())

        self.assertTrue(destino.exists())
        self.assertNotIn(str(self.tmpdir), str(destino))
        self.assertIn("dados-privados", str(destino))


if __name__ == "__main__":
    unittest.main()
