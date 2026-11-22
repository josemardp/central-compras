"""Corpus rotulado: separacao treino / regressao / independente e honestidade estatistica (radar/avaliacao.py)."""

import unittest
from collections import Counter

from radar import avaliacao


class CorpusTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.itens = avaliacao.carregar_corpus()
        cls.rel = avaliacao.avaliar(cls.itens)

    def test_todo_item_tem_conjunto_valido_e_id_unico(self):
        ids = [i["id"] for i in self.itens]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(i.get("conjunto") in avaliacao.CONJUNTOS for i in self.itens),
                        [i["id"] for i in self.itens if i.get("conjunto") not in avaliacao.CONJUNTOS])

    def test_independente_so_tem_dado_real_e_nunca_calibracao(self):
        ind = [i for i in self.itens if i["conjunto"] == "independente"]
        self.assertGreaterEqual(len(ind), 100)
        self.assertTrue(all(i["origem"] in avaliacao.ORIGENS_INDEPENDENTES for i in ind))
        self.assertFalse([i["id"] for i in ind if i.get("calibracao")])
        self.assertFalse([i["id"] for i in self.itens if i["origem"] == "construido" and i["conjunto"] == "independente"])  # sintetico nunca vira mercado

    def test_dado_sintetico_nunca_entra_na_medida_de_mercado(self):
        sintetico = {i["id"] for i in self.itens if i["origem"] in ("construido", "documentado")}
        self.assertTrue(sintetico)
        self.assertFalse(sintetico & {i["id"] for i in self.itens if i["conjunto"] == "independente"})

    def test_item_real_do_gatry_traz_data_e_identificador_para_conferencia(self):
        g = [i for i in self.itens if i["origem"] == "real_gatry_historico"]
        self.assertGreaterEqual(len(g), 85)
        self.assertTrue(all(i.get("gatry_id") and i.get("data") for i in g))

    def test_nenhum_conjunto_tem_falso_positivo_nem_ambiguo_fora_do_esperado(self):
        for nome in ("conjunto:treino", "conjunto:regressao", "conjunto:independente"):
            self.assertEqual(self.rel["por_origem"][nome]["FP"], 0, nome)
            self.assertEqual(self.rel["por_origem"][nome]["FN"], 0, nome)
        self.assertEqual(self.rel["ambiguos_ok"], len(self.rel["ambiguos"]))

    def test_primeira_passada_preserva_o_defeito_que_o_conjunto_independente_achou(self):
        antes = self.rel["por_origem"]["conjunto:independente (primeira passada, antes das correcoes)"]
        depois = self.rel["por_origem"]["conjunto:independente"]
        self.assertEqual((antes["FP"], depois["FP"]), (1, 0))   # a correcao nao apaga o registro do erro original
        self.assertLess(antes["precisao"], depois["precisao"])
        g008 = next(i for i in self.itens if i["id"] == "G008")
        self.assertEqual(g008["primeira_passada"]["obtido"], "elgin_12k")

    def test_recuperacao_independente_vem_com_intervalo_largo_porque_n_e_pequeno(self):
        t = self.rel["por_origem"]["conjunto:independente"]
        n_pos = t["TP"] + t["FN"]
        self.assertLess(n_pos, 30)
        baixo, alto = t["recuperacao_ic95"]
        self.assertLess(baixo, 0.8)  # com poucos positivos nao se pode afirmar recall alto; o intervalo mostra isso
        self.assertEqual(alto, 1.0)

    def test_relatorio_avisa_que_so_o_independente_mede_mercado(self):
        self.assertIn("so 'conjunto:independente' mede mercado", avaliacao.formatar(self.rel))

    def test_wilson(self):
        self.assertIsNone(avaliacao.wilson(0, 0))
        baixo, alto = avaliacao.wilson(7, 7)
        self.assertAlmostEqual(baixo, 0.646, places=3)
        self.assertEqual(alto, 1.0)

    def test_distribuicao_dos_conjuntos(self):
        c = Counter(i["conjunto"] for i in self.itens)
        self.assertGreater(c["independente"], c["treino"])
        self.assertGreater(c["regressao"], 0)


if __name__ == "__main__":
    unittest.main()
