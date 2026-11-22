"""Homologacao dos alertas (ativacao explicita), TTL da fila, revalidacao na fonte e telemetria de efetividade."""

import datetime as dt
import json
import os
import tempfile
import unittest
from unittest import mock

from radar import alertas, catalogo, db, outbox, ranking, varredura
from radar.fontes import promobit
from radar.fontes.base import FonteErro
from radar.modelos import Oferta

AGORA = dt.datetime(2026, 11, 21, 10, 0)


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        p = mock.patch.dict(os.environ, {"CENTRAL_COMPRAS_DADOS_PRIVADOS": self._tmp.name})
        p.start()
        self.addCleanup(p.stop)
        self.addCleanup(self._tmp.cleanup)
        self.con = db.abrir()
        self.addCleanup(lambda: self.con.close())  # lambda: o teste de migracao troca a conexao
        for i, preco in enumerate([1250.0, 1230.0, 1199.98, 1240.0, 1260.0]):
            t = (AGORA - dt.timedelta(days=3) + dt.timedelta(hours=12 * i)).strftime("%Y-%m-%d %H:%M")
            self.con.execute("INSERT INTO observacoes (origem, produto, coletado_em, preco_entregue, onde, hash) VALUES (?,?,?,?,?,?)",
                             ("t", "k800_pro_127v", t, preco, "KaBuM", f"h{i}"))
        self.con.commit()
        self.cat = catalogo.carregar()
        self.regras = ranking.carregar_regras()

    def oferta(self, **kw):
        base = dict(fonte="promobit", canal="recentes-p1", id_externo="1", titulo="Robô Aspirador KaBuM Smart K800 Pro 127V Preto",
                    url="https://www.promobit.com.br/oferta/k800-1/", loja="KaBuM!", preco_anunciado=1100.0,
                    texto="cupom funcionando", publicado_em="2026-11-21 09:30")
        base.update(kw)
        return Oferta(**base)


class PortaoDeHomologacaoTest(Base):
    def test_configuracao_real_entrega_desligada_e_sem_homologacao(self):
        cfg = ranking.carregar_regras()["alertas"]
        self.assertFalse(cfg["enviar"])
        self.assertIsNone(cfg["homologado_em"])

    def test_com_a_config_real_nada_e_enviado(self):
        enviados = []
        r = varredura.processar_oferta(self.con, self.oferta(), self.cat, self.regras, lambda m: (enviados.append(m) or True, "ok"), AGORA)
        self.assertTrue(r["acao"].startswith("sombra"), r["acao"])
        self.assertEqual(enviados, [])

    def test_enviar_true_sem_homologado_em_continua_em_sombra(self):
        self.regras["alertas"]["enviar"] = True
        r = varredura.processar_oferta(self.con, self.oferta(), self.cat, self.regras, lambda m: (True, "ok"), AGORA)
        self.assertIn("nao homologados", r["acao"])

    def test_nao_confirmado_nunca_sai_como_alerta_urgente(self):
        self.regras["alertas"].update(enviar=True, homologado_em="2026-11-21 09:00")
        for status in ("NAO_CONFIRMADO", "EXPIRADO"):
            acao, _ = alertas.decidir(self.con, produto="k800_pro_127v", loja="L", vendedor=None, cupom=None, preco=1000.0,
                                      status=status, fonte="promobit", classe="ALTA", regras=self.regras, agora=AGORA)
            self.assertNotEqual(acao, "enviar", status)
        acao, _ = alertas.decidir(self.con, produto="k800_pro_127v", loja="L", vendedor=None, cupom=None, preco=1000.0,
                                  status="PROVAVEL", fonte="promobit", classe="ALTA", regras=self.regras, agora=AGORA)
        self.assertEqual(acao, "enviar")

    def test_mensagem_de_alerta_provavel_diz_estimado_e_pede_conferencia(self):
        self.regras["alertas"].update(enviar=True, homologado_em="2026-11-21 09:00")
        enviados = []
        varredura.processar_oferta(self.con, self.oferta(), self.cat, self.regras, lambda m: (enviados.append(m) or True, "ok"), AGORA)
        self.assertIn("Status: PROVAVEL", enviados[0])
        self.assertIn("(estimado)", enviados[0])
        self.assertIn("Confirme preço, voltagem e vendedor", enviados[0])


