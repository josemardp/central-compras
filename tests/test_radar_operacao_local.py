"""Estado operacional LOCAL (operacao.yaml, fora do Git): a ativacao nao pode ser desligada em silencio por git pull/restore/reset
nem publicada por engano, e uma instalacao nova (sem o arquivo) fica em SOMBRA."""

import argparse
import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from radar import ativacao, cli, db, piloto, ranking

VERSIONADO = """# regras versionadas (no Git): ativacao DESLIGADA
prioridade:
  orcamento_diario: 6
  max_por_ciclo: 2

piloto:
  ativo: false
  produtos_exatos: [elgin_12k]
  orcamento_diario: 2
  orcamento_critico_diario: 1
  orcamento_excecao_diario: 0
  max_por_ciclo: 1
  max_criticos_por_ciclo: 1
  max_total_por_ciclo: 1
  destinatario_confirmado_em: "2026-11-21 21:21"

alertas:
  enviar: false
  homologado_em: null   # comentario que precisa sobreviver
  status_enviaveis: [PROVAVEL, VALIDADO]
"""
LIGADO = {"alertas": {"enviar": True, "homologado_em": "2026-11-22 09:03"}, "piloto": {"ativo": True}}


class Base(unittest.TestCase):
    def setUp(self):
        self._dados, self._cfg = tempfile.TemporaryDirectory(), tempfile.TemporaryDirectory()
        pe = mock.patch.dict(os.environ, {"CENTRAL_COMPRAS_DADOS_PRIVADOS": self._dados.name})
        pe.start()
        for c in (self._dados.cleanup, self._cfg.cleanup, pe.stop):
            self.addCleanup(c)
        self.dir = Path(self._cfg.name)
        self.versionado = self.dir / "radar_regras.yaml"
        self.versionado.write_text(VERSIONADO, encoding="utf-8")
        for alvo, valor in (("radar.ativacao.caminhos.CONFIG_DIR", self.dir), ("radar.ranking.ARQ_REGRAS", self.versionado)):
            p = mock.patch(alvo, valor)
            p.start()
            self.addCleanup(p.stop)

    def ligar_local(self):
        return ranking.gravar_operacao(LIGADO, {"ativado_em": "2026-11-22 09:03"})


class CamadaOperacionalTest(Base):
    def test_instalacao_nova_sem_o_arquivo_fica_em_sombra(self):
        r = ranking.carregar_regras()
        self.assertEqual(piloto.modo(r), "SOMBRA")
        self.assertFalse(r["_operacao"]["presente"])
        self.assertFalse(ranking.arquivo_operacao().exists())      # ler nao cria o arquivo

    def test_arquivo_local_liga_o_piloto_sem_tocar_o_versionado(self):
        antes = self.versionado.read_text(encoding="utf-8")
        self.ligar_local()
        r = ranking.carregar_regras()
        self.assertEqual(piloto.modo(r), "PILOTO")
        self.assertEqual(r["alertas"]["homologado_em"], "2026-11-22 09:03")
        self.assertEqual(sorted(r["_operacao"]["aplicado"]), ["alertas.enviar", "alertas.homologado_em", "piloto.ativo"])
        self.assertEqual(self.versionado.read_text(encoding="utf-8"), antes)   # o versionado continua desligado e identico
        self.assertEqual(r["piloto"]["destinatario_confirmado_em"], "2026-11-21 21:21")   # o resto do piloto vem do versionado

    def test_git_restore_ou_pull_do_versionado_nao_desliga_o_piloto(self):
        self.ligar_local()
        self.versionado.write_text(VERSIONADO, encoding="utf-8")   # o que `git restore`/`reset --hard`/`pull` fariam
        self.assertEqual(piloto.modo(ranking.carregar_regras()), "PILOTO")

    def test_apagar_o_arquivo_local_volta_a_sombra(self):
        p = self.ligar_local()
        p.unlink()
        self.assertEqual(piloto.modo(ranking.carregar_regras()), "SOMBRA")

    def test_arquivo_ilegivel_e_seguro_e_avisa(self):
        arq = ranking.arquivo_operacao()
        arq.parent.mkdir(parents=True, exist_ok=True)
        arq.write_text("alertas: [isto nao: e valido\n  :::", encoding="utf-8")
        r = ranking.carregar_regras()
        self.assertEqual(piloto.modo(r), "SOMBRA")
        self.assertTrue(any("ilegivel" in a for a in r["_operacao"]["avisos"]))

    def test_so_as_tres_chaves_com_tipo_certo_valem(self):
        arq = ranking.arquivo_operacao()
        arq.parent.mkdir(parents=True, exist_ok=True)
        arq.write_text('alertas:\n  enviar: "true"\n  homologado_em: 123\n  limite_diario: 99\npiloto:\n  ativo: true\n  orcamento_diario: 99\n'
                       'prioridade:\n  orcamento_diario: 99\n', encoding="utf-8")
        r = ranking.carregar_regras()
        self.assertIs(r["alertas"]["enviar"], False)               # string "true" nao liga nada
        self.assertIsNone(r["alertas"]["homologado_em"])
        self.assertEqual(r["piloto"]["orcamento_diario"], 2)       # o arquivo local nunca altera limite
        self.assertEqual(r["prioridade"]["orcamento_diario"], 6)
        self.assertNotIn("limite_diario", r["alertas"])
        self.assertTrue(r["_operacao"]["avisos"])
        self.assertEqual(piloto.modo(r), "SOMBRA")

    def test_data_sem_aspas_com_segundos_e_aceita_e_normalizada(self):
        arq = ranking.arquivo_operacao()
        arq.parent.mkdir(parents=True, exist_ok=True)
        arq.write_text("alertas:\n  enviar: true\n  homologado_em: 2026-11-22 09:03:00\npiloto:\n  ativo: true\n", encoding="utf-8")
        r = ranking.carregar_regras()
        self.assertEqual(r["alertas"]["homologado_em"], "2026-11-22 09:03")
        self.assertEqual(piloto.modo(r), "PILOTO")

    def test_sem_homologado_em_continua_em_sombra(self):
        ranking.gravar_operacao({"alertas": {"enviar": True}, "piloto": {"ativo": True}})
        self.assertEqual(piloto.modo(ranking.carregar_regras()), "SOMBRA")

    def test_cenarios_e_ensaios_ignoram_a_camada_viva(self):
        self.ligar_local()
        self.assertEqual(piloto.modo(ranking.carregar_regras(operacao=False)), "SOMBRA")
        self.assertEqual(piloto.modo(ranking.carregar_regras(self.versionado)), "SOMBRA")   # caminho explicito tambem

    def test_gravacao_atomica_preserva_metadados_e_nao_deixa_temporario(self):
        self.ligar_local()
        ranking.gravar_operacao({"alertas": {"enviar": False}})
        d = ranking.carregar_regras()
        self.assertIs(d["alertas"]["enviar"], False)
        self.assertEqual(d["alertas"]["homologado_em"], "2026-11-22 09:03")   # nao mencionada: preservada
        self.assertEqual([p.name for p in ranking.arquivo_operacao().parent.glob(".operacao-*")], [])
        self.assertIn("ativado_em", ranking.arquivo_operacao().read_text(encoding="utf-8"))


