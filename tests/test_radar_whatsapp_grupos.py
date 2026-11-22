import unittest

from radar import whatsapp_grupos as wg

CFG = {"autorizados": [{"nome": "Promobit Amazon"}, {"nome": "Ofertas Tech", "habilitado": False}],
       "nunca": ["familia", "igreja", "5a cia"], "max_grupos": 5}


class WhatsappGruposTest(unittest.TestCase):
    def test_configuracao_real_nao_autoriza_nenhum_grupo(self):
        cfg = wg.carregar()
        self.assertEqual(cfg["autorizados"], [])
        self.assertIn("Nenhum grupo", wg.resumo(cfg))
        self.assertFalse(wg.verificar("Qualquer Grupo", cfg)[0])

    def test_so_o_listado_e_habilitado_passa_sem_acento_e_sem_caixa(self):
        self.assertTrue(wg.verificar("promobit amazon", CFG)[0])
        self.assertTrue(wg.verificar("PROMOBIT  AMAZON", CFG)[0])
        self.assertFalse(wg.verificar("Ofertas Tech", CFG)[0])      # listado mas desabilitado
        self.assertFalse(wg.verificar("Promobit Magalu", CFG)[0])   # parecido, nao listado

    def test_privado_telefone_e_lista_nunca_sao_sempre_recusados(self):
        cfg = CFG | {"autorizados": [{"nome": "+55 18 99106-3272"}, {"nome": "Familia Silva"}, {"nome": "Igreja Ofertas"}]}
        for nome in ("+55 18 99106-3272", "18991063272", "Familia Silva", "Igreja Ofertas", "Grupo da 5ª Cia PM"):
            ok, motivo = wg.verificar(nome, cfg)
            self.assertFalse(ok, nome)

    def test_exigir_autorizado_levanta(self):
        wg.exigir_autorizado("Promobit Amazon", CFG)
        with self.assertRaises(wg.GrupoNaoAutorizado):
            wg.exigir_autorizado("Outro", CFG)

    def test_lista_maior_que_o_maximo_trava_tudo(self):
        cfg = {"autorizados": [{"nome": f"G{i}"} for i in range(6)], "nunca": [], "max_grupos": 5}
        self.assertFalse(wg.verificar("G1", cfg)[0])

    def test_nome_vazio(self):
        self.assertFalse(wg.verificar("  ", CFG)[0])


if __name__ == "__main__":
    unittest.main()