class FilaComValidadeTest(Base):
    def test_relatorio_vencido_e_descartado_com_desfecho(self):
        outbox.enfileirar(self.con, "relatorio", "r", "erro", tipo="relatorio", agora_dt=AGORA - dt.timedelta(hours=25))
        enviados = []
        self.assertEqual(outbox.drenar(self.con, lambda t: (enviados.append(t) or True, "ok"), agora_dt=AGORA), [])
        self.assertEqual(enviados, [])
        self.assertEqual(self.con.execute("SELECT desfecho FROM outbox").fetchone()[0], "expirado_ttl")

    def test_alerta_dentro_do_ttl_sai_sem_revalidar(self):
        outbox.enfileirar(self.con, "ALERTA", "a", "erro", tipo="alerta", oferta_id=1, ttl_min=30, agora_dt=AGORA - dt.timedelta(minutes=10))
        enviados = []
        r = outbox.drenar(self.con, lambda t: (enviados.append(t) or True, "ok"), agora_dt=AGORA,
                          revalidar=lambda oid: (_ for _ in ()).throw(AssertionError("nao deveria revalidar")))
        self.assertTrue(r[0][1])
        self.assertEqual(enviados, ["ALERTA"])

    def test_alerta_vencido_e_encerrado_na_fonte_e_descartado(self):
        outbox.enfileirar(self.con, "ALERTA", "a", "erro", tipo="alerta", oferta_id=1, ttl_min=30, agora_dt=AGORA - dt.timedelta(hours=3))
        enviados = []
        r = outbox.drenar(self.con, lambda t: (enviados.append(t) or True, "ok"), agora_dt=AGORA,
                          revalidar=lambda oid: (False, "oferta encerrada na fonte (status FINISHED)"))
        self.assertEqual(enviados, [])
        self.assertIn("descartado", r[0][2])
        self.assertEqual(self.con.execute("SELECT desfecho FROM outbox").fetchone()[0], "descartado_revalidacao")

    def test_alerta_vencido_ainda_ativo_sai_rotulado_como_revalidado(self):
        outbox.enfileirar(self.con, "ALERTA", "a", "erro", tipo="alerta", oferta_id=1, ttl_min=30, agora_dt=AGORA - dt.timedelta(hours=3))
        enviados = []
        outbox.drenar(self.con, lambda t: (enviados.append(t) or True, "ok"), agora_dt=AGORA, revalidar=lambda oid: (True, "ativa"))
        self.assertIn("revalidado na fonte", enviados[0])
        self.assertIn("Confira antes de pagar", enviados[0])

    def test_alerta_vencido_sem_como_revalidar_ou_com_erro_e_descartado(self):
        outbox.enfileirar(self.con, "A1", "a", "e", tipo="alerta", oferta_id=1, agora_dt=AGORA - dt.timedelta(hours=3))
        outbox.enfileirar(self.con, "A2", "a", "e", tipo="alerta", oferta_id=2, agora_dt=AGORA - dt.timedelta(hours=3))
        enviados = []
        outbox.drenar(self.con, lambda t: (enviados.append(t) or True, "ok"), agora_dt=AGORA, revalidar=None)
        outbox.drenar(self.con, lambda t: (enviados.append(t) or True, "ok"), agora_dt=AGORA, revalidar=lambda oid: 1 / 0)
        self.assertEqual(enviados, [])
        self.assertEqual({r[0] for r in self.con.execute("SELECT desfecho FROM outbox")}, {"descartado_revalidacao"})

    def test_falha_de_envio_do_alerta_na_varredura_enfileira_com_ttl(self):
        self.regras["alertas"].update(enviar=True, homologado_em="2026-11-21 09:00")
        varredura.processar_oferta(self.con, self.oferta(), self.cat, self.regras, lambda m: (False, "zap fora"), AGORA)
        row = self.con.execute("SELECT tipo, oferta_id, expira_em FROM outbox").fetchone()
        self.assertEqual((row["tipo"], row["expira_em"]), ("alerta", "2026-11-21 10:30:00"))
        self.assertIsNotNone(row["oferta_id"])

    def test_varredura_drena_fila_revalidando_antes_de_entregar(self):
        self.regras["alertas"].update(enviar=True, homologado_em="2026-11-21 09:00")
        varredura.processar_oferta(self.con, self.oferta(), self.cat, self.regras, lambda m: (False, "zap fora"), AGORA)
        enviados = []
        depois = AGORA + dt.timedelta(hours=2)  # alem do TTL de 30 min
        with mock.patch("builtins.print"), mock.patch("radar.varredura.ranking.carregar_regras", return_value=self.regras), \
                mock.patch("radar.varredura.revalidar_oferta", return_value=(False, "oferta encerrada na fonte (status FINISHED)")):
            varredura.executar(enviar=True, coletores={}, fontes_cfg={}, agora=depois, enviar_fn=lambda m: (enviados.append(m) or True, "ok"))
        self.assertEqual(enviados, [])  # promocao encerrada nao e apresentada como ativa
        self.assertEqual(self.con.execute("SELECT desfecho FROM outbox").fetchone()[0], "descartado_revalidacao")


