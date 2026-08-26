"""Escala do score.

Antes o score usava min-max dentro do projeto: com dois candidatos, o segundo
tirava 0,00 em qualidade e valor mesmo perdendo por 0,2 ponto de nota. O numero
tambem nao era comparavel entre compras diferentes.
"""

import unittest

from scripts import central_compras as cc


class QualityScaleTest(unittest.TestCase):
    def test_close_ratings_do_not_become_zero_and_one(self):
        lider = cc.quality_score(4.795)
        segundo = cc.quality_score(4.556)

        self.assertGreater(lider, segundo)
        self.assertGreater(segundo, 0.4, "perder por 0,24 ponto nao pode zerar o eixo")
        self.assertLess(lider, 1.0, "so nota 5,0 cheia deveria valer 1,00")

    def test_scale_is_absolute_across_projects(self):
        # A mesma nota vale o mesmo numero, independente de com quem ela concorre.
        self.assertEqual(cc.quality_score(4.6), cc.quality_score(4.6))
        self.assertEqual(cc.quality_score(5.0), 1.0)
        self.assertEqual(cc.quality_score(3.0), 0.0)


class ValueScaleTest(unittest.TestCase):
    def test_double_the_price_is_half_the_score(self):
        self.assertEqual(cc.value_score(custo=200, menor_custo=100), 0.5)

    def test_cheapest_gets_full_marks(self):
        self.assertEqual(cc.value_score(custo=100, menor_custo=100), 1.0)

    def test_slightly_more_expensive_stays_close_to_one(self):
        self.assertGreater(cc.value_score(custo=110, menor_custo=100), 0.9)


class ConvenienceScaleTest(unittest.TestCase):
    def test_missing_deadline_is_neutral_and_flagged(self):
        score, tem_dado = cc.convenience_score(None)
        self.assertEqual(score, 0.5)
        self.assertFalse(tem_dado)

    def test_fast_delivery_beats_slow(self):
        rapido, _ = cc.convenience_score(2)
        lento, _ = cc.convenience_score(25)
        self.assertGreater(rapido, lento)


class FreshnessTest(unittest.TestCase):
    def test_recent_quote_is_fresh(self):
        hoje = cc.today()
        self.assertFalse(cc.quote_is_stale({"data_coleta": hoje, "fonte": "manual"}))

    def test_old_manual_quote_is_stale(self):
        antiga = {"data_coleta": "2020-01-01", "fonte": "manual"}
        self.assertTrue(cc.quote_is_stale(antiga))
        self.assertGreater(cc.quote_age_days(antiga), 365)

    def test_manual_expires_faster_than_web(self):
        self.assertLessEqual(cc.quote_expiry_days("manual"), cc.quote_expiry_days("web"))

    def test_quote_without_date_is_not_treated_as_stale(self):
        self.assertFalse(cc.quote_is_stale({"data_coleta": "", "fonte": "web"}))


class StopRuleTest(unittest.TestCase):
    def test_cheap_purchase_gets_the_tightest_budget(self):
        barata = cc.stop_rule(150)
        cara = cc.stop_rule(150000)

        self.assertEqual(barata["faixa"], "ate_200")
        self.assertEqual(barata["cotacoes_minimas_por_candidato"], 1)
        self.assertEqual(cara["faixa"], "acima_20000")
        self.assertGreater(cara["cotacoes_minimas_por_candidato"], barata["cotacoes_minimas_por_candidato"])

    def test_human_written_config_is_parsed(self):
        # `3 + 1 presencial` precisa virar 3 sem quebrar.
        self.assertEqual(cc.leading_int("3 + 1 presencial"), 3)
        self.assertEqual(cc.leading_int(""), 0)

    def test_boundary_value_uses_the_lower_band(self):
        self.assertEqual(cc.stop_rule(200)["faixa"], "ate_200")
        self.assertEqual(cc.stop_rule(201)["faixa"], "de_200_a_2000")


class GateTest(unittest.TestCase):
    def _row(self):
        return {
            "custo_total": "100000",
            "nota": "4.9",
            "n_avaliacoes": "5000",
            "nota_ajustada": "4.9",
            "garantia_tipo": "nacional",
            "garantia_meses": "36",
            "vendedor_tipo": "fisica",
        }

    def test_service_network_gate_is_enforced(self):
        produto = {"categoria": "carro", "estado": "pesquisando", "atributos": {}, "requisitos_atendidos": {}}
        eliminacoes = cc.gate_eliminations(self._row(), produto, {"categoria": "carro"})
        self.assertTrue(any("rede de assistencia" in e for e in eliminacoes))

    def test_declared_service_network_passes(self):
        produto = {
            "categoria": "carro",
            "estado": "pesquisando",
            "atributos": {"rede_assistencia": True},
            "requisitos_atendidos": {},
        }
        eliminacoes = cc.gate_eliminations(self._row(), produto, {"categoria": "carro"})
        self.assertFalse(any("rede de assistencia" in e for e in eliminacoes))

    def test_rating_gate_recomputes_instead_of_trusting_frozen_csv_value(self):
        # nota_ajustada gravada no CSV diz 4.9, mas nota 4,0 com 10 avaliacoes
        # encolhe para 4,25 e reprova no gate 4,3 da categoria celular.
        row = {
            "custo_total": "100",
            "nota": "4.0",
            "n_avaliacoes": "10",
            "nota_ajustada": "4.9",
            "garantia_tipo": "nacional",
            "garantia_meses": "12",
            "vendedor_tipo": "oficial",
        }
        produto = {"categoria": "celular", "estado": "pesquisando", "requisitos_atendidos": {}}
        eliminacoes = cc.gate_eliminations(row, produto, {"categoria": "celular"})
        self.assertTrue(any("nota_ajustada" in e for e in eliminacoes))


class AnchorAlertTest(unittest.TestCase):
    def test_anchor_only_compares_against_earlier_quotes(self):
        antiga = {
            "data_coleta": "2026-01-01",
            "produto_id": "p",
            "preco": "100",
        }
        promocao = {
            "data_coleta": "2026-02-01",
            "produto_id": "p",
            "preco": "300",
            "preco_promocional": "150",
        }
        # Ja existia registro de R$ 100 antes: o "de R$ 300" e ancora inflada.
        self.assertIn("ANCORA", cc.manipulation_alerts([antiga, promocao], promocao))

        # Cotacao anterior confirmando o patamar de R$ 300: o desconto e real.
        corrobora = {"data_coleta": "2026-01-01", "produto_id": "p", "preco": "295"}
        self.assertNotIn("ANCORA", cc.manipulation_alerts([corrobora, promocao], promocao))

    def test_later_quote_cannot_serve_as_retroactive_evidence(self):
        promocao = {
            "data_coleta": "2026-02-01",
            "produto_id": "p",
            "preco": "300",
            "preco_promocional": "150",
        }
        # Uma cotacao de R$ 295 coletada DEPOIS nao pode absolver a ancora:
        # na hora da coleta, nao havia serie historica nenhuma.
        futura = {"data_coleta": "2026-03-01", "produto_id": "p", "preco": "295"}
        self.assertIn("ANCORA", cc.manipulation_alerts([promocao, futura], promocao))


if __name__ == "__main__":
    unittest.main()
