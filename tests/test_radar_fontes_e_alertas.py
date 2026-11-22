"""Adaptadores de fontes (HTML/JSON de fixture), ranking, deduplicacao de alertas e varredura ponta a ponta (sem rede)."""

import datetime as dt
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from radar import alertas, catalogo, db, historico, ranking, varredura
from radar.fontes import hardmob, meliuz, promobit, telegram_publico
from radar.fontes.base import FonteErro
from radar.modelos import Oferta

AGORA = dt.datetime(2026, 11, 21, 10, 0)  # depois do periodo de sombra configurado


def _next_data(page_props):
    return f'<html><script id="__NEXT_DATA__" type="application/json">{json.dumps({"props": {"pageProps": page_props}})}</script></html>'


class FontesTest(unittest.TestCase):
    def test_promobit_ofertas_e_cupons_nos_dois_formatos(self):
        oferta = {
            "offerId": 3206770, "offerTitle": "Robô Aspirador KaBuM K800 Pro 127V", "offerPrice": 999.9,
            "offerSlug": "robo-k800-3206770", "offerCoupon": "CASATECH10", "storeName": "KaBuM!",
            "offerPublished": "2026-11-20T15:30:59-0300", "offerLikes": 10,
        }
        cupom = {"couponId": 72427, "couponDiscountValue": "10% de Desconto", "couponDiscountOn": "produtos X",
                 "couponInstructions": "VÁLIDO PARA ITENS SELECIONADOS", "storeName": "Loja X",
                 "couponVerified": "2026-11-20T15:30:59-0300", "couponPublished": "2026-11-20T15:00:00-0300"}
        for formato in ([cupom], {"coupons": [cupom], "total": 1}, {"x": "texto solto"}):
            of = promobit.parse_pagina(_next_data({"serverOffers": {"offers": [oferta]}, "serverCoupons": formato}), "recentes")
            self.assertEqual(of[0].id_externo, "3206770")
            self.assertEqual((of[0].preco_anunciado, of[0].cupom_codigo, of[0].publicado_em), (999.9, "CASATECH10", "2026-11-20 15:30"))
            self.assertEqual(of[0].url, "https://www.promobit.com.br/oferta/robo-k800-3206770/")
        self.assertEqual(len(promobit.parse_pagina(_next_data({"serverOffers": {"offers": [oferta]}, "serverCoupons": [cupom]}), "x")), 2)

    def test_promobit_layout_mudou_e_erro_explicito(self):
        with self.assertRaises(FonteErro):
            promobit.parse_pagina("<html>sem dados</html>", "x")

    def test_promobit_uma_pagina_fora_do_ar_nao_derruba_as_outras(self):
        boa = _next_data({"serverOffers": {"offers": [{"offerId": 1, "offerTitle": "Oferta"}]}})

        def baixar(url):
            if "loja" in url:
                raise FonteErro("HTTP 404")
            return boa

        r = promobit.coletar({"paginas_recentes": 1, "lojas": ["kabum"]}, baixar)
        self.assertEqual(len(r), 1)

    def test_hardmob_titulo_vira_loja_e_preco(self):
        html = ('<a href="x" id="thread_title_842839">Amazon - Garrafa infantil CamelBak Eddy - R$ 63,12</a>'
                '<a href="y" id="thread_title_842832">ML - Robô Aspirador Dreame F10 - R$ 1.102</a>')
        r = hardmob.parse_pagina(html)
        self.assertEqual((r[0].loja, r[0].preco_anunciado, r[0].id_externo), ("Amazon", 63.12, "842839"))
        self.assertEqual(r[1].preco_anunciado, 1102.0)

    def test_telegram_confere_identidade_do_canal(self):
        html = ('<title>OFERTAS PC GAMER – Telegram</title>'
                '<div class="tgme_widget_message_wrap"><div data-post="ofertasdecomputador/29797">'
                '<div class="tgme_widget_message_text js-message_text">SSD 1TB por R$ 299,00 <a href="https://amzn.to/x">link</a></div>'
                '<time datetime="2026-11-20T21:00:00+00:00"></time></div></div>')
        with self.assertRaises(FonteErro):  # handle "promobit" servindo canal de terceiros
            telegram_publico.parse_pagina(html, "promobit", "Promobit")
        with self.assertRaises(FonteErro):  # titulo confere, mas as mensagens sao de outro usuario
            telegram_publico.parse_pagina(html, "outrocanal", "OFERTAS PC GAMER")
        r = telegram_publico.parse_pagina(html, "ofertasdecomputador", "OFERTAS PC GAMER")
        self.assertEqual((r[0].id_externo, r[0].preco_anunciado, r[0].url), ("29797", 299.0, "https://amzn.to/x"))

    def test_meliuz_extrai_codigo_regras_e_ignora_placeholder(self):
        html = ("<div>Atualizado em 20/11/2026, às&nbsp;02h05 "
                "50% › Regras Cupom Amazon de até 50% de desconto na Black dos Sonhos CUPONSBF Ver cupom CUPONSBF "
                "Começaram as ofertas antecipadas! Aproveite cupons. "
                "R$ 1000 › Regras Ganhe até R$1.000 OFF em eletrônicos no cupom Amazon DEVOLTA1000 Ver cupom DEVOLTA1000 "
                "Válido para compra de Iphone 18, vendidos e entregues via Amazon. "
                "R$ 20 › Regras Ative a oferta ACESSEEGANHE Ver cupom ACESSEEGANHE Sem codigo.</div>")
        r = meliuz.parse_pagina(html, "amazon")
        self.assertEqual([o.cupom_codigo for o in r], ["CUPONSBF", "DEVOLTA1000"])
        self.assertEqual(r[0].publicado_em, "2026-11-20 02:05")


