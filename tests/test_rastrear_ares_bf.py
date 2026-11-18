"""Testes unitarios das funcoes puras do rastreador de ares (sem rede/Zap)."""

import unittest

from scripts import rastrear_ares_bf as ra


class RastrearAresTest(unittest.TestCase):
    def test_parse_brl_flex_e_normalizar_cep(self):
        self.assertEqual(ra.parse_brl_flex("Entrega R$190 1 - 3 de Dezembro"), 190.0)
        self.assertEqual(ra.parse_brl_flex("R$ 2.569,00"), 2569.0)
        self.assertIsNone(ra.parse_brl_flex("Frete gratis"))
        self.assertEqual(ra.normalizar_cep("12345" + "-" + "678"), "12345678")
        with self.assertRaises(ValueError):
            ra.normalizar_cep("123")

    def test_detectar_alteracoes_sem_mudanca(self):
        snap = {
            "coletado_em": "2026-11-18 14:00",
            "modelos": {
                "elgin_12k": {"nome": "Elgin Eco Inverter III 12k", "melhor_preco": 1799.90, "melhor_onde": "Amazon"},
                "philco_18k": {"nome": "Philco Eco Inverter 18k", "melhor_preco": 2569.00, "melhor_onde": "Amazon"},
            },
        }
        self.assertEqual(ra.detectar_alteracoes(snap, snap), [])

    def test_detectar_alteracoes_preco(self):
        ant = {
            "coletado_em": "2026-11-18 08:00",
            "modelos": {
                "philco_18k": {"nome": "Philco Eco Inverter 18k", "melhor_preco": 2718.00, "melhor_onde": "WebContinental"},
            },
        }
        atu = {
            "coletado_em": "2026-11-18 14:00",
            "modelos": {
                "philco_18k": {"nome": "Philco Eco Inverter 18k", "melhor_preco": 2569.00, "melhor_onde": "Amazon"},
            },
        }
        mudancas = ra.detectar_alteracoes(atu, ant)
        texto = "\n".join(mudancas)
        self.assertIn("BAIXOU", texto)
        self.assertIn("2.569,00", texto)

    def test_montar_mensagem_ordena_por_menor_total(self):
        snap = {
            "coletado_em": "2026-11-18 15:30",
            "modelos": {
                "agratto_12k": {"nome": "Agratto Kyn Top 12k", "sku": "KNICST12F-02", "grupo": "12k", "melhor_preco": 1832.02, "melhor_onde": "Dufrio"},
                "elgin_12k": {"nome": "Elgin Eco Inverter III 12k", "sku": "HJFC12C2WGCG", "grupo": "12k", "melhor_preco": 1799.90, "melhor_onde": "Amazon", "amazon": {"cupons": ["70OFF"]}},
                "midea_lite_12k": {"nome": "Midea AirVolution Lite 12k", "sku": "42EBVCB12M5", "grupo": "12k", "melhor_preco": 1982.93, "melhor_onde": "Dufrio"},
                "midea_ecomaster_12k": {"nome": "Midea AI Ecomaster 12k", "sku": "42EZVCA12M5", "grupo": "12k", "melhor_preco": 2304.90, "melhor_onde": "Amazon"},
                "elgin_18k": {"nome": "Elgin Eco Inverter III 18k", "sku": "HJFC18C2WHCH", "grupo": "18k", "melhor_preco": 2758.54, "melhor_onde": "WebContinental"},
                "philco_18k": {"nome": "Philco Eco Inverter 18k", "sku": "PAC18FTW", "grupo": "18k", "melhor_preco": 2569.00, "melhor_onde": "Amazon", "webcontinental": {"cupom_banner": "R$200"}},
            },
        }
        msg = ra.montar_mensagem(snap, None, primeira_vez=True)
        self.assertIn("❄️ *RASTREIO ARES", msg)
        self.assertIn("🥇 *Elgin Eco Inverter III 12k*", msg)
        self.assertIn("🥇 *Philco Eco Inverter 18k*", msg)
        self.assertIn("⚖️ *Elgin 18k vs Philco:* +R$ 189,54", msg)


if __name__ == "__main__":
    unittest.main()
