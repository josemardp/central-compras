"""Janela da Black Friday (26 a 30/11/2026): Promobit a cada 5 min, volta sozinho ao normal, sem tocar nas outras fontes."""

import datetime as dt
import os
import tempfile
import unittest
from unittest import mock

import yaml

from radar import agenda_windows, caminhos, db, jobs, varredura

FONTES = varredura.carregar_fontes()
PROMOBIT = FONTES["promobit"]


class JanelaPorDataTest(unittest.TestCase):
    def cfg(self, quando):
        return varredura.cfg_efetiva(PROMOBIT, quando)

    def test_antes_dentro_e_depois_da_janela(self):
        normal, em = self.cfg(dt.datetime(2026, 11, 25, 23, 59))
        self.assertEqual((em, normal["intervalo_min"], normal["paginas_recentes"]), (False, 10, 5))
        dentro, em = self.cfg(dt.datetime(2026, 11, 27, 12, 0))
        self.assertEqual((em, dentro["intervalo_min"], dentro["paginas_recentes"]), (True, 5, 5))
        self.assertEqual(dentro["lojas"], PROMOBIT["lojas"])            # o resto da configuracao e preservado
        self.assertEqual(dentro["paginas_recentes"], PROMOBIT["paginas_recentes"])   # as 5 paginas NAO diminuem: no pico a lista cobre so ~14 min
        depois, em = self.cfg(dt.datetime(2026, 12, 1, 0, 0))
        self.assertEqual((em, depois["intervalo_min"], depois["paginas_recentes"]), (False, 10, 5))   # retorno AUTOMATICO, por data

    def test_limites_da_janela_sao_inclusivos(self):
        self.assertTrue(self.cfg(dt.datetime(2026, 11, 26, 0, 0))[1])
        self.assertTrue(self.cfg(dt.datetime(2026, 11, 30, 23, 59))[1])
        self.assertFalse(self.cfg(dt.datetime(2026, 11, 30, 23, 59, 1))[1])   # `ate` tem precisao de minuto: 23:59:01 ja esta fora

    def test_so_o_promobit_tem_janela_e_a_configuracao_base_nao_e_alterada(self):
        self.assertEqual([f for f, c in FONTES.items() if c.get("janela_intensiva")], ["promobit"])
        self.assertEqual(PROMOBIT["intervalo_min"], 10)
        self.assertNotIn("janela_intensiva", varredura.cfg_efetiva(PROMOBIT, dt.datetime(2026, 11, 27))[0])

    def test_janela_com_data_invalida_e_ignorada_sem_quebrar(self):
        self.assertEqual(varredura.cfg_efetiva({"intervalo_min": 10, "janela_intensiva": {"de": "x", "ate": "y"}}, dt.datetime.now()), ({"intervalo_min": 10, "janela_intensiva": {"de": "x", "ate": "y"}}, False))


class ExecucaoNaJanelaTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        p = mock.patch.dict(os.environ, {"CENTRAL_COMPRAS_DADOS_PRIVADOS": self._tmp.name})
        p.start()
        self.addCleanup(self._tmp.cleanup)
        self.addCleanup(p.stop)
        self.leituras = []

    def coletor(self, nome):
        def f(cfg):
            self.leituras.append((nome, cfg.get("intervalo_min"), cfg.get("paginas_recentes")))
            return []
        return f

    def rodar(self, quando, **kw):
        cols = {n: self.coletor(n) for n in ("promobit", "gatry")}
        fontes = {"promobit": dict(PROMOBIT), "gatry": {"intervalo_min": 10}}
        with mock.patch("builtins.print"):
            varredura.executar(enviar=False, coletores=cols, fontes_cfg=fontes, agora=quando, **kw)

    def test_dentro_da_janela_o_promobit_volta_a_cada_5_min_e_o_gatry_continua_a_cada_10(self):
        t = dt.datetime(2026, 11, 27, 10, 0, 0)
        self.rodar(t)
        self.rodar(t + dt.timedelta(minutes=5))      # tarefa extra: Promobit vence (5 min), Gatry nao (so passaram 5)
        self.rodar(t + dt.timedelta(minutes=10))
        self.assertEqual([x[0] for x in self.leituras], ["promobit", "gatry", "promobit", "promobit", "gatry"])
        self.assertTrue(all(x[1:] == (5, 5) for x in self.leituras if x[0] == "promobit"))   # configuracao da janela chegou ao coletor

    def test_fora_da_janela_o_promobit_so_vence_a_cada_10_min(self):
        t = dt.datetime(2026, 11, 22, 10, 0, 0)
        self.rodar(t)
        self.rodar(t + dt.timedelta(minutes=5))
        self.assertEqual([x[0] for x in self.leituras], ["promobit", "gatry"])
        self.assertEqual(self.leituras[0][1:], (10, 5))

    def test_so_fontes_nao_toca_nas_outras_e_registra_a_janela_na_telemetria(self):
        t = dt.datetime(2026, 11, 27, 10, 0, 0)
        self.rodar(t, so_fontes=["promobit"])
        self.assertEqual([x[0] for x in self.leituras], ["promobit"])
        con = db.abrir()
        try:
            import json
            d = json.loads(con.execute("SELECT descartes_json FROM coletas_ciclo WHERE fonte='promobit'").fetchone()[0])
            self.assertEqual((d["janela_intensiva"], d["intervalo_efetivo_min"]), (True, 5.0))
            self.assertEqual(con.execute("SELECT COUNT(*) FROM coletas_ciclo WHERE fonte='gatry'").fetchone()[0], 0)
        finally:
            con.close()


class TarefaDedicadaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = jobs.carregar_config()
        cls.ag = next(a for a in cls.cfg["agendamentos"] if a["job"] == "varredura_promobit_bf")

    def test_usa_a_mesma_trava_da_varredura_normal_para_nunca_sobrepor(self):
        self.assertEqual(self.cfg["jobs"]["varredura_promobit_bf"]["trava"], self.cfg["jobs"]["varredura"]["trava"])

    def test_comando_le_so_o_promobit_e_nao_roda_a_recuperacao_de_relatorios(self):
        passos = self.cfg["jobs"]["varredura_promobit_bf"]["passos"]
        self.assertEqual(len(passos), 1)
        self.assertEqual(passos[0]["comando"][-3:], ["varrer", "--so", "promobit"])

    def test_script_do_windows_tem_inicio_fim_expiracao_e_nao_sobrepoe_instancias(self):
        sc = agenda_windows._script_aplicar(self.ag, "python.exe", "C:/x", caminhos.backups_dir() / "x.xml")
        for trecho in ("-At '2026-11-26 00:05'", "EndBoundary = '2026-12-01T00:00:00'", "-DeleteExpiredTaskAfter (New-TimeSpan -Hours 24)",
                       "-MultipleInstances IgnoreNew", "executar varredura_promobit_bf", "-RepetitionInterval (New-TimeSpan -Minutes 10)"):
            self.assertIn(trecho, sc)
        self.assertNotIn("-StartWhenAvailable", sc)                 # atraso nao se recupera: so 1 leitura por tick

    def test_criar_so_a_tarefa_da_black_friday_nao_toca_nas_existentes(self):
        """`agendar --aplicar --job varredura_promobit_bf` gera um unico Register-ScheduledTask: relatorios 08/14/20h e varredura normal ficam intactos."""
        filtrado = dict(self.cfg)
        filtrado["agendamentos"] = [a for a in self.cfg["agendamentos"] if a["job"] == "varredura_promobit_bf"]
        scripts = agenda_windows.aplicar(filtrado, so_mostrar=True)
        self.assertEqual([r["tarefa"] for r in scripts], ["Central Compras - Radar Promobit BF"])
        self.assertEqual(scripts[0]["script"].count("Register-ScheduledTask"), 1)

    def test_as_tarefas_existentes_nao_mudaram(self):
        normal = next(a for a in self.cfg["agendamentos"] if a["job"] == "varredura")
        sc = agenda_windows._script_aplicar(normal, "python.exe", "C:/x", caminhos.backups_dir() / "x.xml")
        self.assertIn("-At '00:00'", sc)
        self.assertIn("-RepetitionDuration (New-TimeSpan -Days 3650)", sc)
        self.assertNotIn("EndBoundary", sc)
        self.assertNotIn("DeleteExpiredTaskAfter", sc)


