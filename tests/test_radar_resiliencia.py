"""Resiliencia a queda de rede (achados do teste real de 21/11/2026 com proxy inexistente)."""

import datetime as dt
import json
import os
import tempfile
import unittest
import urllib.error
from unittest import mock

from radar import db, varredura
from radar.fontes import base, gatry, meliuz, promobit
from radar.fontes.base import FonteErro, FonteErroRede

AGORA = dt.datetime(2026, 11, 21, 10, 0)


def sem_rede(url):
    sem_rede.chamadas += 1
    raise FonteErroRede(f"{url}: URLError")


class HttpTest(unittest.TestCase):
    def test_erro_de_rede_vira_fonte_erro_rede_e_http_404_nao(self):
        with mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("sem dns")):
            with self.assertRaises(FonteErroRede):
                base.http_get("https://x", tentativas=2, espera=0)
        err = urllib.error.HTTPError("https://x", 404, "Not Found", {}, None)
        with mock.patch("urllib.request.urlopen", side_effect=err):
            with self.assertRaises(FonteErro) as cm:
                base.http_get("https://x", tentativas=2, espera=0)
        self.assertNotIsInstance(cm.exception, FonteErroRede)


class AbortaNoPrimeiroErroDeRedeTest(unittest.TestCase):
    def setUp(self):
        sem_rede.chamadas = 0

    def test_promobit_gatry_e_meliuz_param_apos_o_primeiro_erro_de_rede(self):
        with self.assertRaises(FonteErro):
            promobit.coletar({"paginas_recentes": 2, "lojas": ["amazon", "kabum"]}, sem_rede)
        self.assertEqual(sem_rede.chamadas, 1)
        with self.assertRaises(FonteErro):
            gatry.coletar({"paginas_promocoes": 3}, sem_rede)
        self.assertEqual(sem_rede.chamadas, 2)
        with self.assertRaises(FonteErro):
            meliuz.coletar({"lojas": {"amazon": "a", "kabum": "b", "magalu": "c"}}, sem_rede)
        self.assertEqual(sem_rede.chamadas, 3)


class MeliuzNaoEngoleErroTest(unittest.TestCase):
    HTML = "<div>Atualizado em 20/11/2026, às 02h05 50% › Regras Cupom X CUPONSBF Ver cupom CUPONSBF Aproveite.</div>"

    def test_todas_as_lojas_com_erro_e_falha_nao_lista_vazia(self):
        def quebra(url):
            raise ValueError("html estranho")
        with self.assertRaises(FonteErro):
            meliuz.coletar({"lojas": {"amazon": "a", "kabum": "b"}}, quebra)

    def test_uma_loja_com_erro_nao_derruba_as_outras(self):
        def meio(url):
            if url.endswith("/a"):
                raise ValueError("quebrou")
            return self.HTML
        r = meliuz.coletar({"lojas": {"amazon": "a", "kabum": "b"}}, meio)
        self.assertEqual([o.cupom_codigo for o in r], ["CUPONSBF"])

    def test_pagina_sem_cupons_sem_erro_e_vazia_legitima(self):
        self.assertEqual(meliuz.coletar({"lojas": {"amazon": "a"}}, lambda u: "<div>nada</div>"), [])