class RevalidarPromobitTest(unittest.TestCase):
    @staticmethod
    def pagina(status, preco):
        dados = {"props": {"pageProps": {"serverOffer": {"offerStatusName": status, "offerPrice": preco}}}}
        return f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(dados)}</script>'

    def test_ativa_encerrada_e_preco_subiu(self):
        self.assertTrue(promobit.revalidar("u", 1100.0, lambda u: self.pagina("RECENTS", 1100.0))[0])
        self.assertTrue(promobit.revalidar("u", 1100.0, lambda u: self.pagina("TOP_OFFER", 1105.0))[0])  # dentro de 2%
        ok, motivo = promobit.revalidar("u", 1100.0, lambda u: self.pagina("FINISHED", 1100.0))
        self.assertFalse(ok)
        self.assertIn("encerrada", motivo)
        ok, motivo = promobit.revalidar("u", 1100.0, lambda u: self.pagina("RECENTS", 1300.0))
        self.assertFalse(ok)
        self.assertIn("subiu", motivo)

    def test_pagina_fora_do_ar_ou_sem_dados_nao_revalida(self):
        def cai(u):
            raise FonteErro("HTTP 503")

        self.assertFalse(promobit.revalidar("u", 1.0, cai)[0])
        self.assertFalse(promobit.revalidar("u", 1.0, lambda u: self.pagina("RECENTS", 1.0).replace("serverOffer", "x"))[0])


class TelemetriaTest(Base):
    def test_ciclo_registra_vazia_erro_e_descartes_por_motivo(self):
        def boa(cfg):
            return [self.oferta(id_externo="a", titulo="Notebook Gamer"),                       # fora do catalogo
                    self.oferta(id_externo="b", publicado_em="2026-11-20 08:00"),               # produto certo, oferta antiga
                    self.oferta(id_externo="c", texto="cupom CASATECH10 10% de desconto")]      # casa, com cupom

        def vazia(cfg):
            return []

        def ruim(cfg):
            raise FonteErro("HTTP 503")

        with mock.patch("builtins.print"):
            varredura.executar(enviar=False, coletores={"boa": boa, "vazia": vazia, "ruim": ruim},
                               fontes_cfg={"boa": {}, "vazia": {}, "ruim": {}}, agora=AGORA)
        linhas = {r["fonte"]: r for r in self.con.execute("SELECT * FROM coletas_ciclo")}
        self.assertEqual((linhas["boa"]["status"], linhas["boa"]["itens"], linhas["boa"]["casadas"]), ("ok", 3, 2))
        self.assertEqual(linhas["vazia"]["status"], "vazia")      # ausencia de ofertas...
        self.assertEqual(linhas["ruim"]["status"], "erro")        # ...nao se confunde com falha do coletor
        self.assertGreaterEqual(linhas["boa"]["cupons_extraidos"], 1)
        self.assertGreaterEqual(json.loads(linhas["boa"]["descartes_json"])["elegiveis"], 1)  # CASATECH10 sem restricao impeditiva
        descartes = json.loads(linhas["boa"]["descartes_json"])
        self.assertEqual(descartes["fora_do_catalogo"], 1)
        self.assertEqual(descartes["oferta_antiga"], 1)

    def test_migracao_2_e_reversivel(self):
        self.con.close()
        con = db.abrir(migrar_automatico=False)
        self.assertEqual(db.versao_aplicada(con), db.VERSAO_ATUAL)
        db.backup(motivo="teste")
        self.assertEqual(db.reverter(con, 1), list(range(db.VERSAO_ATUAL, 1, -1)))
        cols = {r["name"] for r in con.execute("PRAGMA table_info(outbox)")}
        self.assertNotIn("expira_em", cols)
        db.migrar(con)
        self.assertIn("expira_em", {r["name"] for r in con.execute("PRAGMA table_info(outbox)")})
        con.close()
        self.con = db.abrir()


