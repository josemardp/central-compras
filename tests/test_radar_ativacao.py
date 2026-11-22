"""Verificacao previa da ativacao (radar/ativacao.py): somente leitura; o kill switch so desliga."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from radar import ativacao, caminhos, ranking

CONFIG = """# regras
prioridade:
  orcamento_diario: 6

alertas:
  # comentario que precisa sobreviver
  enviar: true
  homologado_em: "2026-11-22 09:00"   # data da revisao
  status_enviaveis: [PROVAVEL, VALIDADO]
  limite_diario: 6

outro:
  enviar: true
"""


class VeredictoTest(unittest.TestCase):
    def test_falha_vence_pendente_e_so_manual_nao_bloqueia(self):
        i = lambda s: {"id": "x", "nome": "n", "status": s, "detalhe": "d"}
        self.assertTrue(ativacao.veredito([i("OK"), i("FALHA"), i("PENDENTE")]).startswith("NAO APTO:"))
        self.assertTrue(ativacao.veredito([i("OK"), i("PENDENTE"), i("MANUAL")]).startswith("NAO APTO AINDA"))
        self.assertTrue(ativacao.veredito([i("OK"), i("MANUAL")]).startswith("APTO"))

    def test_formatar_sempre_lembra_que_ligar_e_passo_do_usuario(self):
        txt = ativacao.formatar([{"id": "A1", "nome": "n", "status": "OK", "detalhe": "d"}])
        self.assertIn("Para LIGAR: edite", txt)
        self.assertIn("operacao.yaml", txt)                        # o estado ligado vive no arquivo LOCAL, fora do Git
        self.assertIn("--desligar", txt)


class DesligarTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._dados = tempfile.TemporaryDirectory()
        pe = mock.patch.dict(os.environ, {"CENTRAL_COMPRAS_DADOS_PRIVADOS": self._dados.name})
        pe.start()
        self.addCleanup(self._dados.cleanup)
        self.addCleanup(self._tmp.cleanup)
        self.addCleanup(pe.stop)
        self.dir = Path(self._tmp.name)
        (self.dir / "radar_regras.yaml").write_text(CONFIG, encoding="utf-8")
        for alvo, valor in (("radar.ativacao.caminhos.CONFIG_DIR", self.dir), ("radar.ranking.ARQ_REGRAS", self.dir / "radar_regras.yaml")):
            p = mock.patch(alvo, valor)
            p.start()
            self.addCleanup(p.stop)

    def test_desliga_so_o_bloco_alertas_e_preserva_comentarios(self):
        ok, info = ativacao.desligar()
        self.assertTrue(ok, info)
        txt = (self.dir / "radar_regras.yaml").read_text(encoding="utf-8")
        cfg = ranking.carregar_regras(self.dir / "radar_regras.yaml")
        self.assertIs(cfg["alertas"]["enviar"], False)
        self.assertIsNone(cfg["alertas"]["homologado_em"])
        self.assertIn("# comentario que precisa sobreviver", txt)
        self.assertEqual(cfg["outro"]["enviar"], True)            # outro bloco com a mesma chave NAO foi tocado
        self.assertEqual(cfg["alertas"]["limite_diario"], 6)
        self.assertEqual(cfg["prioridade"]["orcamento_diario"], 6)

    def test_kill_switch_descarta_alertas_na_fila_e_preserva_relatorios(self):
        from radar import db, outbox
        con = db.abrir()
        outbox.enfileirar(con, "alerta", "radar-alerta", "fora", tipo="alerta", oferta_id=1)
        outbox.enfileirar(con, "relatorio", "rastreador-robos", "fora")
        con.close()
        ok, info = ativacao.desligar()
        self.assertTrue(ok)
        self.assertIn("1 alerta(s) da fila descartado(s)", info)
        con = db.abrir()
        try:
            self.assertEqual({(r["tipo"], r["desfecho"]) for r in con.execute("SELECT tipo, desfecho FROM outbox")},
                             {("alerta", "descartado_alertas_desligados"), ("relatorio", None)})
        finally:
            con.close()

    def test_idempotente(self):
        ativacao.desligar()
        ok, _ = ativacao.desligar()
        self.assertTrue(ok)


class TarefaEmExecucaoTest(unittest.TestCase):
    """O verificador roda de dia, no meio dos ciclos: tarefa `Running` (resultado 267009) nao e falha."""

    def _b2(self, estado):
        tarefas = {n: dict(estado, existe=True, ultima="x", proxima="y") for n in ativacao.TAREFAS}
        ok_dest = {"id": "E4", "nome": "n", "status": "OK", "detalhe": "d"}
        patches = [
            mock.patch("radar.agenda_windows.estado_tarefas", return_value=tarefas),
            mock.patch.object(ativacao, "_destinatario", return_value=ok_dest),
            mock.patch("subprocess.run", return_value=mock.Mock(returncode=0, stdout="limpo\n")),
            mock.patch("radar.simulacao.simular", return_value={"todas_ok": True, "situacoes": []}),
            mock.patch("radar.cenarios.executar_cenarios", return_value={"ok": True, "aprovados": 22, "total": 22}),
        ]
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"CENTRAL_COMPRAS_DADOS_PRIVADOS": tmp}):
            for p in patches:
                p.start()
            try:
                return [i["status"] for i in ativacao.verificar() if i["id"] == "B2"]
            finally:
                mock.patch.stopall()

    def test_running_com_267009_e_ready_com_0_sao_ok_e_resultado_de_erro_e_falha(self):
        self.assertEqual(self._b2({"estado": "Running", "resultado": 267009}), ["OK", "OK"])
        self.assertEqual(self._b2({"estado": "Ready", "resultado": 0}), ["OK", "OK"])
        self.assertEqual(self._b2({"estado": "Ready", "resultado": 1}), ["FALHA", "FALHA"])
        self.assertEqual(self._b2({"estado": "Disabled", "resultado": 0}), ["FALHA", "FALHA"])


class VerificarTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        p = mock.patch.dict(os.environ, {"CENTRAL_COMPRAS_DADOS_PRIVADOS": self._tmp.name})
        p.start()
        self.addCleanup(self._tmp.cleanup)
        self.addCleanup(p.stop)

    def test_sem_evidencia_ao_vivo_o_veredito_e_nao_apto_e_nada_e_enviado(self):
        enviados = mock.Mock()
        with mock.patch.object(ativacao, "_destinatario", return_value={"id": "E4", "nome": "n", "status": "OK", "detalhe": "d"}), \
                mock.patch("radar.canais.enviar_whatsapp", enviados):
            itens = ativacao.verificar(rodar_externos=False)
        por_id = {i["id"]: i for i in itens}
        self.assertEqual(por_id["A1"]["status"], "OK")            # config real: alertas desligados
        self.assertEqual(por_id["D1"]["status"], "PENDENTE")      # banco novo: nenhuma oferta real em sombra
        self.assertEqual(por_id["E1"]["status"], "OK")            # fila e politica em banco temporario
        self.assertEqual(por_id["E2"]["status"], "OK")
        self.assertEqual(por_id["E3"]["status"], "MANUAL")        # envio real e passo do usuario
        self.assertTrue(ativacao.veredito(itens).startswith("NAO APTO"))
        enviados.assert_not_called()

    def test_a_verificacao_nao_tem_caminho_de_envio_nem_de_ligar(self):
        """Verificar, destinatario, formatar e desligar nunca enviam nem ligam; o unico envio do modulo e o teste_entrega, que exige --confirmo."""
        import inspect
        for fn in (ativacao.verificar, ativacao._destinatario, ativacao.formatar, ativacao.veredito, ativacao.desligar):
            src = inspect.getsource(fn)
            for proibido in ("enviar_whatsapp(", "enviar_fn(", "enviar=True", '"enviar": True'):
                self.assertNotIn(proibido, src, f"{fn.__name__}: {proibido}")
        self.assertIn("if not confirmo:", inspect.getsource(ativacao.teste_entrega))


class TesteDeEntregaTest(unittest.TestCase):
    """Teste unico ao SEU WhatsApp: so envia com --confirmo, no maximo 1 por dia, e mede os estagios."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        p = mock.patch.dict(os.environ, {"CENTRAL_COMPRAS_DADOS_PRIVADOS": self._tmp.name})
        p.start()
        self.addCleanup(self._tmp.cleanup)
        self.addCleanup(p.stop)
        self.enviados = []

    def canal(self, texto):
        self.enviados.append(texto)
        return True, "Enviado para '(destino)' | caixa_vazia=True | ultima=' 🧪 TESTE DO RADAR DE COMPRAS (mensagem sintética, não é oferta'"

    def test_sem_confirmo_so_mostra_a_previa_e_nada_e_enviado(self):
        r = ativacao.teste_entrega(confirmo=False, enviar_fn=self.canal)
        self.assertFalse(r["enviado"])
        self.assertIn("TESTE DO RADAR DE COMPRAS", r["previa"])
        self.assertIn("Confiança:", r["previa"])             # mostra o formato REAL, com os tres niveis de preco
        self.assertIn("Confirmado na loja", r["previa"])
        self.assertEqual(self.enviados, [])

    def test_com_confirmo_envia_uma_vez_mede_e_grava_a_latencia(self):
        from radar import latencia
        r = ativacao.teste_entrega(confirmo=True, enviar_fn=self.canal)
        self.assertTrue(r["enviado"] and r["confirmado_no_chat"])
        self.assertEqual(len(self.enviados), 1)
        self.assertGreaterEqual(r["ponta_a_ponta_s"], r["duracao_s"])
        ev = latencia.ler(1)
        self.assertEqual({e["evento"] for e in ev}, {"teste_entrega", "envio_alerta"})
        con = db_abrir()
        try:
            a = latencia.analisar(con, 1)
        finally:
            con.close()
        self.assertTrue(a["entrega_alerta_s"]["medido"])       # passa de ESTIMADO para MEDIDO
        self.assertIn("teste controlado", latencia.formatar(a))

    def test_segundo_teste_no_mesmo_dia_e_recusado_sem_de_novo(self):
        ativacao.teste_entrega(confirmo=True, enviar_fn=self.canal)
        r2 = ativacao.teste_entrega(confirmo=True, enviar_fn=self.canal)
        self.assertFalse(r2["enviado"])
        self.assertIn("UNICO", r2["motivo"])
        self.assertEqual(len(self.enviados), 1)
        ativacao.teste_entrega(confirmo=True, de_novo=True, enviar_fn=self.canal)
        self.assertEqual(len(self.enviados), 2)

    def test_falha_do_canal_nao_conta_como_teste_feito(self):
        r = ativacao.teste_entrega(confirmo=True, enviar_fn=lambda t: (False, "aba do WhatsApp nao encontrada"))
        self.assertFalse(r["enviado"])
        r2 = ativacao.teste_entrega(confirmo=True, enviar_fn=self.canal)   # pode tentar de novo: a marca so vale apos um envio ok
        self.assertTrue(r2["enviado"])


def db_abrir():
    from radar import db
    return db.abrir()


class EnsaioKillSwitchTest(unittest.TestCase):
    def test_ensaio_completo_passa_sem_tocar_na_config_real(self):
        antes = (caminhos.CONFIG_DIR / "radar_regras.yaml").read_text(encoding="utf-8")
        itens = ativacao.ensaio_kill_switch()
        self.assertEqual([i["id"] for i in itens if i["status"] != "OK"], [], itens)
        self.assertEqual((caminhos.CONFIG_DIR / "radar_regras.yaml").read_text(encoding="utf-8"), antes)


if __name__ == "__main__":
    unittest.main()
