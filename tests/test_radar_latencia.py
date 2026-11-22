"""Latencia (radar/latencia.py): MEDIDO x ESTIMADO, cobertura x intervalo e chance de ler promocao curta."""

import datetime as dt
import json
import os
import tempfile
import unittest
from unittest import mock

from radar import db, latencia

AGORA = dt.datetime(2026, 11, 21, 20, 0)


def ciclos(inicio, n, passo_min=10):
    return [inicio + dt.timedelta(minutes=passo_min * i) for i in range(n)]


class ChanceDeLeituraTest(unittest.TestCase):
    def test_ciclos_regulares_de_10_min(self):
        inst = ciclos(AGORA, 50)
        self.assertEqual(latencia.chance_de_leitura(inst, 5), 0.5)
        self.assertEqual(latencia.chance_de_leitura(inst, 3), 0.3)
        self.assertEqual(latencia.chance_de_leitura(inst, 10), 1.0)
        self.assertEqual(latencia.chance_de_leitura(inst, 15), 1.0)

    def test_uma_janela_longa_sem_ler_derruba_a_chance(self):
        inst = ciclos(AGORA, 10) + ciclos(AGORA + dt.timedelta(minutes=90 + 120), 10)   # 120 min sem ler no meio
        self.assertEqual(latencia.chance_de_leitura(inst, 10), 0.633)   # 190 min lidos em 300: a janela de 120 min sem ler pesa

    def test_sem_ciclos_suficientes_nao_inventa_numero(self):
        self.assertIsNone(latencia.chance_de_leitura([AGORA], 5))


class RegistroTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        p = mock.patch.dict(os.environ, {"CENTRAL_COMPRAS_DADOS_PRIVADOS": self._tmp.name})
        p.start()
        self.con = db.abrir()
        self.addCleanup(self._tmp.cleanup)
        self.addCleanup(self.con.close)
        self.addCleanup(p.stop)

    def _ciclo(self, fonte, quando, cobertura):
        self.con.execute("INSERT INTO coletas_ciclo (ciclo_em, fonte, status, itens, descartes_json) VALUES (?,?,?,?,?)",
                         (quando.strftime("%Y-%m-%d %H:%M:%S"), fonte, "ok", 5, json.dumps({"cobertura_min": cobertura})))
        self.con.commit()

    def _oferta(self, fonte, n, publicado, detectado):
        self.con.execute("INSERT INTO ofertas (titulo, url, url_norm, loja, produto, preco_anunciado, fonte, id_externo, publicado_em, detectado_em, ultima_vista_em) "
                         "VALUES (?,?,?,?,?,?,?,?,?,?,?)", ("t", f"u{n}", f"u{n}", "L", "p", 1.0, fonte, str(n), publicado, detectado, detectado))
        self.con.commit()

    def test_registrar_nunca_levanta_e_ler_devolve_so_a_janela(self):
        latencia.registrar("despacho", t_despacho_s=0.01)
        self.assertEqual(len(latencia.ler(1)), 1)
        self.assertEqual(latencia.ler(1, dt.datetime.now() + dt.timedelta(days=2)), [])
        with mock.patch("radar.latencia.caminhos.radar_dir", side_effect=OSError("disco cheio")):
            latencia.registrar("x")   # nao pode derrubar quem esta medindo

    def test_entrega_e_estimada_ate_existir_envio_medido(self):
        a = latencia.analisar(self.con, 24, AGORA)
        self.assertFalse(a["entrega_alerta_s"]["medido"])
        self.assertEqual(a["entrega_alerta_s"]["estimativa_inferior_s"], 4.0)
        self.assertIn("ESTIMADO", latencia.formatar(a))
        agora_real = dt.datetime.now()
        latencia.registrar("envio_alerta", ok=True, duracao_s=6.5, chars=900, espera_s=12.0)
        latencia.registrar("envio_alerta", ok=False, duracao_s=40.0, chars=900, espera_s=None)   # falha nao entra na medida
        b = latencia.analisar(self.con, 24, agora_real + dt.timedelta(minutes=1))
        self.assertTrue(b["entrega_alerta_s"]["medido"])
        self.assertEqual((b["entrega_alerta_s"]["n"], b["entrega_alerta_s"]["p50"]), (1, 6.5))
        self.assertEqual(b["candidato_ate_envio_s"]["p50"], 12.0)

    def test_oferta_antiga_lida_pela_primeira_vez_nao_conta_como_latencia(self):
        self._oferta("gatry", 1, "2026-11-21 19:50", "2026-11-21 19:57")   # 7 min: chegada fresca
        self._oferta("gatry", 2, "2026-11-21 19:40", "2026-11-21 19:52")   # 12 min
        self._oferta("gatry", 3, "2026-11-20 10:00", "2026-11-21 19:30")   # velha: carga inicial
        self._oferta("hardmob", 4, None, "2026-11-21 19:30")               # sem hora: nao medido
        a = latencia.analisar(self.con, 24, AGORA)["publicacao_ate_deteccao_min"]
        self.assertEqual((a["gatry"]["n"], a["gatry"]["max"], a["gatry"]["antigas_lidas_pela_1a_vez"]), (2, 12.0, 1))
        self.assertFalse(a["hardmob"]["medido"])
        self.assertIn("NAO MEDIDO", a["hardmob"]["nota"])

    def test_cobertura_x_intervalo_classifica_suficiente_curta_e_insuficiente(self):
        for i, t in enumerate(ciclos(AGORA - dt.timedelta(hours=2), 12)):
            self._ciclo("a_ok", t, 60)
            self._ciclo("b_curta", t, 14)
            self._ciclo("c_insuf", t, 8)
        cfg = {k: {"intervalo_min": 10} for k in ("a_ok", "b_curta", "c_insuf")}
        f = latencia.analisar(self.con, 24, AGORA, cfg)["fontes"]
        self.assertEqual(f["a_ok"]["avaliacao_cobertura"], "suficiente")
        self.assertTrue(f["b_curta"]["avaliacao_cobertura"].startswith("margem CURTA"))
        self.assertTrue(f["c_insuf"]["avaliacao_cobertura"].startswith("INSUFICIENTE"))
        self.assertEqual(f["a_ok"]["chance_de_ler_promocao_de"]["5 min"], 0.5)

    def test_lista_estatica_fica_fora(self):
        for t in ciclos(AGORA - dt.timedelta(hours=2), 3, 90):
            self._ciclo("meliuz", t, None)
        self.assertNotIn("meliuz", latencia.analisar(self.con, 24, AGORA, {"meliuz": {"lista_estatica": True}})["fontes"])


if __name__ == "__main__":
    unittest.main()