class FrequenciaEfetivaDoPromobitTest(unittest.TestCase):
    """A tarefa extra dispara em :05, mas quem decide se o Promobit e LIDO e `_vencida`. Prova por simulacao dos disparos reais, nao pela agenda."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        p = mock.patch.dict(os.environ, {"CENTRAL_COMPRAS_DADOS_PRIVADOS": self._tmp.name})
        p.start()
        self.addCleanup(self._tmp.cleanup)
        self.addCleanup(p.stop)
        self.leituras = {"promobit": [], "gatry": []}

    def simular(self, inicio, horas, com_tarefa_bf, atrasos):
        """Disparos de 5 em 5 min: a cada :00/:10 a varredura NORMAL (todas as fontes) e, se existir, a tarefa BF em :05/:15 (so o Promobit).
        `atrasos` e a lista (em segundos) de atraso do agendador, aplicada em ciclo."""
        fontes = {"promobit": dict(PROMOBIT), "gatry": {"intervalo_min": 10}}
        cols = {n: (lambda cfg, n=n: self.leituras[n].append(self.agora) or []) for n in self.leituras}
        n = 0
        t = inicio
        fim = inicio + dt.timedelta(hours=horas)
        while t < fim:
            normal = t.minute % 10 == 0
            if normal or com_tarefa_bf:
                self.agora = t + dt.timedelta(seconds=atrasos[n % len(atrasos)])
                with mock.patch("builtins.print"):
                    varredura.executar(enviar=False, coletores=cols, fontes_cfg=fontes, agora=self.agora, so_fontes=None if normal else ["promobit"])
            t += dt.timedelta(minutes=5)
            n += 1

    def espacamentos(self, fonte):
        v = self.leituras[fonte]
        return [(b - a).total_seconds() for a, b in zip(v, v[1:])]

    def test_na_janela_com_a_tarefa_o_promobit_e_lido_a_cada_5_min_sem_duplicar(self):
        self.simular(dt.datetime(2026, 11, 27, 10, 0, 0), 2, True, [2, 3, 1, 2, 4, 2])
        sp = self.espacamentos("promobit")
        self.assertEqual(len(self.leituras["promobit"]), 24)                    # 12 por hora: UMA leitura a cada disparo
        self.assertGreaterEqual(min(sp), 240)                                   # nunca duas leituras coladas
        self.assertLessEqual(max(sp), 310)                                      # e nunca um buraco de 10 min
        self.assertEqual(len(self.leituras["gatry"]), 12)                       # as outras fontes NAO mudam: 6 por hora

    def test_atraso_do_agendador_de_ate_50_s_nao_derruba_a_leitura_para_10_min(self):
        # alterna atrasos grandes e pequenos: antes da folga de 60 s a leitura de :05 era pulada quando a anterior tinha comecado 25 s atrasada
        self.simular(dt.datetime(2026, 11, 27, 10, 0, 0), 2, True, [45, 0, 30, 5, 50, 0])
        self.assertEqual(len(self.leituras["promobit"]), 24)
        self.assertLessEqual(max(self.espacamentos("promobit")), 360)

    def test_fora_da_janela_a_tarefa_extra_nao_gera_leitura_a_mais(self):
        self.simular(dt.datetime(2026, 11, 22, 10, 0, 0), 2, True, [2, 3])
        self.assertEqual(len(self.leituras["promobit"]), 12)                    # so 6 por hora: o disparo de :05 e pulado (smoke test de 21/11)
        self.assertGreaterEqual(min(self.espacamentos("promobit")), 540)

    def test_na_janela_sem_a_tarefa_o_ganho_e_nenhum(self):
        self.simular(dt.datetime(2026, 11, 27, 10, 0, 0), 2, False, [2, 3])
        self.assertEqual(len(self.leituras["promobit"]), 12)                    # sem a tarefa so ha disparo de 10 em 10 min

    def test_duas_execucoes_no_mesmo_instante_nao_duplicam_a_requisicao(self):
        fontes = {"promobit": dict(PROMOBIT)}
        cols = {"promobit": lambda cfg: self.leituras["promobit"].append(1) or []}
        t = dt.datetime(2026, 11, 27, 10, 0, 0)
        for _ in range(3):
            with mock.patch("builtins.print"):
                varredura.executar(enviar=False, coletores=cols, fontes_cfg=fontes, agora=t, so_fontes=["promobit"])
        self.assertEqual(len(self.leituras["promobit"]), 1)
        with mock.patch("builtins.print"):
            varredura.executar(enviar=False, coletores=cols, fontes_cfg=fontes, agora=t + dt.timedelta(seconds=200), so_fontes=["promobit"])   # 200 s: ainda cedo
        self.assertEqual(len(self.leituras["promobit"]), 1)
        with mock.patch("builtins.print"):
            varredura.executar(enviar=False, coletores=cols, fontes_cfg=fontes, agora=t + dt.timedelta(seconds=245), so_fontes=["promobit"])   # 245 s: vence
        self.assertEqual(len(self.leituras["promobit"]), 2)

    def test_intervalo_de_10_min_ou_mais_mantem_a_folga_de_20_s(self):
        con = db.abrir()
        try:
            varredura._saude(con, "x", True, 1, None, dt.datetime(2026, 11, 22, 10, 0, 0))
            self.assertFalse(varredura._vencida(con, "x", 10, dt.datetime(2026, 11, 22, 10, 9, 30)))   # 570 s < 580
            self.assertTrue(varredura._vencida(con, "x", 10, dt.datetime(2026, 11, 22, 10, 9, 45)))    # 585 s >= 580
        finally:
            con.close()


class ConcorrenciaDasTarefasTest(unittest.TestCase):
    """Normal e Black Friday dividem a trava `varredura`: a que chegar com a outra rodando e IGNORADA (nunca roda em cima)."""

    def test_job_da_black_friday_e_ignorado_se_a_varredura_normal_esta_rodando(self):
        import sys
        from pathlib import Path
        from radar import trava
        with tempfile.TemporaryDirectory() as dados, tempfile.TemporaryDirectory() as pasta, mock.patch.dict(os.environ, {"CENTRAL_COMPRAS_DADOS_PRIVADOS": dados}):
            marca = Path(pasta) / "rodou.txt"
            cfg = {"jobs": {"varredura_promobit_bf": {"trava": "varredura", "continuar_apos_falha": False, "respeita_maquina_oficial": False,
                                                       "passos": [{"id": "x", "comando": [sys.executable, "-c", f"open(r'{marca}','w').write('1')"], "timeout_min": 1}]}}}
            with trava.trava("varredura", pasta=Path(pasta)):              # a varredura normal esta rodando
                codigo = jobs.executar_job("varredura_promobit_bf", config=cfg, pasta_trava=Path(pasta))
            self.assertEqual(codigo, 0)
            self.assertFalse(marca.exists())                                # o comando NAO foi executado
            con = db.abrir()
            try:
                self.assertEqual(con.execute("SELECT status FROM execucoes WHERE job='varredura_promobit_bf'").fetchone()[0], "ignorada")
            finally:
                con.close()
            codigo = jobs.executar_job("varredura_promobit_bf", config=cfg, pasta_trava=Path(pasta))   # liberada: agora roda
            self.assertEqual(codigo, 0)
            self.assertTrue(marca.exists())

    def test_a_tarefa_do_windows_ignora_nova_instancia_e_nao_recupera_disparo_perdido(self):
        ag = next(a for a in jobs.carregar_config()["agendamentos"] if a["job"] == "varredura_promobit_bf")
        sc = agenda_windows._script_aplicar(ag, "python.exe", "C:/x", caminhos.backups_dir() / "x.xml")
        self.assertIn("-MultipleInstances IgnoreNew", sc)
        self.assertNotIn("-StartWhenAvailable", sc)


class UltimoDisparoTest(unittest.TestCase):
    def test_ultimo_disparo_programado_e_30_11_as_23h55_com_fim_em_01_12(self):
        ag = next(a for a in jobs.carregar_config()["agendamentos"] if a["job"] == "varredura_promobit_bf")
        sc = agenda_windows._script_aplicar(ag, "python.exe", "C:/x", caminhos.backups_dir() / "x.xml")
        ini = dt.datetime.strptime(ag["inicio"], "%Y-%m-%d %H:%M")
        m = __import__("re").search(r"-RepetitionDuration \(New-TimeSpan -Minutes (\d+)\)", sc)
        self.assertIsNotNone(m, sc)
        duracao = dt.timedelta(minutes=int(m.group(1)))
        passo = dt.timedelta(minutes=int(ag["a_cada_min"]))
        disparos = [ini + passo * k for k in range(int(duracao / passo) + 1)]       # o Windows dispara enquanto decorrido <= duracao
        self.assertEqual(disparos[0], dt.datetime(2026, 11, 26, 0, 5))
        self.assertEqual(disparos[-1], dt.datetime(2026, 11, 30, 23, 55))           # ULTIMO disparo
        self.assertGreater(disparos[-1] + passo, dt.datetime(2026, 12, 1, 0, 0))   # o disparo seguinte (01/12 00:05) cairia DEPOIS do encerramento e nao ocorre
        self.assertIn("EndBoundary = '2026-12-01T00:00:00'", sc)                    # encerramento em 01/12 00:00 preservado
        self.assertIn("-DeleteExpiredTaskAfter (New-TimeSpan -Hours 24)", sc)       # exclusao automatica preservada


if __name__ == "__main__":
    unittest.main()