class QuaseCasouEEfetividadeTest(Base):
    def test_motivo_de_recusa_distingue_quase_casou_de_nada_a_ver(self):
        m = lambda t: catalogo.motivo_recusa(t, self.cat)
        self.assertEqual(m("Ar Condicionado Split Elgin Eco Inverter III Wi-Fi 9000 BTUs Frio 220V"), "quase_casou:outra_capacidade_btu")
        self.assertEqual(m("Robô Aspirador KaBuM K800 Pro 220V"), "quase_casou:outra_tensao")
        self.assertEqual(m("Tapo RV20 Mop"), "quase_casou:variante_excluida")
        self.assertEqual(m("Filtro HEPA para Dreame F10"), "quase_casou:acessorio")
        self.assertIsNone(m("Notebook Gamer XYZ"))

    def test_relatorio_separa_falha_de_ausencia_e_de_nao_configurado(self):
        from radar import efetividade

        def boa(cfg):
            return [self.oferta(id_externo="a", titulo="Elgin Eco Inverter III 9000 BTUs 220V"), self.oferta(id_externo="b", titulo="Notebook")]

        def ruim(cfg):
            raise FonteErro("HTTP 503")

        with mock.patch("builtins.print"):
            varredura.executar(enviar=False, coletores={"boa": boa, "vazia": lambda c: [], "ruim": ruim, "tg": lambda c: []},
                               fontes_cfg={"boa": {}, "vazia": {}, "ruim": {}, "tg": {"canais": []}}, agora=AGORA)
        rel = efetividade.gerar(self.con, 2, AGORA + dt.timedelta(minutes=1))
        diag = {k: v["diagnostico"] for k, v in rel["fontes"].items()}
        self.assertIn("nenhuma publicacao era dos seus 12 produtos", diag["boa"])
        self.assertIn("sem publicacoes", diag["vazia"])
        self.assertIn("FALHA DO COLETOR", diag["ruim"])
        self.assertIn("NAO CONFIGURADA", diag["tg"])
        self.assertEqual(rel["descartes"]["quase_casou:outra_capacidade_btu"], 1)
        self.assertEqual(rel["descartes"]["fora_do_catalogo"], 1)
        self.assertIn("FALHA DO COLETOR", efetividade.formatar(rel))


class CriticaNaoEBarradaPeloLimiteTest(Base):
    def test_limite_diario_barra_alta_mas_nao_critica(self):
        self.regras["alertas"].update(enviar=True, homologado_em="2026-11-21 09:00", limite_diario=1)
        kw = dict(produto="k800_pro_127v", loja="L", vendedor=None, cupom=None, status="PROVAVEL", fonte="promobit", regras=self.regras, agora=AGORA)
        alertas.registrar(self.con, oferta_id=None, produto="k800_pro_127v", loja="X", vendedor=None, cupom=None, preco=900.0, url=None,
                          classe="ALTA", status="PROVAVEL", modo="real", detalhe="ja enviado hoje", agora=AGORA)
        self.assertEqual(alertas.decidir(self.con, preco=1000.0, classe="ALTA", **kw)[0], "sombra")
        crit = alertas.decidir(self.con, preco=1000.0, classe="CRITICA", **{**kw, "status": "VALIDADO"})
        self.assertEqual(crit[0], "enviar")


