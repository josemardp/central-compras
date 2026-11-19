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

    def test_montar_mensagem_tem_espacamento_e_emojis(self):
        snap = {
            "coletado_em": "2026-11-18 15:15",
            "modelos": {
                "dreame_f10": {"nome": "Dreame F10", "melhor_preco": 1994.05, "melhor_onde": "Amazon (DREAME LTDA)", "promobit": []},
                "k800_pro_127v": {"nome": "KaBuM K800 Pro 127V", "melhor_preco": 1199.99, "melhor_onde": "KaBuM Pix", "kabum_preto": {"cupom": "CASATECH10"}},
                "tapo_rv20_max": {"nome": "Tapo RV20 Max", "melhor_preco": 854.05, "melhor_onde": "Amazon (TNTinfoLoja)", "amazon": {"cupons": ["25PRIMEBF"]}},
                "xiaomi_s40c": {"nome": "Xiaomi S40C", "melhor_preco": 1165.83, "melhor_onde": "Amazon (J R C STORE)"},
            },
        }
        msg = rr.montar_mensagem(snap, snap)
        self.assertIn("🥇 *Dreame F10*", msg)
        self.assertIn("\n\n🥈 *KaBuM K800 Pro 127V*", msg)
        self.assertIn("🔴 *R$ 1.994,05*", msg)
        self.assertIn("🟢 *R$ 1.199,99*", msg)

    def test_parse_usd_e_resumir_ofertas_cp(self):
        self.assertEqual(rr.parse_usd("US$ 225,00 R$ 1.327,50"), 225.0)
        self.assertEqual(rr.fmt_usd(214.0), "US$ 214,00")
        ofertas_raw = [
            {"loja": "Visãovip", "text": "Xiaomi S40 Pro (Recondicionado) Código: 1 US$ 199,00 R$ 1.174,10"},
            {"loja": "Cellshop", "text": "Xiaomi S40 Pro (Caixa Feia) Código: 2 US$ 210,00 R$ 1.239,00"},
            {"loja": "MultiPass", "text": "Xiaomi S40 Pro BHR089REU Código: 3 US$ 214,00 R$ 1.262,60"},
            {"loja": "Nissei", "text": "Xiaomi S40 Pro BHR0890US Código: 4 US$ 225,00"},
        ]
        res = rr._resumir_ofertas_cp(ofertas_raw, dolar_hoje=5.90)
        self.assertEqual(res["qtd_ofertas"], 4)
        self.assertEqual(res["menor_novo"]["loja"], "MultiPass")
        self.assertEqual(res["menor_novo"]["preco_brl"], 1262.60)
        self.assertEqual(res["menor_geral"]["loja"], "Visãovip")
        self.assertTrue(res["menor_geral"]["avaria_ou_recond"])
        self.assertEqual(res["menor_grandes"]["loja"], "Nissei")
        self.assertEqual(res["menor_grandes"]["preco_brl"], 1327.50)

    def test_montar_mensagem_inclui_s40_pro_paraguai(self):
        snap = {
            "coletado_em": "2026-11-19 18:30",
            "modelos": {
                "dreame_f10": {"nome": "Dreame F10", "melhor_preco": 1994.05, "melhor_onde": "Amazon (DREAME LTDA)", "promobit": []},
                "k800_pro_127v": {"nome": "KaBuM K800 Pro 127V", "melhor_preco": 1199.99, "melhor_onde": "KaBuM Pix", "kabum_preto": {"cupom": "CASATECH10"}},
                "tapo_rv20_max": {"nome": "Tapo RV20 Max", "melhor_preco": 854.05, "melhor_onde": "Amazon (TNTinfoLoja)", "amazon": {"cupons": []}},
                "xiaomi_s40c": {"nome": "Xiaomi S40C", "melhor_preco": 1165.83, "melhor_onde": "Amazon (J R C STORE)"},
                "xiaomi_s40_pro_py": {
                    "nome": "Xiaomi S40 Pro (Paraguai)",
                    "melhor_preco": 1262.60,
                    "melhor_onde": "Compras PY/MultiPass (US$ 214,00)",
                    "compras_paraguai": {
                        "dolar_hoje": 5.90,
                        "qtd_ofertas": 42,
                        "menor_grandes": {"loja": "Madrid Center", "preco_usd": 225.0, "preco_brl": 1327.50},
                        "menor_geral": {"loja": "Visãovip", "preco_usd": 199.0, "preco_brl": 1174.10, "avaria_ou_recond": True},
                    },
                },
            },
        }
        msg = rr.montar_mensagem(snap, None)
        self.assertIn("5️⃣ *Xiaomi S40 Pro (Paraguai)*", msg)
        self.assertIn("Compras PY/MultiPass (US$ 214,00)", msg)
        self.assertIn("64,90 mais barato* que 19/11", msg)
        self.assertIn("Dolar CP: R$ 5,90", msg)
        self.assertIn("Grandes CDE: *R$ 1.327,50* (Madrid Center · US$ 225,00)", msg)
        self.assertIn("Recond.: R$ 1.174,10 (Visãovip · US$ 199,00)", msg)


if __name__ == "__main__":
    unittest.main()