class RankingTest(unittest.TestCase):
    REGRAS = ranking.carregar_regras()
    STATS = {"observacoes_validas": 20, "cobertura_dias": 3,
             "historico_total": {"menor": 1000.0, "maior": 1300.0, "mediana": 1150.0},
             "ultimos_30_dias": {"menor": 1000.0, "maior": 1300.0, "mediana": 1150.0}}

    def cl(self, preco, validacao, stats=None, avisos=None):
        return ranking.classificar(preco, validacao, self.STATS if stats is None else stats, self.REGRAS, avisos)[0]

    def test_critica_exige_validado_e_novo_minimo(self):
        self.assertEqual(self.cl(990.0, "VALIDADO"), "CRITICA")
        self.assertEqual(self.cl(990.0, "PROVAVEL"), "ALTA")  # comunitaria nunca e CRITICA
        self.assertEqual(self.cl(990.0, "NAO_CONFIRMADO"), "BAIXA")

    def test_alta_perto_do_minimo_ou_queda_grande(self):
        self.assertEqual(self.cl(1020.0, "PROVAVEL"), "ALTA")  # 2% acima do minimo
        # minimo antigo bem mais baixo: so a queda de 17% vs mediana justifica ALTA
        stats = dict(self.STATS, historico_total={"menor": 800.0, "maior": 1300.0, "mediana": 1150.0})
        self.assertEqual(self.cl(950.0, "PROVAVEL", stats=stats), "ALTA")
        self.assertEqual(self.cl(1050.0, "PROVAVEL", stats=stats), "MEDIA")  # 8,7% abaixo da mediana

    def test_media_e_baixa(self):
        self.assertEqual(self.cl(1090.0, "PROVAVEL"), "MEDIA")  # 5% abaixo da mediana
        self.assertEqual(self.cl(1200.0, "PROVAVEL"), "BAIXA")

    def test_sem_historico_nao_afirma_minimo(self):
        c, _, motivo = ranking.classificar(500.0, "PROVAVEL", {"observacoes_validas": 1, "cobertura_dias": 0}, self.REGRAS)
        self.assertEqual(c, "MEDIA")
        self.assertIn("insuficiente", motivo)
        self.assertEqual(ranking.classificar(500.0, "NAO_CONFIRMADO", None, self.REGRAS)[0], "BAIXA")

    def test_oferta_igual_ou_pior_que_o_melhor_preco_atual_nao_e_novidade(self):
        """Achado real (21/11/2026): 8 de 24 ofertas reais, todas no preco que o relatorio ja mostra, seriam ALTA."""
        # preco no minimo do historico (1000) E igual ao melhor preco atual (1000): sem novidade
        c, _, motivo = ranking.classificar(1000.0, "PROVAVEL", self.STATS, self.REGRAS, preco_ref=1000.0)
        self.assertEqual(c, "MEDIA")
        self.assertIn("sem novidade", motivo)
        # 2% melhor que o atual: ainda pouco (exige 3%)
        self.assertEqual(ranking.classificar(980.0, "PROVAVEL", self.STATS, self.REGRAS, preco_ref=1000.0)[0], "MEDIA")
        # 5% melhor que o atual e no minimo historico: ALTA, e o motivo diz quanto
        c, _, motivo = ranking.classificar(950.0, "PROVAVEL", self.STATS, self.REGRAS, preco_ref=1000.0)
        self.assertEqual(c, "ALTA")
        self.assertIn("5% abaixo do melhor preco atual", motivo)
        # mais caro que o atual
        c, _, motivo = ranking.classificar(1020.0, "PROVAVEL", self.STATS, self.REGRAS, preco_ref=1000.0)
        self.assertNotEqual(c, "ALTA")
        self.assertIn("mais caro", motivo)
        # sem referencia (produto sem coleta recente): comportamento anterior
        self.assertEqual(ranking.classificar(1000.0, "PROVAVEL", self.STATS, self.REGRAS, preco_ref=None)[0], "ALTA")

    def test_validado_tambem_exige_novidade_para_ser_critica(self):
        self.assertNotEqual(ranking.classificar(1000.0, "VALIDADO", self.STATS, self.REGRAS, preco_ref=1000.0)[0], "CRITICA")
        self.assertEqual(ranking.classificar(950.0, "VALIDADO", self.STATS, self.REGRAS, preco_ref=1000.0)[0], "CRITICA")

    def test_preco_de_referencia_ignora_coleta_velha_degradada_e_invalida(self):
        import tempfile, os
        from unittest import mock
        from radar import historico
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"CENTRAL_COMPRAS_DADOS_PRIVADOS": tmp}):
            con = db.abrir()
            try:
                def obs(t, p, degr=0, inval=0, h="x"):
                    con.execute("INSERT INTO observacoes (origem, produto, coletado_em, preco_entregue, onde, hash, degradada, invalida) VALUES (?,?,?,?,?,?,?,?)",
                                ("t", "p", t, p, "L", h + t, degr, inval))
                obs("2026-11-21 09:00", 100.0)
                obs("2026-11-21 09:30", 50.0, degr=1, h="d")      # rodada degradada: ignorada
                obs("2026-11-21 09:45", 1.0, inval=1, h="i")      # leitura invalida: ignorada
                con.commit()
                agora = dt.datetime(2026, 11, 21, 10, 0)
                self.assertEqual(historico.preco_referencia(con, "p", agora), 100.0)
                self.assertIsNone(historico.preco_referencia(con, "p", agora + dt.timedelta(hours=40)))  # coleta velha demais
                self.assertIsNone(historico.preco_referencia(con, "outro", agora))
            finally:
                con.close()

    def test_expirado_e_aviso_de_tensao_rebaixam(self):
        self.assertEqual(self.cl(900.0, "EXPIRADO"), "BAIXA")
        self.assertNotIn(self.cl(900.0, "VALIDADO", avisos=["tensao_ambigua"]), ("CRITICA", "ALTA"))


class AlertasETudoJuntoTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        p = mock.patch.dict(os.environ, {"CENTRAL_COMPRAS_DADOS_PRIVADOS": self._tmp.name})
        p.start()
        self.addCleanup(p.stop)
        self.addCleanup(self._tmp.cleanup)
        self.con = db.abrir()
        self.addCleanup(self.con.close)
        # historico valido do K800: 3 dias, minimo R$ 1.199,98
        for i, preco in enumerate([1250.0, 1230.0, 1199.98, 1240.0, 1260.0]):
            t = (AGORA - dt.timedelta(days=3) + dt.timedelta(hours=12 * i)).strftime("%Y-%m-%d %H:%M")
            self.con.execute(
                "INSERT INTO observacoes (origem, produto, coletado_em, preco_entregue, onde, hash) VALUES (?,?,?,?,?,?)",
                ("rastreador-robos", "k800_pro_127v", t, preco, "KaBuM", f"h{i}"))
        self.con.commit()
        self.cat = catalogo.carregar()
        self.regras = ranking.carregar_regras()
        self.regras["alertas"].update(enviar=True, homologado_em="2026-11-21 09:00")  # ativacao explicita (a config real vem desligada)
        self.enviados = []

    def _oferta(self, **kw):
        base = dict(fonte="promobit", canal="recentes-p1", id_externo="1", titulo="Robô Aspirador KaBuM Smart K800 Pro 127V Preto",
                    url="https://www.promobit.com.br/oferta/k800-1/", loja="KaBuM!", preco_anunciado=1100.0,
                    texto="cupom funcionando", publicado_em="2026-11-21 09:30")
        base.update(kw)
        return Oferta(**base)

    def _enviar(self, msg):
        self.enviados.append(msg)
        return True, "ok"

    def test_oferta_forte_vira_alerta_e_repetida_e_suprimida(self):
        r = varredura.processar_oferta(self.con, self._oferta(), self.cat, self.regras, self._enviar, AGORA)
        self.assertEqual((r["produto"], r["classe"]), ("k800_pro_127v", "ALTA"))
        self.assertTrue(r["acao"].startswith("real"), r["acao"])
        self.assertIn("RADAR CENTRAL-COMPRAS", self.enviados[0])
        self.assertNotIn("—", self.enviados[0])  # sem travessao em texto para humanos
        # mesma oferta de novo (outro id, mesmo preco/loja): suprimida
        r2 = varredura.processar_oferta(self.con, self._oferta(id_externo="2"), self.cat, self.regras, self._enviar, AGORA)
        self.assertTrue(r2["acao"].startswith("suprimir"), r2["acao"])
        self.assertEqual(len(self.enviados), 1)
        # preco 6% menor: novo alerta permitido
        r3 = varredura.processar_oferta(self.con, self._oferta(id_externo="3", preco_anunciado=1030.0), self.cat, self.regras, self._enviar, AGORA)
        self.assertTrue(r3["acao"].startswith("real"), r3["acao"])
        self.assertEqual(len(self.enviados), 2)

    def test_periodo_de_sombra_registra_mas_nao_envia(self):
        antes = AGORA.replace(hour=2)
        r = varredura.processar_oferta(self.con, self._oferta(publicado_em="2026-11-21 01:50"), self.cat, self.regras, self._enviar, antes)
        self.assertTrue(r["acao"].startswith("sombra"), r["acao"])
        self.assertEqual(self.enviados, [])
        self.assertEqual(self.con.execute("SELECT modo FROM alertas").fetchone()[0], "sombra")

    def test_oferta_antiga_nao_vira_relampago(self):
        r = varredura.processar_oferta(self.con, self._oferta(publicado_em="2026-11-20 08:00"), self.cat, self.regras, self._enviar, AGORA)
        self.assertEqual(r["acao"], "sem_alerta")
        self.assertEqual(self.enviados, [])

    def test_tensao_errada_e_produto_fora_do_catalogo_nao_geram_nada(self):
        for tit in ("Robô KaBuM K800 Pro 220V", "Notebook Gamer XYZ"):
            r = varredura.processar_oferta(self.con, self._oferta(titulo=tit), self.cat, self.regras, self._enviar, AGORA)
            self.assertIsNone(r["produto"])
        self.assertEqual(self.enviados, [])

    def test_falha_no_envio_registra_falha_e_tenta_de_novo_depois(self):
        r = varredura.processar_oferta(self.con, self._oferta(), self.cat, self.regras, lambda m: (False, "zap fora"), AGORA)
        self.assertTrue(r["acao"].startswith("falha"))
        # 'falha' nao conta como alerta enviado: a mesma oferta pode ser reavaliada e enviada no ciclo seguinte
        acao, _ = alertas.decidir(self.con, produto="k800_pro_127v", loja="KaBuM!", vendedor=None, cupom=None, preco=1100.0,
                                  status="PROVAVEL", fonte="promobit", classe="ALTA", regras=self.regras, agora=AGORA)
        self.assertEqual(acao, "enviar")

    def test_limite_diario_e_fora_do_horario(self):
        self.regras["alertas"]["limite_diario"] = 1
        varredura.processar_oferta(self.con, self._oferta(), self.cat, self.regras, self._enviar, AGORA)
        r = varredura.processar_oferta(self.con, self._oferta(id_externo="9", loja="Amazon", preco_anunciado=1100.0), self.cat, self.regras, self._enviar, AGORA)
        self.assertTrue(r["acao"].startswith("sombra"), r["acao"])
        self.assertIn("limite diario", r["acao"])
        noite = AGORA.replace(hour=23, minute=30)
        acao, motivo = alertas.decidir(self.con, produto="x", loja="L", vendedor=None, cupom=None, preco=1.0, status="PROVAVEL",
                                       fonte="promobit", classe="ALTA", regras=self.regras, agora=noite)
        self.assertEqual(acao, "sombra")

    def test_cupom_de_loja_so_e_registrado(self):
        of = Oferta(fonte="meliuz", canal="cupom_loja:amazon", id_externo="amazon:CUPONSBF", titulo="amazon: Cupom 50% (50%)",
                    texto="Cupom Amazon de até 50% de desconto", cupom_codigo="CUPONSBF", loja="amazon", extras={"tipo": "cupom_loja"})
        r = varredura.processar_oferta(self.con, of, self.cat, self.regras, self._enviar, AGORA)
        self.assertEqual(r["acao"], "registrado")
        self.assertEqual(self.enviados, [])
        self.assertEqual(self.con.execute("SELECT produto, cupom_codigo FROM ofertas").fetchone()[1], "CUPONSBF")

    def test_executar_isola_fonte_com_falha(self):
        def boa(cfg):
            return [self._oferta(id_externo="77", titulo="Notebook")]

        def ruim(cfg):
            raise FonteErro("HTTP 503")

        with mock.patch("builtins.print"):
            codigo = varredura.executar(enviar=False, coletores={"a": boa, "b": ruim}, fontes_cfg={"a": {}, "b": {}}, agora=AGORA)
        self.assertEqual(codigo, 0)  # uma fonte ok basta
        saude = {r["fonte"]: r["falhas_consecutivas"] for r in self.con.execute("SELECT * FROM fontes_saude")}
        self.assertEqual(saude, {"a": 0, "b": 1})
        with mock.patch("builtins.print"):  # todas falham -> codigo 1
            self.con.execute("UPDATE fontes_saude SET ultima_tentativa=NULL")
            self.con.commit()
            self.assertEqual(varredura.executar(enviar=False, coletores={"b": ruim}, fontes_cfg={"b": {}}, agora=AGORA), 1)

    def test_chave_de_url_ignora_parametros_de_rastreio(self):
        self.assertEqual(alertas.normalizar_url("https://www.kabum.com.br/produto/1?utm=x#a"), "kabum.com.br/produto/1")


if __name__ == "__main__":
    unittest.main()
