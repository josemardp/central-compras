"""Comportamento sob entrada quebrada e interrupcao.

Um sistema de memoria de compra e usado por anos, de varias maquinas, com
arquivo editado a mao. O que ele faz quando o dado esta torto importa tanto
quanto o que ele faz no caminho feliz.
"""

import csv
import datetime as dt
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import ambiente
from scripts import central_compras as cc


ROOT = Path(__file__).resolve().parents[1]
ANO = dt.date.today().year


class AtomicWriteTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="central-compras-atomic-"))

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_interrupted_write_does_not_destroy_the_ledger(self):
        """Abrir em modo `w` truncava o arquivo antes de gravar."""
        alvo = self.tmpdir / "cotacoes.csv"
        cc.write_quotes(self.tmpdir, [
            {"data_coleta": "2026-01-01", "produto_id": "a", "custo_total": "100"},
            {"data_coleta": "2026-02-01", "produto_id": "a", "custo_total": "90"},
        ])
        antes = alvo.read_text(encoding="utf-8")

        original = csv.DictWriter.writerow

        def explode(self, row):
            raise KeyboardInterrupt("Ctrl+C no meio da gravacao")

        csv.DictWriter.writerow = explode
        try:
            with self.assertRaises(KeyboardInterrupt):
                cc.write_quotes(self.tmpdir, cc.read_quotes(self.tmpdir))
        finally:
            csv.DictWriter.writerow = original

        self.assertEqual(alvo.read_text(encoding="utf-8"), antes, "serie historica foi perdida")

    def test_interrupted_write_leaves_no_temp_file_behind(self):
        alvo = self.tmpdir / "produto.yaml"
        cc.write_yaml(alvo, {"id": "a"})
        try:
            cc.atomic_write_text(alvo, None)  # type: ignore[arg-type]
        except Exception:
            pass
        self.assertEqual(list(self.tmpdir.glob(".*tmp")), [])
        self.assertEqual(cc.read_yaml(alvo), {"id": "a"})

    def test_write_yaml_is_reversible(self):
        alvo = self.tmpdir / "p.yaml"
        dados = {"id": "x", "atributos": {"cor": "preto"}, "preco_alvo": 260.0}
        cc.write_yaml(alvo, dados)
        self.assertEqual(cc.read_yaml(alvo), dados)


class CorruptInputTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="central-compras-corrupt-"))

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_broken_yaml_gives_a_readable_error_not_a_traceback(self):
        ruim = self.tmpdir / "produto.yaml"
        ruim.write_text("id: a\natributos: [nao\n  fecha\n", encoding="utf-8")
        with self.assertRaises(SystemExit) as ctx:
            cc.read_yaml(ruim)
        mensagem = str(ctx.exception)
        self.assertIn("YAML invalido", mensagem)
        self.assertIn("produto.yaml", mensagem)


class CollectionDateTest(unittest.TestCase):
    def test_accepts_the_documented_formats(self):
        self.assertTrue(cc.iso_datetime("2026-08-26").startswith("2026-08-26"))
        self.assertTrue(cc.iso_datetime("2026-08-26T13:48:20").startswith("2026-08-26T13:48"))

    def test_rejects_a_date_it_cannot_parse(self):
        import argparse
        for ruim in ["ontem", "26/08/2026", "amanha cedo", ""]:
            with self.assertRaises(argparse.ArgumentTypeError, msg=ruim):
                cc.iso_datetime(ruim)

    def test_a_broken_date_would_escape_every_date_guard(self):
        # Por isso a data e barrada na entrada e reclamada na validacao.
        podre = {"data_coleta": "ontem", "fonte": "manual"}
        self.assertIsNone(cc.quote_age_days(podre))
        self.assertFalse(cc.quote_is_stale(podre))
        self.assertFalse(cc.valid_collection_date("ontem"))
        self.assertTrue(cc.valid_collection_date("2026-08-26T13:48:20"))


class ProductCeilingTest(unittest.TestCase):
    def _row(self, custo):
        return {
            "custo_total": str(custo), "nota": "4.6", "n_avaliacoes": "900",
            "garantia_tipo": "nacional", "garantia_meses": "12", "vendedor_tipo": "oficial",
        }

    def test_product_ceiling_is_enforced_even_when_lower_than_the_briefing(self):
        produto = {"categoria": "fone", "estado": "pesquisando", "preco_teto": 300, "requisitos_atendidos": {}}
        cortes = cc.gate_eliminations(self._row(500), produto, {"categoria": "fone", "preco_teto": 600})
        self.assertTrue(any("preco_teto do produto" in c for c in cortes))

    def test_briefing_ceiling_still_applies(self):
        produto = {"categoria": "fone", "estado": "pesquisando", "requisitos_atendidos": {}}
        cortes = cc.gate_eliminations(self._row(700), produto, {"categoria": "fone", "preco_teto": 600})
        self.assertTrue(any("preco_teto do briefing" in c for c in cortes))

    def test_within_both_ceilings_passes(self):
        produto = {"categoria": "fone", "estado": "pesquisando", "preco_teto": 300, "requisitos_atendidos": {}}
        cortes = cc.gate_eliminations(self._row(280), produto, {"categoria": "fone", "preco_teto": 600})
        self.assertFalse(any("preco_teto" in c for c in cortes))


