"""Auto-recuperacao de relatorio perdido (caso real de 21/11/2026: notebook suspenso 02:26-09:37)."""

import datetime as dt
import os
import tempfile
import unittest
from unittest import mock

from radar import db, recuperacao

CFG = {"agendamentos": [
    {"tarefa": "T-relatorios", "job": "relatorios", "horarios": ["08:00", "14:00", "20:00"], "recuperar_ate_horas": 6, "habilitada": True},
    {"tarefa": "T-varredura", "job": "varredura", "a_cada_min": 10, "habilitada": True},
]}


class RecuperacaoTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        p = mock.patch.dict(os.environ, {"CENTRAL_COMPRAS_DADOS_PRIVADOS": self._tmp.name})
        p.start()
        self.addCleanup(p.stop)
        self.addCleanup(self._tmp.cleanup)
        self.con = db.abrir()
        self.addCleanup(self.con.close)

    def _exec(self, quando, job="relatorios", status="ok"):
        self.con.execute("INSERT INTO execucoes (job, passo, inicio, status) VALUES (?,?,?,?)", (job, "robos", quando, status))
        self.con.commit()

    def test_ultimo_slot(self):
        h = ["08:00", "14:00", "20:00"]
        self.assertEqual(recuperacao.ultimo_slot(h, dt.datetime(2026, 11, 21, 9, 52)), dt.datetime(2026, 11, 21, 8, 0))
        self.assertEqual(recuperacao.ultimo_slot(h, dt.datetime(2026, 11, 21, 7, 0)), dt.datetime(2026, 11, 20, 20, 0))

    def test_slot_sem_execucao_dentro_da_tolerancia_e_atrasado(self):
        self._exec("2026-11-20 20:00:00")  # a de ontem a noite nao conta para o slot das 08:00
        r = recuperacao.atrasados(CFG, self.con, dt.datetime(2026, 11, 21, 9, 52))
        self.assertEqual([(a["job"], a["atraso_min"]) for a in r], [("relatorios", 112)])

    def test_slot_ja_executado_nao_e_atrasado(self):
        self._exec("2026-11-21 08:00:03")
        self.assertEqual(recuperacao.atrasados(CFG, self.con, dt.datetime(2026, 11, 21, 9, 52)), [])

    def test_execucao_ignorada_por_trava_conta_como_tratada(self):
        self._exec("2026-11-21 09:40:00", status="ignorada")
        self.assertEqual(recuperacao.atrasados(CFG, self.con, dt.datetime(2026, 11, 21, 9, 52)), [])

    def test_alem_da_tolerancia_nao_recupera(self):
        cfg = {"agendamentos": [{"tarefa": "T", "job": "relatorios", "horarios": ["08:00"], "recuperar_ate_horas": 6, "habilitada": True}]}
        self.assertEqual(len(recuperacao.atrasados(cfg, self.con, dt.datetime(2026, 11, 21, 13, 30))), 1)  # 5h30 de atraso
        self.assertEqual(recuperacao.atrasados(cfg, self.con, dt.datetime(2026, 11, 21, 14, 30)), [])  # 6h30: velho demais

    def test_recuperar_dispara_uma_vez_e_nao_repete_a_cada_ciclo(self):
        chamadas = []
        agora = dt.datetime(2026, 11, 21, 9, 52)
        with mock.patch("radar.recuperacao.db.agora", return_value=agora.strftime("%Y-%m-%d %H:%M:%S")):
            r1 = recuperacao.recuperar(CFG, agora, lambda t: (chamadas.append(t) or True, "ok"))
            r2 = recuperacao.recuperar(CFG, agora + dt.timedelta(minutes=10), lambda t: (chamadas.append(t) or True, "ok"))
        self.assertEqual(chamadas, ["T-relatorios"])
        self.assertEqual(len(r1), 1)
        self.assertEqual(r2, [])

    def test_jobs_sem_tolerancia_ou_por_intervalo_sao_ignorados(self):
        cfg = {"agendamentos": [{"tarefa": "x", "job": "relatorios", "horarios": ["08:00"], "habilitada": True}]}
        self.assertEqual(recuperacao.atrasados(cfg, self.con, dt.datetime(2026, 11, 21, 9, 0)), [])


if __name__ == "__main__":
    unittest.main()
