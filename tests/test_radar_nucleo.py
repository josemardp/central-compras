"""Testes do nucleo do radar: banco, trava, historico, fila de reenvio, ciclo e executor de jobs.

Sem rede, sem WhatsApp e sem tocar nos dados reais (tudo em pasta temporaria).
"""

import datetime as dt
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from radar import ciclo, db, historico, jobs, outbox, trava


def _coleta(hora, modelos, erros=0):
    """modelos: {chave: preco|None}. `erros` = quantos timeouts de navegacao a rodada teve."""
    dados = {
        "coletado_em": hora,
        "modelos": {
            k: {"nome": k, "melhor_preco": v, "melhor_onde": "Loja" if v else "indisponivel"} for k, v in modelos.items()
        },
    }
    for i in range(erros):
        dados["modelos"][next(iter(modelos))].setdefault("fontes", {})[f"f{i}"] = {
            "erro": "Page.goto: Timeout 25000ms exceeded."
        }
    return dados


class TempBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        patcher = mock.patch.dict(os.environ, {"CENTRAL_COMPRAS_DADOS_PRIVADOS": str(self.dir)})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self._tmp.cleanup)


class BancoTest(TempBase):
    def test_migracao_cria_esquema_e_e_idempotente(self):
        con = db.abrir()
        self.assertEqual(db.versao_aplicada(con), db.VERSAO_ATUAL)
        tabelas = {r["name"] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for t in ("observacoes", "ofertas", "alertas", "execucoes", "jobs_estado", "fontes_saude", "outbox"):
            self.assertIn(t, tabelas)
        con.close()
        con = db.abrir()  # segunda abertura nao reaplica
        self.assertEqual(db.migrar(con), [])
        con.close()

    def test_rollback_remove_tabelas_e_backup_preserva_dados(self):
        con = db.abrir()
        con.execute("INSERT INTO outbox (criado_em, texto) VALUES ('2026-11-20 10:00:00','oi')")
        con.commit()
        con.close()
        copia = db.backup(motivo="teste")
        self.assertTrue(copia and copia.exists())
        con = db.abrir(migrar_automatico=False)
        self.assertEqual(db.reverter(con, 0), list(range(db.VERSAO_ATUAL, 0, -1)))  # desfaz todas, da mais nova a mais antiga
        tabelas = {r["name"] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertNotIn("outbox", tabelas)
        con.close()
        restaurado = db._conectar(copia)
        self.assertEqual(restaurado.execute("SELECT COUNT(*) AS n FROM outbox").fetchone()["n"], 1)
        restaurado.close()


class TravaTest(TempBase):
    def test_segunda_trava_do_mesmo_nome_falha_e_libera_ao_sair(self):
        with trava.trava("job-x"):
            with self.assertRaises(trava.TravaOcupada):
                with trava.trava("job-x"):
                    pass
        with trava.trava("job-x"):  # liberada
            pass

    def test_trava_de_processo_morto_e_tomada(self):
        caminho = Path(self.dir) / "radar" / "travas" / "job-y.lock"
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text(json.dumps({"pid": 999999, "desde": 0}), encoding="utf-8")
        with trava.trava("job-y"):
            pass


class HistoricoTest(TempBase):
    BOM = _coleta("2026-11-20 08:00", {"a": 100.0, "b": 200.0, "c": 300.0, "d": 400.0, "e": 500.0})

    def test_rodada_com_timeouts_e_perdas_e_degradada(self):
        ruim = _coleta("2026-11-20 14:34", {"a": 100.0, "b": None, "c": None, "d": 400.0, "e": 500.0}, erros=9)
        degradada, motivo = historico.esta_degradada(ruim, self.BOM)
        self.assertTrue(degradada)
        self.assertIn("estouraram o tempo", motivo)

    def test_perda_isolada_sem_sinal_de_rede_nao_e_degradacao(self):
        # um produto realmente esgotado nao pode disparar alarme de coleta ruim
        esgotou = _coleta("2026-11-20 14:00", {"a": 100.0, "b": None, "c": 300.0, "d": 400.0, "e": 500.0})
        self.assertFalse(historico.esta_degradada(esgotou, self.BOM)[0])

    def test_perda_de_metade_ou_mais_e_degradacao_mesmo_sem_timeout(self):
        quase_tudo = _coleta("2026-11-20 14:00", {"a": None, "b": None, "c": None, "d": 400.0, "e": 500.0})
        self.assertTrue(historico.esta_degradada(quase_tudo, self.BOM)[0])

    def test_modelo_unico_com_timeouts_e_sem_preco_e_degradado(self):
        bom = _coleta("2026-11-20 08:03", {"x": 111.89})
        ruim = _coleta("2026-11-20 14:44", {"x": None}, erros=3)
        self.assertTrue(historico.esta_degradada(ruim, bom)[0])

    def test_ultimo_estado_bom_ignora_rodada_degradada(self):
        ruim = _coleta("2026-11-20 14:34", {"a": None, "b": None, "c": None, "d": None, "e": None}, erros=9)
        self.assertEqual(historico.ultimo_estado_bom([self.BOM, ruim])["coletado_em"], "2026-11-20 08:00")

    def test_importacao_e_idempotente_e_nao_trata_none_como_zero(self):
        arq = self.dir / "historico.jsonl"
        ruim = _coleta("2026-11-20 14:34", {"a": None, "b": None, "c": None, "d": None, "e": None}, erros=9)
        arq.write_text("\n".join(json.dumps(r) for r in (self.BOM, ruim)) + "\n", encoding="utf-8")
        con = db.abrir()
        r1 = historico.importar_para_db(con, "rastreador-teste", arq)
        r2 = historico.importar_para_db(con, "rastreador-teste", arq)
        self.assertEqual(r1["observacoes_novas"], 10)
        self.assertEqual(r2["observacoes_novas"], 0)
        stats = historico.estatisticas(con, "a", agora=dt.datetime(2026, 11, 20, 18, 0))
        self.assertEqual(stats["historico_total"], {"n": 1, "menor": 100.0, "maior": 100.0, "mediana": 100.0})
        self.assertEqual(stats["ultimos_7_dias"]["n"], 1)
        con.close()

    def test_estatisticas_sem_dados_nao_inventam_serie(self):
        con = db.abrir()
        stats = historico.estatisticas(con, "inexistente")
        self.assertEqual(stats["observacoes_validas"], 0)
        self.assertIsNone(stats["ultimos_90_dias"]["menor"])
        con.close()


class OutboxTest(TempBase):
    def test_reenvio_so_marca_enviado_quando_confirma(self):
        con = db.abrir()
        outbox.enfileirar(con, "relatorio 14h", "rastreador-robos", "texto divergiu")
        falha = outbox.drenar(con, lambda t: (False, "caixa nao ficou pronta"))
        self.assertFalse(falha[0][1])
        self.assertEqual(outbox.contar_pendentes(con), 1)
        enviados = []
        ok = outbox.drenar(con, lambda t: (enviados.append(t) or True, "ok"))
        self.assertTrue(ok[0][1])
        self.assertIn("relatorio 14h", enviados[0])
        self.assertIn("Reenvio", enviados[0])
        self.assertEqual(outbox.contar_pendentes(con), 0)
        self.assertEqual(outbox.drenar(con, lambda t: (True, "ok")), [])  # nada a reenviar duas vezes
        con.close()


class CicloTest(TempBase):
    def setUp(self):
        super().setUp()
        p = mock.patch("radar.maquina.pode_rodar", return_value=(True, "teste"))  # independe de qual maquina roda a suite
        p.start()
        self.addCleanup(p.stop)

    def _rodar(self, coletas, enviar_ok=True, anterior=None, enviar_zap=True):
        estado = self.dir / "estado.json"
        hist = self.dir / "historico.jsonl"
        if anterior:
            hist.write_text(json.dumps(anterior) + "\n", encoding="utf-8")
            estado.write_text(json.dumps(anterior), encoding="utf-8")
        fila = list(coletas)
        enviados = []

        def enviar(texto):
            enviados.append(texto)
            return (enviar_ok, "ok" if enviar_ok else "texto divergiu")

        with mock.patch("builtins.print"):
            codigo = ciclo.executar_ciclo(
                rotulo="teste", origem="rastreador-teste",
                coletar=lambda: fila.pop(0) if len(fila) > 1 else fila[0],
                montar_mensagem=lambda atual, anterior, primeira_vez=False: f"MSG {atual['coletado_em']}",
                estado_path=estado, hist_path=hist, enviar_zap=enviar_zap, enviar_fn=enviar,
                pausa_retentativa_s=0,
            )
        return codigo, estado, hist, enviados

    def test_coleta_boa_grava_estado_historico_e_envia(self):
        bom = _coleta("2026-11-20 20:00", {"a": 100.0})
        codigo, estado, hist, enviados = self._rodar([bom])
        self.assertEqual(codigo, 0)
        self.assertEqual(json.loads(estado.read_text(encoding="utf-8"))["coletado_em"], "2026-11-20 20:00")
        self.assertEqual(len(hist.read_text(encoding="utf-8").splitlines()), 1)
        self.assertEqual(enviados, ["MSG 2026-11-20 20:00"])

    def test_coleta_degradada_nao_sobrescreve_estado_e_avisa_no_relatorio(self):
        anterior = _coleta("2026-11-20 08:00", {"a": 100.0, "b": 200.0})
        ruim = _coleta("2026-11-20 14:34", {"a": None, "b": None}, erros=6)
        codigo, estado, hist, enviados = self._rodar([ruim], anterior=anterior)
        self.assertEqual(json.loads(estado.read_text(encoding="utf-8"))["coletado_em"], "2026-11-20 08:00")
        linhas = [json.loads(l) for l in hist.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(linhas), 2)
        self.assertTrue(linhas[-1].get("degradada"))
        self.assertIn("Coleta parcial", enviados[0])

    def test_segunda_tentativa_recupera_coleta_degradada(self):
        anterior = _coleta("2026-11-20 08:00", {"a": 100.0, "b": 200.0})
        ruim = _coleta("2026-11-20 14:34", {"a": None, "b": None}, erros=6)
        boa = _coleta("2026-11-20 14:36", {"a": 99.0, "b": 201.0})
        codigo, estado, hist, enviados = self._rodar([ruim, boa], anterior=anterior)
        self.assertEqual(json.loads(estado.read_text(encoding="utf-8"))["coletado_em"], "2026-11-20 14:36")
        self.assertNotIn("Coleta parcial", enviados[0])

    def test_falha_no_envio_enfileira_e_proximo_ciclo_reenvia(self):
        bom = _coleta("2026-11-20 14:00", {"a": 100.0})
        codigo, *_ = self._rodar([bom], enviar_ok=False)
        self.assertEqual(codigo, 1)
        con = db.abrir()
        self.assertEqual(outbox.contar_pendentes(con), 1)
        con.close()
        bom2 = _coleta("2026-11-20 20:00", {"a": 98.0})
        codigo, _, _, enviados = self._rodar([bom2], enviar_ok=True)
        self.assertEqual(codigo, 0)
        self.assertEqual(len(enviados), 2)  # o novo e o reenvio do das 14h
        self.assertIn("Reenvio", enviados[1])
        con = db.abrir()
        self.assertEqual(outbox.contar_pendentes(con), 0)
        con.close()

    def test_dry_run_nao_persiste_nada(self):
        bom = _coleta("2026-11-20 20:00", {"a": 100.0})
        estado = self.dir / "estado.json"
        hist = self.dir / "historico.jsonl"
        with mock.patch("builtins.print"):
            ciclo.executar_ciclo(
                rotulo="t", origem="o", coletar=lambda: bom,
                montar_mensagem=lambda a, b, primeira_vez=False: "m", estado_path=estado, hist_path=hist,
                enviar_zap=False, enviar_fn=lambda t: (True, ""), persistir=False,
            )
        self.assertFalse(estado.exists())
        self.assertFalse(hist.exists())


class JobsTest(TempBase):
    def _cfg(self, passos, seguir=True):
        return {"jobs": {"t": {"trava": "t", "continuar_apos_falha": seguir, "passos": passos}}, "agendamentos": []}

    def test_passo_que_falha_nao_impede_os_seguintes(self):
        cfg = self._cfg([
            {"id": "ok1", "comando": ["{python}", "-c", "print('oi')"], "timeout_min": 1},
            {"id": "ruim", "comando": ["{python}", "-c", "import sys; sys.exit(3)"], "timeout_min": 1},
            {"id": "ok2", "comando": ["{python}", "-c", "print('tchau')"], "timeout_min": 1},
        ])
        self.assertEqual(jobs.executar_job("t", config=cfg), 1)
        con = db.abrir()
        status = {r["passo"]: r["status"] for r in con.execute("SELECT passo, status FROM execucoes")}
        self.assertEqual(status, {"ok1": "ok", "ruim": "falha", "ok2": "ok"})
        self.assertEqual(con.execute("SELECT falhas_consecutivas FROM jobs_estado").fetchone()[0], 1)
        con.close()

    def test_sem_continuar_apos_falha_para_no_primeiro_erro(self):
        cfg = self._cfg([
            {"id": "ruim", "comando": ["{python}", "-c", "import sys; sys.exit(1)"], "timeout_min": 1},
            {"id": "nunca", "comando": ["{python}", "-c", "print(1)"], "timeout_min": 1},
        ], seguir=False)
        jobs.executar_job("t", config=cfg)
        con = db.abrir()
        self.assertEqual([r["passo"] for r in con.execute("SELECT passo FROM execucoes")], ["ruim"])
        con.close()

    def test_timeout_mata_o_processo_e_registra(self):
        cfg = self._cfg([{"id": "lento", "comando": ["{python}", "-c", "import time; time.sleep(30)"], "timeout_min": 0.05}])
        self.assertEqual(jobs.executar_job("t", config=cfg), 1)
        con = db.abrir()
        self.assertEqual(con.execute("SELECT status FROM execucoes").fetchone()[0], "timeout")
        con.close()

    def test_execucao_morta_no_meio_e_marcada_interrompida_no_proximo_inicio(self):
        con = db.abrir()
        con.execute("INSERT INTO execucoes (job, passo, inicio, status) VALUES ('t','robos','2026-11-21 08:00:00','rodando')")
        con.commit()
        con.close()
        jobs.executar_job("t", config=self._cfg([{"id": "ok", "comando": ["{python}", "-c", "print(1)"], "timeout_min": 1}]))
        con = db.abrir()
        estados = [r["status"] for r in con.execute("SELECT status FROM execucoes ORDER BY id")]
        self.assertEqual(estados, ["interrompida", "ok"])
        con.close()

    def test_job_ja_em_execucao_e_ignorado_sem_duplicar(self):
        cfg = self._cfg([{"id": "x", "comando": ["{python}", "-c", "print(1)"], "timeout_min": 1}])
        with trava.trava("t"):
            self.assertEqual(jobs.executar_job("t", config=cfg), 0)
        con = db.abrir()
        self.assertEqual(con.execute("SELECT status FROM execucoes").fetchone()[0], "ignorada")
        con.close()

    def test_log_sai_em_utf8_com_acentos_e_emoji(self):
        cfg = self._cfg([{"id": "u", "comando": ["{python}", "-c", "print('relatório ❄️ ação')"], "timeout_min": 1}])
        jobs.executar_job("t", config=cfg)
        log = next((self.dir / "radar" / "logs").glob("t-*.log"))
        self.assertIn("relatório ❄️ ação", log.read_text(encoding="utf-8"))

    def test_proxima_execucao(self):
        agora = dt.datetime(2026, 11, 20, 18, 7)
        self.assertEqual(jobs.proxima_execucao({"horarios": ["08:00", "14:00", "20:00"]}, agora), dt.datetime(2026, 11, 20, 20, 0))
        self.assertEqual(jobs.proxima_execucao({"horarios": ["08:00"]}, agora), dt.datetime(2026, 11, 21, 8, 0))
        self.assertEqual(jobs.proxima_execucao({"a_cada_min": 10}, agora), dt.datetime(2026, 11, 20, 18, 10))

    def test_configuracao_real_e_valida(self):
        cfg = jobs.carregar_config()
        self.assertIn("relatorios", cfg["jobs"])
        self.assertEqual([p["id"] for p in cfg["jobs"]["relatorios"]["passos"]], ["robos", "ares", "chuveiro"])
        relatorios = next(a for a in cfg["agendamentos"] if a["job"] == "relatorios")
        self.assertEqual(relatorios["horarios"], ["08:00", "14:00", "20:00"])  # horarios preservados
        self.assertEqual(relatorios["tarefa"], "Central Compras - Rastrear Robos BF")
        self.assertGreaterEqual(relatorios["limite_execucao_min"], 30)


if __name__ == "__main__":
    unittest.main()