class KillSwitchLocalTest(Base):
    def test_desliga_no_arquivo_local_e_nao_reescreve_o_versionado_desligado(self):
        self.ligar_local()
        antes, mtime = self.versionado.read_bytes(), self.versionado.stat().st_mtime_ns
        ok, info = ativacao.desligar()
        self.assertTrue(ok, info)
        r = ranking.carregar_regras()
        self.assertEqual(piloto.modo(r), "SOMBRA")
        self.assertIs(r["alertas"]["enviar"], False)
        self.assertIsNone(r["alertas"]["homologado_em"])
        self.assertTrue(r["piloto"]["ativo"])                       # so desliga o envio; o resto do estado local e preservado
        self.assertEqual(self.versionado.read_bytes(), antes)       # versionado intocado (nem regravado)
        self.assertEqual(self.versionado.stat().st_mtime_ns, mtime)
        self.assertIn("desligado_em", ranking.arquivo_operacao().read_text(encoding="utf-8"))

    def test_desliga_tambem_o_versionado_se_alguem_o_deixou_ligado(self):
        self.versionado.write_text(VERSIONADO.replace("enviar: false", "enviar: true").replace("homologado_em: null", 'homologado_em: "2026-11-22 09:00"'),
                                   encoding="utf-8")
        self.assertEqual(piloto.modo(ranking.carregar_regras()), "COMPLETO")   # ligado so no versionado (legado)
        ok, _ = ativacao.desligar()
        self.assertTrue(ok)
        self.assertEqual(piloto.modo(ranking.carregar_regras()), "SOMBRA")
        self.assertIn("# comentario que precisa sobreviver", self.versionado.read_text(encoding="utf-8"))

    def test_o_local_desligado_vence_um_versionado_ligado(self):
        self.versionado.write_text(VERSIONADO.replace("enviar: false", "enviar: true").replace("homologado_em: null", 'homologado_em: "2026-11-22 09:00"'),
                                   encoding="utf-8")
        ranking.gravar_operacao({"alertas": {"enviar": False, "homologado_em": None}})
        self.assertEqual(piloto.modo(ranking.carregar_regras()), "SOMBRA")

    def test_ensaio_do_kill_switch_nao_escreve_no_estado_real(self):
        real = tempfile.TemporaryDirectory()
        self.addCleanup(real.cleanup)
        with mock.patch.dict(os.environ, {"CENTRAL_COMPRAS_DADOS_PRIVADOS": real.name}):
            self.ligar_local()
            antes = ranking.arquivo_operacao().read_text(encoding="utf-8")
            itens = ativacao.ensaio_kill_switch()
            self.assertEqual(ranking.arquivo_operacao().read_text(encoding="utf-8"), antes)   # o estado "real" (deste teste) ficou como estava
        falhas = [i for i in itens if i["status"] != "OK"]
        self.assertEqual(falhas, [], falhas)


class PainelPrioridadeTest(Base):
    def _saida(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cli.cmd_prioridade(argparse.Namespace(horas=24.0, limite=5))
        return buf.getvalue()

    def test_em_sombra_diz_que_e_sombra(self):
        s = self._saida()
        self.assertIn("Modo: SOMBRA", s)
        self.assertIn("comum 0/6", s)                               # politica completa em sombra, como antes

    def test_no_piloto_mostra_modo_e_os_limites_efetivos_do_piloto(self):
        self.ligar_local()
        s = self._saida()
        self.assertIn("Modo: PILOTO", s)
        self.assertIn("python -m radar piloto", s)
        self.assertIn("comum 0/2", s)
        self.assertIn("critico 0/1", s)
        self.assertIn("excecao 0/0", s)
        self.assertIn("max por ciclo 1 | total por varredura 1", s)
        self.assertNotIn("comum 0/6", s)                            # nao exibe mais os limites da politica completa no piloto

    def test_a_politica_nao_foi_alterada_pelo_painel(self):
        self.ligar_local()
        con = db.abrir()
        con.close()
        p = ranking.carregar_regras()
        from radar import prioridade
        self.assertEqual(prioridade.config(p)["orcamento_diario"], 6)   # prioridade.config segue devolvendo a politica completa
        self.assertEqual(piloto.config(p)["orcamento_diario"], 2)


if __name__ == "__main__":
    unittest.main()
