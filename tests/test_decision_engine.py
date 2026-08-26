import unittest

from scripts import central_compras


class DecisionEngineTest(unittest.TestCase):
    def test_adjusted_rating_shrinks_low_volume_perfect_score(self):
        self.assertLess(central_compras.adjusted_rating(5.0, 4), 4.4)
        self.assertGreater(central_compras.adjusted_rating(4.7, 6000), 4.69)

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


if __name__ == "__main__":
    unittest.main()