class HoraPorPrimeiraVistaTest(unittest.TestCase):
    """HardMOB nao informa hora. Tres horas DIFERENTES: published_at (so se a fonte informa), first_seen_at (quando o radar viu)
    e collected_at (quando leu). A hora em que o radar viu NUNCA vira a hora da postagem."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        p = mock.patch.dict(os.environ, {"CENTRAL_COMPRAS_DADOS_PRIVADOS": self._tmp.name})
        p.start()
        self.addCleanup(p.stop)
        self.addCleanup(self._tmp.cleanup)

    @staticmethod
    def itens(*ids):
        from radar.modelos import Oferta
        return [Oferta(fonte="hardmob", id_externo=str(i), titulo=f"Loja - Produto {i} - R$ 10") for i in ids]

    def test_primeira_vista_nunca_vira_hora_de_publicacao(self):
        a = self.itens(100, 101, 102)
        self.assertEqual(varredura.hora_por_primeira_vista("hardmob", a, AGORA), (0, False))
        self.assertTrue(all(o.primeira_vista_em is None for o in a))  # 1o ciclo so grava a marca
        b = self.itens(100, 101, 102, 103, 104)
        self.assertEqual(varredura.hora_por_primeira_vista("hardmob", b, AGORA), (2, False))
        self.assertTrue(all(o.publicado_em is None for o in b))  # published_at CONTINUA vazio
        self.assertEqual([(o.id_externo, o.primeira_vista_em) for o in b if o.primeira_vista_em], [("103", "2026-11-21 10:00"), ("104", "2026-11-21 10:00")])
        self.assertTrue(b[3].hora_incerta)
        self.assertFalse(b[0].hora_incerta)  # nao e "novo": nada a afirmar
        c = self.itens(100, 104, 105)
        self.assertEqual(varredura.hora_por_primeira_vista("hardmob", c, AGORA + dt.timedelta(minutes=10))[0], 1)  # 104 ja era conhecido

    def test_hora_que_a_fonte_informa_continua_sendo_confiavel(self):
        a = self.itens(1)
        varredura.hora_por_primeira_vista("f", a, AGORA)
        b = self.itens(1, 2)
        b[1].publicado_em = "2026-11-21 08:00"
        varredura.hora_por_primeira_vista("f", b, AGORA)
        self.assertEqual(b[1].publicado_em, "2026-11-21 08:00")
        self.assertFalse(b[1].hora_incerta)  # tem published_at: a hora da fonte vale
        from radar.modelos import Oferta
        self.assertEqual(varredura.hora_por_primeira_vista("g", [Oferta(fonte="g", id_externo="abc", titulo="x")], AGORA), (0, False))

    def test_transbordo_quando_quase_toda_a_lista_e_nova(self):
        varredura.hora_por_primeira_vista("h", self.itens(1, 2, 3, 4, 5, 6), AGORA)
        n, transbordo = varredura.hora_por_primeira_vista("h", self.itens(1, 2, 7, 8, 9, 10), AGORA)  # 4 novos de 6, 2 fixos
        self.assertEqual((n, transbordo), (4, True))  # a lista pode ter perdido itens entre os ciclos

    def test_dry_run_nao_grava_a_marca(self):
        varredura.hora_por_primeira_vista("h2", self.itens(5), AGORA, persistir=False)
        self.assertEqual(varredura.hora_por_primeira_vista("h2", self.itens(5, 6), AGORA, persistir=True), (0, False))  # 1o ciclo "de verdade"


class AlertasDesligadosNaoSaemDaFilaTest(unittest.TestCase):
    """Kill switch: com os alertas desligados, alerta que esperava na fila e descartado e so relatorio e reenviado."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        p = mock.patch.dict(os.environ, {"CENTRAL_COMPRAS_DADOS_PRIVADOS": self._tmp.name})
        p.start()
        self.addCleanup(p.stop)
        self.addCleanup(self._tmp.cleanup)

    def test_varredura_com_alertas_desligados_descarta_fila_de_alerta_e_reenvia_relatorio(self):
        from radar import outbox
        con = db.abrir()
        outbox.enfileirar(con, "ALERTA ANTIGO", "radar-alerta", "fora", tipo="alerta", oferta_id=7)
        outbox.enfileirar(con, "RELATORIO", "rastreador-robos", "fora")
        con.close()
        enviados = []
        with mock.patch("builtins.print"):
            varredura.executar(enviar=True, enviar_fn=lambda t: (enviados.append(t) or (True, "ok")), coletores={"tg": lambda c: []},
                               fontes_cfg={"tg": {"canais": []}}, agora=AGORA)
        self.assertEqual(len(enviados), 1)
        self.assertIn("RELATORIO", enviados[0])
        self.assertFalse([t for t in enviados if "ALERTA ANTIGO" in t])
        con = db.abrir()
        self.assertEqual(con.execute("SELECT desfecho FROM outbox WHERE tipo='alerta'").fetchone()[0], "descartado_alertas_desligados")
        con.close()


