"""Relatorios e prompts precisam informar, nao so existir.

Config declarada e nunca lida, prompt que despeja CSV cru e metrica que mede a
si mesma sao tres jeitos de o sistema parecer completo sem ser.
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


class PreferredStoreTest(unittest.TestCase):
    def test_preferred_store_matches_across_spelling(self):
        # `Mercado Livre` na config tem que casar com `MercadoLivre` no CSV.
        self.assertTrue(cc.preferred_store("MercadoLivre"))
        self.assertTrue(cc.preferred_store("Mercado Livre"))
        self.assertTrue(cc.preferred_store("amazon"))

    def test_unknown_store_is_not_preferred(self):
        self.assertFalse(cc.preferred_store("Loja Desconhecida do Zap"))
        self.assertFalse(cc.preferred_store(""))
        self.assertFalse(cc.preferred_store(None))

    def test_preferred_store_lowers_risk(self):
        base = {"vendedor_tipo": "oficial", "garantia_tipo": "nacional", "garantia_meses": "12"}
        conhecida = cc.risk_score({**base, "loja": "Amazon"}, [])
        estranha = cc.risk_score({**base, "loja": "Loja Desconhecida do Zap"}, [])
        self.assertGreater(conhecida, estranha)


class ConfigCoverageTest(unittest.TestCase):
    def test_no_dead_config_in_preferences(self):
        """Chave de config que ninguem le e promessa que o sistema nao cumpre."""
        cfg = yaml.safe_load((ROOT / "config" / "preferencias.yaml").read_text(encoding="utf-8"))
        codigo = (ROOT / "scripts" / "central_compras.py").read_text(encoding="utf-8")
        # Blocos lidos dinamicamente por .items(): basta o nome do bloco aparecer.
        dinamicos = {"regras_parada", "marcas_vetadas", "lojas_preferidas", "score"}
        mortas = []

        def varre(bloco, prefixo=""):
            for chave, valor in (bloco or {}).items():
                if prefixo.rstrip(".") in dinamicos:
                    continue
                if f'"{chave}"' not in codigo:
                    mortas.append(f"{prefixo}{chave}")
                if isinstance(valor, dict):
                    varre(valor, f"{prefixo}{chave}.")

        varre(cfg)
        self.assertFalse(mortas, f"config declarada e nunca lida: {mortas}")


class ReuseMetricTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="central-compras-reuse-"))
        ambiente.montar(self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, "scripts/central_compras.py", *args],
            cwd=self.tmpdir, text=True, capture_output=True, check=True,
        )

    def test_a_project_does_not_count_its_own_knowledge_as_reuse(self):
        self.run_cli("novo-projeto", "fone metrica", "--categoria", "fone",
                     "--valor-estimado", "300", "--preco-teto", "500")
        # A propria compra registra marca e loja durante a pesquisa.
        self.run_cli("registrar-marca", "QCY", "--categoria", "fone", "--resumo", "Registrada agora.")
        self.run_cli("registrar-loja", "Amazon", "--categoria", "fone", "--resumo", "Registrada agora.")
        self.run_cli("novo-produto", f"projetos/{ANO}-fone-metrica", "QCY H3",
                     "--marca", "QCY", "--categoria", "fone", "--produto-id", "qcy-h3")
        self.run_cli("cotar", f"projetos/{ANO}-fone-metrica", "--produto-id", "qcy-h3",
                     "--loja", "Amazon", "--vendedor", "Oficial", "--vendedor-tipo", "oficial",
                     "--preco", "299", "--nota", "4.6", "--avaliacoes", "1200",
                     "--garantia-meses", "12", "--garantia-tipo", "nacional",
                     "--fonte", "manual", "--link", "https://ex.com/x")

        resultado = self.run_cli("reaproveitamento")
        self.assertIn("Taxa: 0.0%", resultado.stdout,
                      "conhecimento criado pela propria compra nao e reaproveitamento")

    def test_knowledge_written_before_the_project_counts(self):
        # Marca registrada com data anterior a abertura da compra.
        marca = self.tmpdir / "base-conhecimento" / "marcas" / "qcy.md"
        marca.write_text("# QCY\n\n## 2020-01-01\n\n- Resumo: fone anterior durou bem.\n",
                         encoding="utf-8")
        self.run_cli("novo-projeto", "fone com base", "--categoria", "fone",
                     "--valor-estimado", "300", "--preco-teto", "500")
        self.run_cli("novo-produto", f"projetos/{ANO}-fone-com-base", "QCY H3",
                     "--marca", "QCY", "--categoria", "fone", "--produto-id", "qcy-h3")

        resultado = self.run_cli("reaproveitamento")
        self.assertIn("Taxa: 100.0%", resultado.stdout)


class DecisionPromptTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="central-compras-prompt-"))
        ambiente.montar(self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, "scripts/central_compras.py", *args],
            cwd=self.tmpdir, text=True, capture_output=True, check=True,
        )

    def test_decision_prompt_sends_the_ranking_not_the_raw_csv(self):
        self.run_cli("novo-projeto", "fone prompt", "--categoria", "fone",
                     "--valor-estimado", "400", "--preco-teto", "600")
        project = f"projetos/{ANO}-fone-prompt"
        for pid, nome, preco, nota, aval in [
            ("fone-a", "Fone A", "299", "4.7", "3000"),
            ("fone-b", "Fone B", "399", "4.4", "800"),
        ]:
            self.run_cli("novo-produto", project, nome, "--marca", "M",
                         "--categoria", "fone", "--produto-id", pid)
            self.run_cli("cotar", project, "--produto-id", pid, "--loja", "Amazon",
                         "--vendedor", "Oficial", "--vendedor-tipo", "oficial",
                         "--preco", preco, "--nota", nota, "--avaliacoes", aval,
                         "--garantia-meses", "12", "--garantia-tipo", "nacional",
                         "--fonte", "manual", "--link", f"https://ex.com/{pid}")
        saida = self.run_cli("prompt-ia", project, "--etapa", "decisao").stdout

        # Traz o score aberto e o contexto de decisao...
        self.assertIn("qualidade", saida)
        self.assertIn("Fone A", saida)
        self.assertIn("Regra de parada", saida)
        self.assertIn("comparativo dentro deste projeto", saida)
        self.assertIn("conveniencia --", saida)
        self.assertNotIn("escala absoluta 0-100", saida)
        # ...e nao o repr cru do CSV.
        self.assertNotIn("'produto_id':", saida)
        self.assertNotIn("'variacao':", saida)

    def test_decision_prompt_warns_when_there_is_no_price_series(self):
        self.run_cli("novo-projeto", "fone serie", "--categoria", "fone",
                     "--valor-estimado", "400", "--preco-teto", "600")
        project = f"projetos/{ANO}-fone-serie"
        self.run_cli("novo-produto", project, "Fone A", "--marca", "M",
                     "--categoria", "fone", "--produto-id", "fone-a")
        self.run_cli("cotar", project, "--produto-id", "fone-a", "--loja", "Amazon",
                     "--vendedor", "Oficial", "--vendedor-tipo", "oficial",
                     "--preco", "299", "--nota", "4.7", "--avaliacoes", "3000",
                     "--garantia-meses", "12", "--garantia-tipo", "nacional",
                     "--fonte", "manual", "--link", "https://ex.com/a")
        saida = self.run_cli("prompt-ia", project, "--etapa", "decisao").stdout

        self.assertIn("unica observacao de preco", saida)


if __name__ == "__main__":
    unittest.main()
