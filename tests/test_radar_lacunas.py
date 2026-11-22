"""Analise historica de lacunas de coleta (qualidade.lacunas_historicas) sobre ciclos gravados."""

import datetime as dt
import json
import os
import tempfile
import unittest
from unittest import mock

from radar import db, qualidade

AGORA = dt.datetime(2026, 11, 21, 20, 0)


class LacunasHistoricasTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        p = mock.patch.dict(os.environ, {"CENTRAL_COMPRAS_DADOS_PRIVADOS": self._tmp.name})
        p.start()
        self.con = db.abrir()
        self.addCleanup(self._tmp.cleanup)
        self.addCleanup(self.con.close)
        self.addCleanup(p.stop)

    def ciclo(self, fonte, quando, cobertura=None, status="ok"):
        self.con.execute("INSERT INTO coletas_ciclo (ciclo_em, fonte, status, itens, descartes_json) VALUES (?,?,?,?,?)",
                         (quando.strftime("%Y-%m-%d %H:%M:%S"), fonte, status, 10, json.dumps({"cobertura_min": cobertura})))
        self.con.commit()

    def test_intervalo_normal_nao_e_lacuna_e_queda_longa_e(self):
        t = AGORA - dt.timedelta(hours=10)
        for i in range(6):                                  # ciclos de 10 em 10 min
            self.ciclo("promobit", t + dt.timedelta(minutes=10 * i), cobertura=40)
        self.ciclo("promobit", t + dt.timedelta(minutes=50 + 590), cobertura=40)   # internet fora por quase 10 h
        r = qualidade.lacunas_historicas(self.con, 24, AGORA)["promobit"]
        self.assertEqual(len(r["lacunas"]), 1)
        self.assertEqual((r["lacunas"][0]["sem_ler_min"], r["lacunas"][0]["alcance_min"], r["lacunas"][0]["perdido_min"]), (590, 40, 550))
        self.assertEqual(r["perdido_total_min"], 550)

    def test_janela_maior_que_o_ciclo_mas_menor_que_o_alcance_nao_perde_nada(self):
        t = AGORA - dt.timedelta(hours=3)
        self.ciclo("gatry", t, cobertura=968)
        self.ciclo("gatry", t + dt.timedelta(hours=7 - 4), cobertura=968)           # 180 min sem ler, lista alcanca 968 min
        self.assertEqual(qualidade.lacunas_historicas(self.con, 24, AGORA)["gatry"]["lacunas"], [])

    def test_fonte_sem_hora_usa_a_estimativa_da_configuracao_e_sem_nada_fica_indeterminada(self):
        t = AGORA - dt.timedelta(hours=6)
        self.ciclo("hardmob", t)
        self.ciclo("hardmob", t + dt.timedelta(hours=4))
        cfg = {"hardmob": {"cobertura_estimada_min": 120}}
        r = qualidade.lacunas_historicas(self.con, 24, AGORA, cfg)["hardmob"]
        self.assertEqual((r["lacunas"][0]["situacao"], r["lacunas"][0]["alcance_min"], r["lacunas"][0]["perdido_min"]), ("LACUNA", 120, 120))
        r2 = qualidade.lacunas_historicas(self.con, 24, AGORA)["hardmob"]   # sem estimativa: nao afirma perda
        self.assertEqual((r2["lacunas"][0]["situacao"], r2["perdido_total_min"]), ("indeterminada (cobertura desconhecida)", 0))

    def test_lista_estatica_de_cupons_nao_gera_lacuna(self):
        t = AGORA - dt.timedelta(hours=6)
        self.ciclo("meliuz", t)
        self.ciclo("meliuz", t + dt.timedelta(hours=5))
        self.assertNotIn("meliuz", qualidade.lacunas_historicas(self.con, 24, AGORA, {"meliuz": {"lista_estatica": True}}))

    def test_ciclo_com_erro_nao_conta_como_leitura(self):
        t = AGORA - dt.timedelta(hours=3)
        self.ciclo("promobit", t, cobertura=30)
        self.ciclo("promobit", t + dt.timedelta(minutes=10), cobertura=None, status="erro")  # falhou: nao leu
        self.ciclo("promobit", t + dt.timedelta(minutes=120), cobertura=30)
        r = qualidade.lacunas_historicas(self.con, 24, AGORA)["promobit"]
        self.assertEqual(r["lacunas"][0]["sem_ler_min"], 120)  # a janela vai da ultima leitura BOA ate a proxima


if __name__ == "__main__":
    unittest.main()
