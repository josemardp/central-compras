import shutil
import tempfile
from pathlib import Path

import ambiente
import unittest

from scripts import central_compras


class DecisionEngineTest(unittest.TestCase):
    def test_adjusted_rating_shrinks_low_volume_perfect_score(self):
        # Com m=250, nota 5,0 com 4 avaliacoes quase nao sai da media da
        # categoria: volume e evidencia, e 4 avaliacoes nao sao evidencia.
        self.assertLess(central_compras.adjusted_rating(5.0, 4), 4.35)
        # Ja 6.000 avaliacoes dominam a ancora com folga.
        self.assertGreater(central_compras.adjusted_rating(4.7, 6000), 4.68)

    def test_risk_score_penalizes_alerts(self):
        row = {
            "vendedor_tipo": "oficial",
            "garantia_tipo": "nacional",
            "garantia_meses": "12",
        }
        clean = central_compras.risk_score(row, [])
        suspicious = central_compras.risk_score(row, ["AVAL_SUSPEITA", "ANCORA"])
        self.assertLess(suspicious, clean)

    def test_discarded_product_is_cut_by_gate(self):
        row = {
            "custo_total": "100",
            "nota_ajustada": "4.8",
            "n_avaliacoes": "1000",
            "garantia_tipo": "nacional",
            "garantia_meses": "12",
            "vendedor_tipo": "oficial",
        }
        product = {
            "categoria": "fone",
            "estado": "descartado",
            "descartado_porque": "Microfone ruim.",
            "requisitos_atendidos": {},
        }
        briefing = {"categoria": "fone", "preco_teto": 600}
        eliminations = central_compras.gate_eliminations(row, product, briefing)
        self.assertIn("produto descartado", eliminations[0])

    def test_tco_total_uses_monthly_cost_and_resale_value(self):
        total = central_compras.quote_tco_total(
            custo_total=100000,
            custo_operacional_mensal=1000,
            tco_meses=60,
            valor_revenda_estimado=50000,
        )
        self.assertEqual(total, 110000)


class CategoryBayesianAnchorTest(unittest.TestCase):
    """`nota_bayesiana` pode ser sobrescrito por categoria."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="central-compras-bayes-"))
        ambiente.montar(self.tmpdir)
        self._orig_config = central_compras.CONFIG
        central_compras.CONFIG = self.tmpdir / "config"
        central_compras._PREFS_CACHE.clear()

    def tearDown(self):
        central_compras.CONFIG = self._orig_config
        central_compras._PREFS_CACHE.clear()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_category_without_block_uses_global(self):
        sem_categoria = central_compras.adjusted_rating(4.8, 30)
        com_categoria = central_compras.adjusted_rating(4.8, 30, "generico")
        self.assertEqual(sem_categoria, com_categoria)

    def test_category_with_custom_anchor_uses_local_value(self):
        categorias = central_compras.read_yaml(self.tmpdir / "config" / "categorias.yaml", {})
        categorias["teste_bayes"] = {
            "atributos_obrigatorios": [],
            "nota_bayesiana": {"peso_ancora": 30},
            "gate": {},
        }
        central_compras.write_yaml(self.tmpdir / "config" / "categorias.yaml", categorias)

        global_ancora = central_compras.adjusted_rating(4.8, 30, "generico")
        local_ancora = central_compras.adjusted_rating(4.8, 30, "teste_bayes")
        # Ancora menor deixa a nota bruta pesar mais, aproximando do valor original.
        self.assertGreater(local_ancora, global_ancora)


if __name__ == "__main__":
    unittest.main()