class WaitingPriceTest(unittest.TestCase):
    def test_waiting_product_above_target_is_flagged(self):
        produto = {"estado": "aguardando_preco", "preco_alvo": 260, "aguardando_preco_desde": "2026-08-26"}
        aviso = cc.waiting_gap(produto, {"custo_total": "296.64"})
        self.assertIn("faltam R$ 36,64", aviso)

    def test_waiting_product_that_hit_the_target_says_so(self):
        produto = {"estado": "aguardando_preco", "preco_alvo": 300, "aguardando_preco_desde": "2026-08-26"}
        aviso = cc.waiting_gap(produto, {"custo_total": "296.64"})
        self.assertIn("ALVO FOI ATINGIDO", aviso)

    def test_ordinary_product_gets_no_warning(self):
        self.assertEqual(cc.waiting_gap({"estado": "pesquisando"}, {"custo_total": "100"}), "")


class PromoteQuoteTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="central-compras-promote-"))
        ambiente.montar(self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def run_cli(self, *args, check=True):
        return subprocess.run(
            [sys.executable, "scripts/central_compras.py", *args],
            cwd=self.tmpdir, text=True, capture_output=True, check=check,
        )

    def test_manual_confirmation_does_not_inherit_the_web_suspicion_flag(self):
        self.run_cli("novo-projeto", "fone flag", "--categoria", "fone",
                     "--valor-estimado", "400", "--preco-teto", "600")
        project = f"projetos/{ANO}-fone-flag"
        self.run_cli("novo-produto", project, "Fone A", "--marca", "M",
                     "--categoria", "fone", "--produto-id", "fone-a",
                     "--requisito", "uso=true")
        self.run_cli("cotar", project, "--produto-id", "fone-a", "--loja", "Amazon",
                     "--vendedor", "V", "--vendedor-tipo", "oficial", "--preco", "299",
                     "--nota", "4.6", "--avaliacoes", "900", "--garantia-meses", "12",
                     "--garantia-tipo", "nacional", "--fonte", "web",
                     "--link", "https://ex.com/a", "--flag-suspeita", "AVAL_SUSPEITA")
        self.run_cli("promover-cotacao", project, "--produto-id", "fone-a", "--preco", "289")

        with (self.tmpdir / project / "cotacoes.csv").open(encoding="utf-8", newline="") as f:
            linhas = list(csv.DictReader(f))
        web = next(l for l in linhas if l["fonte"] == "web")
        manual = next(l for l in linhas if l["fonte"] == "manual")
        self.assertEqual(web["flag_suspeita"], "AVAL_SUSPEITA", "a linha web preserva o que foi observado")
        self.assertEqual(manual["flag_suspeita"], "", "a conferencia manual e observacao nova")

    def test_cli_refuses_an_unparseable_collection_date(self):
        self.run_cli("novo-projeto", "fone data", "--categoria", "fone", "--valor-estimado", "400")
        project = f"projetos/{ANO}-fone-data"
        self.run_cli("novo-produto", project, "Fone A", "--marca", "M",
                     "--categoria", "fone", "--produto-id", "fone-a",
                     "--requisito", "uso=true")
        resultado = self.run_cli("cotar", project, "--produto-id", "fone-a", "--loja", "Amazon",
                                 "--vendedor", "V", "--vendedor-tipo", "oficial", "--preco", "299",
                                 "--nota", "4.6", "--avaliacoes", "900", "--garantia-meses", "12",
                                 "--garantia-tipo", "nacional", "--fonte", "manual",
                                 "--link", "https://ex.com/a", "--data", "ontem", check=False)
        self.assertNotEqual(resultado.returncode, 0)
        self.assertIn("data invalida", resultado.stderr)

    def test_deciding_on_a_product_still_waiting_for_a_better_price_is_blocked(self):
        self.run_cli("novo-projeto", "fone espera", "--categoria", "fone",
                     "--valor-estimado", "400", "--preco-teto", "600")
        project = f"projetos/{ANO}-fone-espera"
        self.run_cli("novo-produto", project, "Fone A", "--marca", "M",
                     "--categoria", "fone", "--produto-id", "fone-a",
                     "--requisito", "uso=true")
        self.run_cli("cotar", project, "--produto-id", "fone-a", "--loja", "Amazon",
                     "--vendedor", "V", "--vendedor-tipo", "oficial", "--preco", "349",
                     "--nota", "4.6", "--avaliacoes", "900", "--garantia-meses", "12",
                     "--garantia-tipo", "nacional", "--fonte", "manual", "--link", "https://ex.com/a")
        self.run_cli("aguardar-preco", "--produto-id", "fone-a", "--projeto", project,
                     "--preco-alvo", "260", "--porque", "Caro demais agora.")

        bloqueado = self.run_cli("decidir", project, "--produto-id", "fone-a",
                                 "--porque", "Comprando.", check=False)
        self.assertNotEqual(bloqueado.returncode, 0)
        self.assertIn("aguardando_preco", bloqueado.stderr)

        # Declarando que mudou de ideia, fecha.
        self.run_cli("decidir", project, "--produto-id", "fone-a",
                     "--porque", "Mudei de ideia, preciso agora.", "--permitir-aguardando")


if __name__ == "__main__":
    unittest.main()
