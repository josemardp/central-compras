"""Testes unitarios das funcoes puras do rastreador de robos (sem rede/Zap)."""

import unittest

from scripts import rastrear_robos_bf as rr


class RastrearRobosTest(unittest.TestCase):
    def test_parse_and_format_brl(self):
        self.assertEqual(rr.parse_brl("R$ 1.199,99 à vista"), 1199.99)
        self.assertEqual(rr.parse_brl("sem preco"), None)
        self.assertEqual(rr.fmt_brl(1199.99), "R$ 1.199,99")
        self.assertEqual(rr.fmt_brl(None), "indisponivel")

    def test_detectar_alteracoes_sem_mudanca(self):
        snap = {
            "coletado_em": "2026-11-18 08:00",
            "modelos": {
                "dreame_f10": {"nome": "Dreame F10", "melhor_preco": 1994.05, "melhor_onde": "Amazon"},
                "k800_pro_127v": {
                    "nome": "KaBuM K800 Pro 127V",
                    "melhor_preco": 1199.99,
                    "melhor_onde": "KaBuM",
                    "kabum_preto": {"cupom": "CASATECH10"},
                },
            },
        }
        self.assertEqual(rr.detectar_alteracoes(snap, snap), [])

    def test_detectar_alteracoes_queda_preco_e_cupom(self):
        ant = {
            "coletado_em": "2026-11-18 08:00",
            "modelos": {
                "dreame_f10": {"nome": "Dreame F10", "melhor_preco": 1994.05, "melhor_onde": "Amazon"},
                "k800_pro_127v": {
                    "nome": "KaBuM K800 Pro 127V",
                    "melhor_preco": 1199.99,
                    "melhor_onde": "KaBuM",
                    "kabum_preto": {"cupom": "CASATECH10"},
                },
            },
        }
        atu = {
            "coletado_em": "2026-11-18 14:00",
            "modelos": {
                "dreame_f10": {"nome": "Dreame F10", "melhor_preco": 1102.00, "melhor_onde": "Amazon"},
                "k800_pro_127v": {
                    "nome": "KaBuM K800 Pro 127V",
                    "melhor_preco": 959.00,
                    "melhor_onde": "KaBuM",
                    "kabum_preto": {"cupom": "20TAONOROBO"},
                },
            },
        }
        mudancas = rr.detectar_alteracoes(atu, ant)
        texto = "\n".join(mudancas)
        self.assertIn("BAIXOU", texto)
        self.assertIn("1.102,00", texto)
        self.assertIn("20TAONOROBO", texto)


if __name__ == "__main__":
    unittest.main()
