"""A cadeia completa de alerta, com cenarios sinteticos (radar/cenarios.py), tem que passar sempre. Nao envia nada."""

import unittest
from unittest import mock

from radar import alertas, cenarios, outbox


class CenariosTest(unittest.TestCase):
    def test_todos_os_cenarios_sinteticos_passam(self):
        with mock.patch("builtins.print"):
            res = cenarios.executar_cenarios()
        reprovados = [c for c in res["cenarios"] if not c["ok"]]
        self.assertEqual(reprovados, [], reprovados)
        self.assertGreaterEqual(res["total"], 16)
        self.assertIsNone(res["envio_teste"])  # por padrao nada e enviado ao WhatsApp

    def test_o_harness_nao_toca_o_banco_real_nem_a_config(self):
        import os
        antes = os.environ.get("CENTRAL_COMPRAS_DADOS_PRIVADOS")
        with mock.patch("builtins.print"):
            cenarios.executar_cenarios()
        self.assertEqual(os.environ.get("CENTRAL_COMPRAS_DADOS_PRIVADOS"), antes)
        from radar import ranking
        a = ranking.carregar_regras()["alertas"]
        self.assertFalse(a["enviar"])
        self.assertIsNone(a["homologado_em"])

    def test_cenario_que_quebra_vira_reprovacao_e_nao_crash(self):
        with mock.patch.object(alertas, "decidir", side_effect=RuntimeError("quebrou")), mock.patch("builtins.print"):
            res = cenarios.executar_cenarios()
        self.assertFalse(res["ok"])
        self.assertIn("RuntimeError", res["cenarios"][0]["obtido"])

    def test_sabotar_a_revalidacao_reprova_o_cenario_de_fila(self):
        original = outbox.drenar
        mock_drenar = lambda con, fn, limite=3, revalidar=None, agora_dt=None: original(
            con, fn, limite, revalidar=lambda o: (True, "sabotado"), agora_dt=agora_dt)
        with mock.patch.object(outbox, "drenar", mock_drenar), mock.patch("builtins.print"):
            res = cenarios.executar_cenarios()
        self.assertIn("S07a", [c["id"] for c in res["cenarios"] if not c["ok"]])

    def test_mensagem_de_teste_e_inequivoca_e_sem_link(self):
        m = cenarios.mensagem_de_teste("corpo https://exemplo.invalido/sint-01")
        self.assertIn("TESTE", m.splitlines()[0])
        self.assertIn("não é oferta real", m)
        self.assertIn("DESLIGADOS", m)
        self.assertNotIn("exemplo.invalido", m)

    def test_o_texto_do_motivo_nao_se_contradiz(self):
        from radar import ranking
        stats = {"observacoes_validas": 20, "cobertura_dias": 3, "historico_total": {"menor": 1000.0, "maior": 1300.0, "mediana": 1150.0},
                 "ultimos_30_dias": {"menor": 1000.0, "maior": 1300.0, "mediana": 1150.0}}
        _, _, motivo = ranking.classificar(990.0, "PROVAVEL", stats, ranking.carregar_regras())
        self.assertIn("NAO validada", motivo)
        self.assertNotIn("minimo historico validado", motivo)  # antes: 'no minimo historico validado ... (nao validado)'


if __name__ == "__main__":
    unittest.main()
