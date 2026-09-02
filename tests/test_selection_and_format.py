"""Escolha da cotacao, idempotencia, edicao de config e formato de dinheiro.

Sao quatro jeitos diferentes de o sistema estar tecnicamente funcionando e
ainda assim entregar a resposta errada para quem le.
"""

import datetime as dt
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

import ambiente
from scripts import central_compras as cc


ROOT = Path(__file__).resolve().parents[1]
ANO = dt.date.today().year


class QuoteSelectionTest(unittest.TestCase):
    """Qual cotacao representa o produto no ranking."""

    def linha(self, fonte, dias_atras, custo, **extras):
        data = (dt.date.today() - dt.timedelta(days=dias_atras)).isoformat()
        return {"produto_id": "p", "fonte": fonte, "data_coleta": data, "custo_total": str(custo), **extras}

    def test_fresh_manual_beats_fresh_web(self):
        escolhida = cc.latest_quotes([self.linha("web", 0, 400), self.linha("manual", 1, 420)])["p"]
        self.assertEqual(escolhida["fonte"], "manual", "manual foi conferida, deve prevalecer")

    def test_expired_manual_loses_to_a_fresh_observation(self):
        """Preferir manual cegamente fazia preco de dois anos atras rankear."""
        antiga = self.linha("manual", 900, 900)
        nova = self.linha("web", 0, 400)
        escolhida = cc.latest_quotes([antiga, nova])["p"]
        self.assertEqual(escolhida["fonte"], "web")
        self.assertEqual(escolhida["custo_total"], "400")

    def test_when_everything_is_expired_the_manual_still_wins(self):
        escolhida = cc.latest_quotes([self.linha("web", 400, 400), self.linha("manual", 500, 900)])["p"]
        self.assertEqual(escolhida["fonte"], "manual")

    def test_the_most_recent_of_two_fresh_manuals_wins(self):
        escolhida = cc.latest_quotes([self.linha("manual", 5, 500), self.linha("manual", 1, 450)])["p"]
        self.assertEqual(escolhida["custo_total"], "450")

    def test_gate_passing_quote_beats_later_same_day_quote_inside_same_priority(self):
        boa = self.linha("manual", 0, 329.63, garantia_tipo="nacional", loja="Mercado Livre")
        ruim = self.linha("manual", 0, 253.71, garantia_tipo="nenhuma", loja="Amazon")

        escolhida = cc.latest_quotes(
            [boa, ruim],
            prefer=lambda row: row.get("garantia_tipo") in {"nacional", "vendedor"},
        )["p"]

        self.assertEqual(escolhida["loja"], "Mercado Livre")
        self.assertEqual(escolhida["garantia_tipo"], "nacional")

    def test_cheaper_quote_breaks_tie_when_multiple_preferred_quotes_have_same_date(self):
        cara = self.linha("manual", 0, 340, garantia_tipo="nacional", loja="Loja A")
        barata = self.linha("manual", 0, 310, garantia_tipo="vendedor", loja="Loja B")

        escolhida = cc.latest_quotes(
            [cara, barata],
            prefer=lambda row: row.get("garantia_tipo") in {"nacional", "vendedor"},
        )["p"]

        self.assertEqual(escolhida["loja"], "Loja B")
        self.assertEqual(escolhida["custo_total"], "310")


class BrlFormatTest(unittest.TestCase):
    def test_formats_like_a_brazilian_reads_money(self):
        self.assertEqual(cc.brl(1234.5), "R$ 1.234,50")
        self.assertEqual(cc.brl("296.64"), "R$ 296,64")
        self.assertEqual(cc.brl(1000000), "R$ 1.000.000,00")
        self.assertEqual(cc.brl(0.5), "R$ 0,50")

    def test_handles_empty_and_negative(self):
        self.assertEqual(cc.brl(None), "-")
        self.assertEqual(cc.brl(""), "-")
        self.assertEqual(cc.brl("", vazio=""), "")
        self.assertEqual(cc.brl(-50), "-R$ 50,00")

    def test_does_not_mangle_something_that_is_not_a_number(self):
        self.assertEqual(cc.brl("a combinar"), "a combinar")


class CategoryGateEditTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="central-compras-gate-"))
        self.path = self.tmpdir / "categorias.yaml"

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def escrever(self, texto):
        self.path.write_text(texto, encoding="utf-8")

    def test_editing_a_gate_keeps_hand_written_comments(self):
        """Um safe_dump do arquivo inteiro apagava toda explicacao escrita a mao."""
        self.escrever(
            "# arquivo de categorias\n"
            "fone:\n"
            "  # esse gate nasceu de uma compra ruim em 2025\n"
            "  gate:\n"
            "    minimo_avaliacoes: 150\n"
            "\n"
            "tenis:\n"
            "  gate:\n"
            "    nota_minima_ajustada: 4.2\n"
        )
        cc.set_category_gate(self.path, "fone", "minimo_avaliacoes", 200)
        texto = self.path.read_text(encoding="utf-8")

        self.assertIn("# arquivo de categorias", texto)
        self.assertIn("esse gate nasceu de uma compra ruim", texto)
        self.assertIn("minimo_avaliacoes: 200", texto)
        dados = yaml.safe_load(texto)
        self.assertEqual(dados["fone"]["gate"]["minimo_avaliacoes"], 200)
        self.assertEqual(dados["tenis"]["gate"]["nota_minima_ajustada"], 4.2)

    def test_adds_a_new_field_to_an_existing_gate(self):
        self.escrever("fone:\n  gate:\n    minimo_avaliacoes: 150\n")
        cc.set_category_gate(self.path, "fone", "exige_vendedor_oficial", True)
        dados = yaml.safe_load(self.path.read_text(encoding="utf-8"))
        self.assertIs(dados["fone"]["gate"]["exige_vendedor_oficial"], True)
        self.assertEqual(dados["fone"]["gate"]["minimo_avaliacoes"], 150)

    def test_creates_the_gate_block_when_the_category_has_none(self):
        self.escrever("fone:\n  atributos_obrigatorios:\n    - tipo\n")
        cc.set_category_gate(self.path, "fone", "minimo_avaliacoes", 150)
        dados = yaml.safe_load(self.path.read_text(encoding="utf-8"))
        self.assertEqual(dados["fone"]["gate"]["minimo_avaliacoes"], 150)
        self.assertEqual(dados["fone"]["atributos_obrigatorios"], ["tipo"])

    def test_creates_a_brand_new_category(self):
        self.escrever("fone:\n  gate:\n    minimo_avaliacoes: 150\n")
        cc.set_category_gate(self.path, "bicicleta", "exige_vendedor_oficial", True)
        dados = yaml.safe_load(self.path.read_text(encoding="utf-8"))
        self.assertIs(dados["bicicleta"]["gate"]["exige_vendedor_oficial"], True)
        self.assertEqual(dados["fone"]["gate"]["minimo_avaliacoes"], 150)


class VerdictIdempotencyTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="central-compras-idem-"))
        ambiente.montar(self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def run_cli(self, *args, check=True):
        return subprocess.run(
            [sys.executable, "scripts/central_compras.py", *args],
            cwd=self.tmpdir, text=True, capture_output=True, check=check,
        )

    def preparar_veredito(self):
        self.run_cli("novo-projeto", "fone idem", "--categoria", "fone",
                     "--valor-estimado", "400", "--preco-teto", "600")
        project = f"projetos/{ANO}-fone-idem"
        self.run_cli("novo-produto", project, "Fone A", "--marca", "MarcaUnica",
                     "--categoria", "fone", "--produto-id", "fone-a",
                     "--requisito", "uso=true")
        self.run_cli("cotar", project, "--produto-id", "fone-a", "--loja", "Amazon",
                     "--vendedor", "V", "--vendedor-tipo", "oficial", "--preco", "299",
                     "--nota", "4.6", "--avaliacoes", "900", "--garantia-meses", "12",
                     "--garantia-tipo", "nacional", "--fonte", "manual", "--link", "https://ex.com/a")
        self.run_cli("decidir", project, "--produto-id", "fone-a", "--porque", "Escolhido.")
        veredito = next((self.tmpdir / "vereditos").glob("*fone-a.md"))
        self.run_cli("preencher-veredito", str(veredito), "--fase", "d30",
                     "--nota-arrependimento", "1", "--compraria-de-novo", "sim",
                     "--resumo", "Chegou certo.")
        return veredito

    def test_exporting_the_same_verdict_twice_is_refused(self):
        """A base alimenta o prompt-ia: entrada duplicada conta o aprendizado dobrado."""
        veredito = self.preparar_veredito()
        self.run_cli("aprender-veredito", str(veredito))
        segunda = self.run_cli("aprender-veredito", str(veredito), check=False)

        self.assertNotEqual(segunda.returncode, 0)
        self.assertIn("ja foi exportado", segunda.stderr)
        marca = (self.tmpdir / "base-conhecimento" / "marcas" / "marcaunica.md").read_text(encoding="utf-8")
        self.assertEqual(marca.count("- Tipo: marca"), 1)

    def test_force_allows_a_deliberate_re_export(self):
        veredito = self.preparar_veredito()
        self.run_cli("aprender-veredito", str(veredito))
        self.run_cli("aprender-veredito", str(veredito), "--force")
        marca = (self.tmpdir / "base-conhecimento" / "marcas" / "marcaunica.md").read_text(encoding="utf-8")
        self.assertEqual(marca.count("- Tipo: marca"), 2)

    def test_d30_does_not_block_the_later_d180_learning(self):
        veredito = self.preparar_veredito()
        self.run_cli("aprender-veredito", str(veredito), "--fase", "d30")
        self.run_cli(
            "preencher-veredito", str(veredito), "--fase", "d180",
            "--nota-arrependimento", "0", "--compraria-de-novo", "sim",
            "--resumo", "Continua funcionando depois de seis meses.",
            "--o-que-aprendi", "Durabilidade confirmou a escolha.",
            "--ainda-usa", "sim", "--valeu-o-que-pagou", "sim",
        )
        self.run_cli("aprender-veredito", str(veredito), "--fase", "d180")

        texto = veredito.read_text(encoding="utf-8")
        self.assertIn("## Aprendizado exportado D+30", texto)
        self.assertIn("## Aprendizado exportado D+180", texto)
        marca = (self.tmpdir / "base-conhecimento" / "marcas" / "marcaunica.md").read_text(encoding="utf-8")
        self.assertEqual(marca.count("- Tipo: marca"), 2)
        licoes = (self.tmpdir / "base-conhecimento" / "licoes.md").read_text(encoding="utf-8")
        self.assertIn("Durabilidade confirmou a escolha", licoes)


class DecisionIntegrityTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="central-compras-dec-"))
        ambiente.montar(self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def run_cli(self, *args, check=True):
        return subprocess.run(
            [sys.executable, "scripts/central_compras.py", *args],
            cwd=self.tmpdir, text=True, capture_output=True, check=check,
        )

    def test_the_winner_cannot_be_listed_as_its_own_loser(self):
        self.run_cli("novo-projeto", "fone self", "--categoria", "fone", "--valor-estimado", "400")
        project = f"projetos/{ANO}-fone-self"
        self.run_cli("novo-produto", project, "Fone A", "--marca", "M",
                     "--categoria", "fone", "--produto-id", "fone-a",
                     "--requisito", "uso=true")
        self.run_cli("cotar", project, "--produto-id", "fone-a", "--loja", "Amazon",
                     "--vendedor", "V", "--vendedor-tipo", "oficial", "--preco", "299",
                     "--nota", "4.6", "--avaliacoes", "900", "--garantia-meses", "12",
                     "--garantia-tipo", "nacional", "--fonte", "manual", "--link", "https://ex.com/a")
        resultado = self.run_cli("decidir", project, "--produto-id", "fone-a",
                                 "--porque", "Escolhido.",
                                 "--perdedores", "fone-a: eu mesmo", check=False)
        self.assertNotEqual(resultado.returncode, 0)
        self.assertIn("nao pode constar como perdedor", resultado.stderr)


if __name__ == "__main__":
    unittest.main()
