import unittest

from radar import equivalentes as eq
from radar.modelos import Oferta


def of(fonte, titulo, preco, loja="Amazon", **kw):
    return Oferta(fonte=fonte, canal="recentes", id_externo=titulo[:8] + fonte, titulo=titulo, preco_anunciado=preco, loja=loja,
                  url=f"https://x/{fonte}", publicado_em="2026-11-21 11:00", **kw)


HISENSE = "Ar Condicionado Split Inverter 12000 BTUs Hisense Hi-Efficiency Frio - 220V"
MELHORES = {"ares_12k": 1865.60, "ares_18k": 2438.01}


class EquivalentesTest(unittest.TestCase):
    def test_classe_so_para_split_inverter_frio_220v_na_capacidade_certa(self):
        self.assertEqual(eq.classe_do_texto(HISENSE), "ares_12k")
        self.assertEqual(eq.classe_do_texto("Split Inverter LG Dual 18.000 BTUs Só Frio 220V"), "ares_18k")
        for t in ("Ar Condicionado Split Inverter 9000 BTUs Hisense Frio 220V",          # outra capacidade
                  "Ar Condicionado Split Inverter 12000 BTUs Quente e Frio 220V",        # quente/frio
                  "Ar Condicionado Split Inverter 12000 BTUs Frio 127V",                 # voltagem
                  "Ar Condicionado Split Inverter 12000 BTUs Frio Bivolt",               # nao garante 220V
                  "Ar Condicionado Split 12000 BTUs Frio 220V",                           # nao e inverter
                  "Ar Condicionado Portátil Inverter 12000 BTUs Frio 220V",              # portatil
                  "Micro-ondas Philco 20L"):
            self.assertIsNone(eq.classe_do_texto(t), t)

    def test_mesmo_anuncio_em_tres_fontes_vira_um_so_com_economia_e_aviso(self):
        res = eq.levantar([of("promobit", HISENSE, 1710.0), of("gatry", HISENSE, 1710.96), of("pelando", HISENSE, 1710.0)], MELHORES)
        self.assertEqual(len(res), 1)
        r = res[0]
        self.assertEqual((r["n_fontes"], r["preco"], r["economia"], r["mais_barato_que_o_seu"]), (3, 1710.0, 155.6, True))
        self.assertIn("gate de qualidade", r["aviso"])

    def test_um_dos_seus_12_produtos_nao_e_equivalente(self):
        self.assertEqual(eq.levantar([of("promobit", "Ar Condicionado Split Elgin Eco Inverter III Wi-Fi 12000 BTUs Frio - 220V", 1799.0)], MELHORES), [])

    def test_mais_caro_que_o_seu_e_marcado_assim_e_cupom_de_loja_nao_entra(self):
        r = eq.levantar([of("promobit", HISENSE, 2100.0)], MELHORES)[0]
        self.assertFalse(r["mais_barato_que_o_seu"])
        cupom = of("meliuz", "amazon: cupom 12000 BTU", 1.0, extras={"tipo": "cupom_loja"})
        self.assertEqual(eq.levantar([cupom], MELHORES), [])

    def test_nunca_gera_alerta(self):
        import inspect
        src = inspect.getsource(eq)
        self.assertNotIn("enviar", src)
        self.assertNotIn("alertas", src)


if __name__ == "__main__":
    unittest.main()