class HoraIncertaNaMensagemTest(unittest.TestCase):
    """Hora incerta nunca e anunciada como relampago, mesmo CRITICA (validada manualmente)."""

    def msg(self, incerta):
        from radar import alertas
        return alertas.montar_mensagem(
            nome_produto="KaBuM Smart K800 Pro 127V", loja="KaBuM", preco_anunciado=959.0, cupom=None, preco_final=959.0, estimado=False,
            stats={}, fonte="hardmob", canal="forum", detectado_em="21/11 10:00", status="VALIDADO", url="https://x", classe="CRITICA",
            motivo="abaixo do minimo", avisos=["hora_incerta"] if incerta else [], hora_incerta=incerta)

    def test_relampago_so_com_hora_confiavel(self):
        self.assertIn("OFERTA RELÂMPAGO", self.msg(False))
        incerta = self.msg(True)
        self.assertNotIn("RELÂMPAGO", incerta)
        self.assertIn("OFERTA EM DESTAQUE", incerta)
        self.assertIn("NÃO informa a hora da postagem", incerta)


class LacunaDeColetaTest(unittest.TestCase):
    """Janela sem ler a fonte MAIOR que a cobertura da lista = ofertas perdidas. Medido a cada ciclo."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        p = mock.patch.dict(os.environ, {"CENTRAL_COMPRAS_DADOS_PRIVADOS": self._tmp.name})
        p.start()
        self.addCleanup(p.stop)
        self.addCleanup(self._tmp.cleanup)

    @staticmethod
    def fonte(quando, minutos_atras):
        from radar.modelos import Oferta
        pub = (quando - dt.timedelta(minutes=minutos_atras)).strftime("%Y-%m-%d %H:%M")  # a lista alcanca `minutos_atras` para tras DESTE ciclo
        return lambda cfg: [Oferta(fonte="x", canal="recentes-p1", id_externo="a", titulo="Notebook", publicado_em=pub)]

    def _rodar(self, quando, minutos_cobertos):
        with mock.patch("builtins.print"):
            varredura.executar(enviar=False, coletores={"x": self.fonte(quando, minutos_cobertos)}, fontes_cfg={"x": {"intervalo_min": 10}}, agora=quando)

    def _ultimo(self):
        con = db.abrir()
        try:
            return json.loads(con.execute("SELECT descartes_json FROM coletas_ciclo ORDER BY id DESC LIMIT 1").fetchone()[0])
        finally:
            con.close()

    def test_notebook_suspenso_por_mais_que_a_cobertura_gera_lacuna_medida(self):
        self._rodar(AGORA, 40)
        self._rodar(AGORA + dt.timedelta(minutes=10), 40)
        d = self._ultimo()
        self.assertFalse(d["lacuna"])  # janela de 10 min, lista cobre 40: sem perda
        self._rodar(AGORA + dt.timedelta(hours=7, minutes=10), 40)  # suspenso por 7 h
        d = self._ultimo()
        self.assertTrue(d["lacuna"])
        self.assertEqual(d["lacuna_min"], 420.0)
        self.assertEqual(d["perdido_min"], 380.0)  # 420 sem ler - 40 que a lista ainda alcanca

    def test_lacuna_aparece_no_relatorio_de_efetividade(self):
        from radar import efetividade
        self._rodar(AGORA, 40)
        self._rodar(AGORA + dt.timedelta(hours=3), 40)
        con = db.abrir()
        try:
            rel = efetividade.gerar(con, 6, AGORA + dt.timedelta(hours=3, minutes=1))
        finally:
            con.close()
        self.assertIn("LACUNA DE COLETA", rel["fontes"]["x"]["diagnostico"])

    def test_hora_incerta_apos_lacuna_nao_e_tratada_como_nova(self):
        """Item sem published_at, visto 'agora' DEPOIS de uma lacuna, pode ter sido postado durante a lacuna: sem evidencia de novidade."""
        from radar import catalogo, ranking
        from radar.modelos import Oferta
        con = db.abrir()
        try:
            for i, p in enumerate([1250.0, 1230.0, 1199.98, 1240.0, 1260.0]):
                t = (AGORA - dt.timedelta(days=3) + dt.timedelta(hours=12 * i)).strftime("%Y-%m-%d %H:%M")
                con.execute("INSERT INTO observacoes (origem, produto, coletado_em, preco_entregue, onde, hash) VALUES (?,?,?,?,?,?)", ("t", "k800_pro_127v", t, p, "L", f"h{i}"))
            con.commit()
            regras = ranking.carregar_regras()
            regras["alertas"].update(enviar=True, homologado_em="x")

            def oferta(lacuna):
                return Oferta(fonte="hardmob", id_externo="900", titulo="KaBuM - Robô Aspirador Smart K800 Pro 127V Preto - R$ 1.000", loja="KaBuM",
                              preco_anunciado=1000.0, primeira_vista_em=AGORA.strftime("%Y-%m-%d %H:%M"), extras={"lacuna_antes": True} if lacuna else {})
            r_ok = varredura.processar_oferta(con, oferta(False), catalogo.carregar(), regras, None, AGORA, diferir=True)
            self.assertTrue(r_ok["acao"].startswith("candidato"), r_ok)       # visto agora, sem lacuna: pode ser candidato (com hora incerta)
            r_lac = varredura.processar_oferta(con, Oferta(fonte="hardmob", id_externo="901", titulo="KaBuM - Robô Aspirador Smart K800 Pro 127V Preto - R$ 990",
                                                           loja="Outra", preco_anunciado=990.0, primeira_vista_em=AGORA.strftime("%Y-%m-%d %H:%M"),
                                                           extras={"lacuna_antes": True}), catalogo.carregar(), regras, None, AGORA, diferir=True)
            self.assertEqual(r_lac["descarte"], "hora_incerta_sem_evidencia_de_novidade")
        finally:
            con.close()


class CodigoDeSaidaDaVarreduraTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        p = mock.patch.dict(os.environ, {"CENTRAL_COMPRAS_DADOS_PRIVADOS": self._tmp.name})
        p.start()
        self.addCleanup(p.stop)
        self.addCleanup(self._tmp.cleanup)

    def test_fonte_sem_configuracao_nao_mascara_queda_total(self):
        def ruim(cfg):
            raise FonteErro("sem rede")
        with mock.patch("builtins.print"):
            codigo = varredura.executar(enviar=False, coletores={"ruim": ruim, "tg": lambda c: []},
                                        fontes_cfg={"ruim": {}, "tg": {"canais": []}}, agora=AGORA)
        self.assertEqual(codigo, 1)  # antes: 0, porque a fonte sem configuracao contava como "ok"
        con = db.abrir()
        self.assertEqual({r["fonte"]: r["status"] for r in con.execute("SELECT fonte, status FROM coletas_ciclo")},
                         {"ruim": "erro", "tg": "sem_configuracao"})
        con.close()

    def test_so_fontes_sem_configuracao_nao_e_falha(self):
        with mock.patch("builtins.print"):
            self.assertEqual(varredura.executar(enviar=False, coletores={"tg": lambda c: []},
                                                fontes_cfg={"tg": {"canais": []}}, agora=AGORA), 0)


if __name__ == "__main__":
    unittest.main()