class CoberturaNaTelemetriaTest(Base):
    def test_lista_que_cobre_menos_que_o_intervalo_e_sinalizada_no_relatorio(self):
        from radar import efetividade

        def curta(cfg):  # a oferta mais antiga tem 9 min e o ciclo e de 10: pode haver buraco
            return [self.oferta(id_externo="a", publicado_em=(AGORA - dt.timedelta(minutes=9)).strftime("%Y-%m-%d %H:%M"), titulo="Notebook", canal="recentes-p1")]

        def longa(cfg):
            return [self.oferta(id_externo="b", publicado_em=(AGORA - dt.timedelta(minutes=40)).strftime("%Y-%m-%d %H:%M"), titulo="Notebook", canal="recentes-p1")]

        with mock.patch("builtins.print"):
            varredura.executar(enviar=False, coletores={"curta": curta, "longa": longa}, fontes_cfg={"curta": {"intervalo_min": 10}, "longa": {"intervalo_min": 10}}, agora=AGORA)
        rel = efetividade.gerar(self.con, 2, AGORA + dt.timedelta(minutes=1))
        self.assertIn("pode ter perdido ofertas", rel["fontes"]["curta"]["diagnostico"])
        self.assertNotIn("perdido", rel["fontes"]["longa"]["diagnostico"])


class ElegibilidadeDeCupomDeLojaTest(Base):
    def test_cupom_de_loja_conta_como_elegivel_so_sem_restricao_impeditiva_e_nao_expirado(self):
        def of(i, texto, codigo):
            return Oferta(fonte="meliuz", canal="cupom_loja:amazon", id_externo=i, titulo=f"amazon: {texto}", texto=texto,
                          cupom_codigo=codigo, loja="amazon", extras={"tipo": "cupom_loja"})
        casos = {"livre": of("1", "10% de desconto com o cupom LIVRE10", "LIVRE10"),
                 "primeira": of("2", "20% off so na primeira compra cupom NOVO20BF", "NOVO20BF"),
                 "app": of("3", "R$ 30 de desconto somente no app cupom APP30BF", "APP30BF")}
        res = {k: varredura.processar_oferta(self.con, v, self.cat, self.regras, None, AGORA)["cupons_elegiveis"] for k, v in casos.items()}
        self.assertEqual(res, {"livre": 1, "primeira": 0, "app": 0})  # perfil padrao: nao e primeira compra, nao usa app


class InvalidacaoNaoContaminaTest(Base):
    def test_observacao_invalidada_nao_entra_em_minimo_nem_em_alerta(self):
        from radar import historico

        self.con.execute("INSERT INTO observacoes (origem, produto, coletado_em, preco_entregue, onde, hash) VALUES (?,?,?,?,?,?)",
                         ("t", "k800_pro_127v", (AGORA - dt.timedelta(hours=2)).strftime("%Y-%m-%d %H:%M"), 60.65, "Leroy", "lixo"))
        self.con.commit()
        self.assertEqual(historico.estatisticas(self.con, "k800_pro_127v", AGORA)["historico_total"]["menor"], 60.65)
        n = historico.sincronizar_correcoes(self.con, [{"origem": "t", "produto": "k800_pro_127v", "coletado_em": (AGORA - dt.timedelta(hours=2)).strftime("%Y-%m-%d %H:%M"),
                                                        "melhor_preco": None, "motivo": "leitura invalida"}])
        self.assertEqual(n, 1)
        st = historico.estatisticas(self.con, "k800_pro_127v", AGORA)
        self.assertEqual(st["historico_total"]["menor"], 1199.98)
        # valor bruto preservado para auditoria
        self.assertEqual(self.con.execute("SELECT preco_entregue, invalida FROM observacoes WHERE hash='lixo'").fetchone()[:], (60.65, 1))
        # e o ranking nao trata 1100 como "abaixo do minimo de 60" nem usa o lixo como base
        classe, _, _ = ranking.classificar(1100.0, "PROVAVEL", st, self.regras)
        self.assertEqual(classe, "ALTA")


if __name__ == "__main__":
    unittest.main()
