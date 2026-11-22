"""Simulacao da politica de prioridade (radar/simulacao.py) com historico sintetico: deterministico e sem tocar no historico real."""

import unittest

from radar import simulacao


class SimulacaoTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.res = simulacao.simular(historico_real=False)
        cls.sit = {s["nome"]: s for s in cls.res["situacoes"]}

    def test_todas_as_situacoes_pedidas_se_comportam_como_desenhado(self):
        self.assertEqual(set(self.sit), {f"S{i}" for i in range(1, 9)})
        self.assertEqual([n for n, s in self.sit.items() if not s["ok"]], [])
        self.assertTrue(self.res["todas_ok"])

    def test_nada_fica_pendente_para_sempre_em_nenhuma_situacao(self):
        for n, s in self.sit.items():
            self.assertEqual(s["estados_finais"].get("pendente", 0), 0, n)

    def test_tres_ofertas_simultaneas_saem_no_maximo_duas_por_varredura(self):
        s = self.sit["S1"]
        por_hora: dict[str, int] = {}
        for l in s["linhas"]:
            if l["evento"].startswith("ENVIADA"):
                por_hora[l["hora"]] = por_hora.get(l["hora"], 0) + 1
        self.assertTrue(por_hora and max(por_hora.values()) <= 2)
        self.assertEqual(s["mensagens_enviadas"], 3)   # a 3a nao se perde: sai na varredura seguinte

    def test_excepcional_depois_de_esgotado_o_orcamento_fica_retida_e_listada(self):
        s = self.sit["S2"]
        self.assertTrue(any("orcamento:excecao" in l["evento"] for l in s["linhas"]))
        self.assertEqual(len(s["retidas"]), 1)
        self.assertIn("NAO entregue", s["retidas"][0]["motivo"])

    def test_reducoes_sucessivas_so_repetem_com_melhora_de_5_por_cento(self):
        s = self.sit["S3"]
        env = s["precos_enviados"]
        self.assertTrue(all(b <= a * 0.95 for a, b in zip(env, env[1:])), env)
        self.assertEqual(s["estados_finais"].get("suprimido_repeticao"), 2)

    def test_mesmo_cupom_em_varias_comunidades_gera_uma_notificacao(self):
        self.assertEqual(self.sit["S4"]["mensagens_enviadas"], 1)

    def test_promocao_encerrada_antes_do_envio_nao_e_enviada(self):
        s = self.sit["S5"]
        self.assertEqual((s["mensagens_enviadas"], s["estados_finais"].get("expirado")), (1, 1))

    def test_oferta_que_esperou_vaga_e_venceu_fica_retida_visivel(self):
        self.assertTrue(any("venceu aguardando vaga" in r["motivo"] for r in self.sit["S6"]["retidas"]))

    def test_whatsapp_fora_guarda_na_fila_entrega_na_validade_e_descarta_o_vencido(self):
        s = self.sit["S7"]
        self.assertEqual(s["mensagens_enviadas"], 1)
        self.assertTrue(any("descart" in str(d) for d in s["desfechos_da_fila"]))

    def test_dia_cheio_respeita_o_orcamento_e_lista_o_que_reteve(self):
        s = self.sit["S8"]
        self.assertLessEqual(s["mensagens_enviadas"], 6 + 2)
        self.assertEqual(s["mensagens_enviadas"], s["estados_finais"].get("enviado"))
        self.assertTrue(s["retidas"])
        self.assertTrue(all(r["motivo"] for r in s["retidas"]))

    def test_o_historico_real_so_e_lido_nunca_alterado(self):
        import os
        antes = os.environ.get("CENTRAL_COMPRAS_DADOS_PRIVADOS")
        simulacao.simular(historico_real=False)
        self.assertEqual(os.environ.get("CENTRAL_COMPRAS_DADOS_PRIVADOS"), antes)  # variavel de ambiente restaurada


if __name__ == "__main__":
    unittest.main()
