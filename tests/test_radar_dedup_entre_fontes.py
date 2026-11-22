"""Deduplicacao da MESMA oferta publicada em fontes diferentes (Pelando site, Pelando Telegram `pelandobr`, Promobit) e a interacao
entre os limites de 3% (porta de 24 h, `alertas.melhora_minima_pct`) e de 5%/7% (anti-repeticao por produto, `prioridade`/`piloto`).

A queda de 3% com R$ 100 e a reavaliacao do candidato suprimido (22/11/2026) estao em test_radar_repeticao_melhora_relevante.py; aqui
ficam a deduplicacao e os efeitos dessas regras sobre a faixa de 4% a 7% numa base de R$ 1.700 (R$ 68 e R$ 85 seguem suprimidos, R$ 102 passa).
Banco temporario; a ativacao local (operacao.yaml) e ignorada (operacao=False)."""

import copy
import datetime as dt
import os
import tempfile
import unittest
from unittest import mock

from radar import alertas, catalogo, db, prioridade, ranking, varredura
from radar.modelos import Oferta

AGORA = dt.datetime(2026, 11, 22, 10, 0)
# SKU no titulo: sem ele o catalogo avisa `sku_nao_confirmado` (bloqueio de confianca) e o piloto nao deixaria nada sair.
TITULO = "Ar Condicionado Split Elgin Eco Inverter III 12000 BTUs Frio 220V HJFC12C2WGCG"
HISTORICO = [1950.0, 1930.0, 1899.0, 1940.0, 1960.0]
P0 = 1700.0                                   # preco do primeiro alerta
P = {"2%": 1666.0, "4%": 1632.0, "5%": 1615.0, "6%": 1598.0, "7,06%": 1580.0}   # quedas sobre P0


def regras(modo):
    r = copy.deepcopy(ranking.carregar_regras(operacao=False))
    r["alertas"].update(enviar=True, homologado_em="2026-11-22 09:00")
    r["prioridade"]["limiar_ultimo_comum"] = 40
    r["piloto"] = {**r.get("piloto", {}), "ativo": modo == "PILOTO", "destinatario_confirmado_em": "2026-11-22 09:30"}
    return r


def minutos(m):
    return AGORA + dt.timedelta(minutes=m)


def oferta(fonte, canal, ident, url, *, loja="WebContinental", vendedor=None, preco=P0, cupom=None, quando=AGORA):
    return Oferta(fonte=fonte, canal=canal, id_externo=ident, titulo=TITULO, url=url, loja=loja, vendedor=vendedor, preco_anunciado=preco,
                  texto="oferta", cupom_codigo=cupom, publicado_em=(quando - dt.timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M"))


def pelando_site(**kw):
    return oferta("pelando", "recentes", "p1", "https://www.pelando.com.br/d/elgin-12k-abc?utm_source=feed", **kw)


def pelando_telegram(**kw):          # o parser do Telegram publico nunca informa loja nem vendedor
    kw.setdefault("loja", None)
    return oferta("telegram", "pelandobr", "901", "https://pelando.promo/Xk3Tz9", **kw)


def promobit(**kw):                  # link de afiliado; nenhuma fonte real preenche `vendedor` (todas deixam None)
    return oferta("promobit", "recentes-p1", "b9", "https://www.promobit.com.br/oferta/elgin-12k-9/?tag=afil-123&ref=x", **kw)


class Caixa:
    def __init__(self):
        self.msgs = []

    def __call__(self, t):
        self.msgs.append(t)
        return True, "ok"


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        p = mock.patch.dict(os.environ, {"CENTRAL_COMPRAS_DADOS_PRIVADOS": self._tmp.name})
        p.start()
        self.addCleanup(p.stop)
        self.addCleanup(self._tmp.cleanup)
        self.con = db.abrir()
        self.addCleanup(self.con.close)
        for i, preco in enumerate(HISTORICO):
            t = (AGORA - dt.timedelta(days=3) + dt.timedelta(hours=12 * i)).strftime("%Y-%m-%d %H:%M")
            self.con.execute("INSERT INTO observacoes (origem, produto, coletado_em, preco_entregue, onde, hash) VALUES (?,?,?,?,?,?)",
                             ("rastreador-ares", "elgin_12k", t, preco, "WebContinental", f"h{i}"))
        self.con.commit()
        self.cat = catalogo.carregar()
        self.caixa = Caixa()

    def limpar(self):
        for tab in ("alertas", "candidatos_alerta", "ofertas", "outbox"):
            self.con.execute(f"DELETE FROM {tab}")
        self.con.commit()
        self.caixa.msgs.clear()

    def ciclo(self, ofertas, quando, modo):
        """Uma varredura real: cada oferta vira candidato (diferir=True) e o despachante decide ao fim do ciclo."""
        r = regras(modo)
        res = [varredura.processar_oferta(self.con, o, self.cat, r, self.caixa, quando, diferir=True) for o in ofertas]
        dec = prioridade.despachar(self.con, r, self.caixa, quando)
        return res, dec

    def estados(self):
        return sorted((x["fonte"], x["estado"]) for x in self.con.execute("SELECT fonte, estado FROM candidatos_alerta"))

    def estados_so(self):
        return sorted(e for _, e in self.estados())


class MesmaOfertaEmTresFontesTest(Base):
    def test_mesmo_ciclo_pelando_site_telegram_e_promobit_geram_uma_unica_mensagem(self):
        for modo in ("PILOTO", "COMPLETO"):
            with self.subTest(modo=modo):
                self.limpar()
                res, _ = self.ciclo([pelando_site(), pelando_telegram(), promobit()], AGORA, modo)
                self.assertTrue(all(r["produto"] == "elgin_12k" for r in res), res)
                self.assertEqual(len(self.caixa.msgs), 1, self.estados())
                self.assertEqual(self.estados_so(), ["enviado", "substituido", "substituido"])

    def test_outra_fonte_nos_ciclos_seguintes_nao_repete_com_loja_e_vendedor_presentes_ou_ausentes(self):
        combos = [("WebContinental", None), (None, None), ("WebContinental", "WebContinental"), (None, "Outro Vendedor"), ("Amazon", None)]
        for modo in ("PILOTO", "COMPLETO"):
            for loja, vendedor in combos:
                with self.subTest(modo=modo, loja=loja, vendedor=vendedor):
                    self.limpar()
                    self.ciclo([promobit()], AGORA, modo)
                    self.assertEqual(len(self.caixa.msgs), 1)
                    outra = pelando_telegram(loja=loja, vendedor=vendedor)
                    self.ciclo([outra], minutos(10), modo)                       # mesmo preco, link diferente
                    self.ciclo([pelando_site(loja=loja, vendedor=vendedor)], minutos(20), modo)
                    self.assertEqual(len(self.caixa.msgs), 1, self.estados())

    def test_preco_igual_em_loja_diferente_tambem_nao_gera_segundo_alerta_do_mesmo_produto(self):
        """O anti-repeticao do despachante olha so o PRODUTO (nao a loja nem a fonte)."""
        for modo in ("PILOTO", "COMPLETO"):
            with self.subTest(modo=modo):
                self.limpar()
                self.ciclo([promobit()], AGORA, modo)
                self.ciclo([pelando_telegram(loja="Amazon")], minutos(10), modo)
                self.assertEqual(len(self.caixa.msgs), 1)
                self.assertIn("suprimido_repeticao", self.estados_so())

    def test_cupom_repetido_nas_tres_fontes_no_mesmo_ciclo_gera_uma_mensagem(self):
        for modo in ("PILOTO", "COMPLETO"):
            with self.subTest(modo=modo):
                self.limpar()
                self.ciclo([pelando_site(cupom="ELGIN10"), pelando_telegram(cupom="ELGIN10"), promobit(cupom="ELGIN10")], AGORA, modo)
                self.assertEqual(len(self.caixa.msgs), 1)

    def test_cupom_novo_passa_a_porta_de_24h_mas_o_anti_repeticao_do_produto_segura(self):
        """Primeiro alerta sem cupom; outra fonte traz o MESMO preco com cupom: `cupom_novo` libera a porta de 24 h, e o despachante suprime."""
        for modo in ("PILOTO", "COMPLETO"):
            with self.subTest(modo=modo):
                self.limpar()
                self.ciclo([promobit()], AGORA, modo)
                res, _ = self.ciclo([pelando_telegram(cupom="ELGIN10")], minutos(15), modo)
                self.assertTrue(res[0]["acao"].startswith("candidato"), res[0]["acao"])      # passou na porta de 24 h
                self.assertEqual(len(self.caixa.msgs), 1)                                   # e foi segurado depois
                self.assertIn("suprimido_repeticao", self.estados_so())

    def test_porta_de_24h_suprime_o_mesmo_item_de_outra_fonte_com_a_mesma_chave(self):
        r = regras("COMPLETO")
        alertas.registrar(self.con, oferta_id=None, produto="elgin_12k", loja="WebContinental", vendedor="WebContinental", cupom=None, preco=P0,
                          url="https://www.promobit.com.br/oferta/x/?tag=a", classe="ALTA", status="PROVAVEL", modo="real", detalhe="t", agora=AGORA)
        kw = dict(produto="elgin_12k", loja="WebContinental", vendedor="WebContinental", cupom=None, preco=P0, status="PROVAVEL", classe="ALTA",
                  regras=r, agora=minutos(30))
        self.assertEqual(alertas.gates(self.con, **kw)[0], "suprimir")


class ChaveDeDeduplicacaoTest(unittest.TestCase):
    base = dict(produto="elgin_12k", loja="WebContinental", vendedor="WebContinental", cupom=None, preco=1700.0)

    def test_parametros_de_afiliado_www_e_barra_final_nao_mudam_a_chave(self):
        a = alertas.chave_exata(**self.base, url="https://www.promobit.com.br/oferta/elgin-12k-9/?tag=afil-123&ref=x")
        b = alertas.chave_exata(**self.base, url="http://promobit.com.br/oferta/elgin-12k-9/#topo")
        self.assertEqual(a, b)

    def test_preco_so_conta_arredondado_para_o_real(self):
        a = alertas.chave_exata(**{**self.base, "preco": 1699.60}, url="https://x.com/a")
        b = alertas.chave_exata(**{**self.base, "preco": 1700.40}, url="https://x.com/a")
        self.assertEqual(a, b)

    def test_dominios_diferentes_mudam_a_chave_exata_mas_nao_a_familia(self):
        """Pelando site e Pelando Telegram usam dominios diferentes: a chave EXATA difere (inclui o link), a FAMILIA (produto+loja+vendedor) nao."""
        site = alertas.chave_exata(**self.base, url="https://www.pelando.com.br/d/elgin-12k-abc")
        tg = alertas.chave_exata(**self.base, url="https://pelando.promo/Xk3Tz9")
        self.assertNotEqual(site, tg)
        self.assertEqual(alertas.chave_familia("elgin_12k", "WebContinental", "WebContinental"), alertas.chave_familia("elgin_12k", "webcontinental", "WEBCONTINENTAL"))

    def test_LIMITACAO_loja_ou_vendedor_ausente_muda_a_familia_e_a_porta_de_24h_nao_junta(self):
        """A porta de 24 h nao junta 'WebContinental' com 'sem loja' (Telegram nao informa loja). Quem segura e o anti-repeticao por produto."""
        f = alertas.chave_familia
        self.assertNotEqual(f("elgin_12k", "WebContinental", None), f("elgin_12k", None, None))
        self.assertNotEqual(f("elgin_12k", "WebContinental", "WebContinental"), f("elgin_12k", "WebContinental", None))


class LimitesDe3E7PorCentoTest(Base):
    def alerta_inicial(self, modo):
        self.limpar()
        self.ciclo([promobit(preco=P0)], AGORA, modo)
        self.assertEqual(len(self.caixa.msgs), 1)

    def test_porta_de_24h_exige_3_por_cento(self):
        r = regras("COMPLETO")
        alertas.registrar(self.con, oferta_id=None, produto="elgin_12k", loja="WebContinental", vendedor=None, cupom=None, preco=P0, url="https://x/1",
                          classe="ALTA", status="PROVAVEL", modo="real", detalhe="t", agora=AGORA)
        def porta(preco):
            return alertas.gates(self.con, produto="elgin_12k", loja="WebContinental", vendedor=None, cupom=None, preco=preco, status="PROVAVEL",
                                 classe="ALTA", regras=r, agora=minutos(300))[0]
        self.assertEqual(porta(P0 * 0.98), "suprimir")     # 2%
        self.assertEqual(porta(P0 * 0.971), "suprimir")    # 2,9%
        self.assertEqual(porta(P0 * 0.969), "ok")          # 3,1%
        self.assertEqual(porta(P["4%"]), "ok")

    def test_piloto_nas_primeiras_4_horas_suprime_2_4_e_5_por_cento_e_libera_6_com_r_102_e_7(self):
        """Base R$ 1.700: 2% (R$ 34), 4% (R$ 68) e 5% (R$ 85) seguem suprimidos; 6% ja e R$ 102 (>= R$ 100 e >= 3%) e libera; 7% libera pela regra dos 7%."""
        for nome in ("2%", "4%", "5%"):
            with self.subTest(queda=nome):
                self.alerta_inicial("PILOTO")
                self.ciclo([pelando_telegram(preco=P[nome])], minutos(30), "PILOTO")
                self.assertEqual(len(self.caixa.msgs), 1, self.estados())
        for nome in ("6%", "7,06%"):
            with self.subTest(queda=nome):
                self.alerta_inicial("PILOTO")
                self.ciclo([pelando_telegram(preco=P[nome])], minutos(30), "PILOTO")
                self.assertEqual(len(self.caixa.msgs), 2, self.estados())

    def test_piloto_depois_de_4_horas_vale_so_a_regra_de_3_por_cento(self):
        """Mesma loja (o alerta agora e registrado com a loja da oferta): a porta de 24 h acha o alerta anterior."""
        self.alerta_inicial("PILOTO")
        self.ciclo([pelando_site(preco=P["2%"])], minutos(250), "PILOTO")              # 2%: a porta de 24 h segura
        self.assertEqual(len(self.caixa.msgs), 1)
        self.limpar(); self.alerta_inicial("PILOTO")
        self.ciclo([pelando_site(preco=P["4%"])], minutos(250), "PILOTO")              # 4%: passa em tudo
        self.assertEqual(len(self.caixa.msgs), 2, self.estados())

    def test_alerta_enviado_pelo_despachante_e_registrado_com_a_loja_da_oferta(self):
        """Regressao: o despachante registrava o alerta sem loja, e a porta de 24 h (familia produto+loja+vendedor) nunca o encontrava."""
        self.alerta_inicial("PILOTO")
        fam = self.con.execute("SELECT chave FROM alertas ORDER BY id DESC LIMIT 1").fetchone()[0].split("|")[0]
        self.assertEqual(fam, alertas.chave_familia("elgin_12k", "WebContinental", None))
        self.assertNotEqual(fam, alertas.chave_familia("elgin_12k", None, None))

    def test_alerta_em_sombra_tambem_e_registrado_com_a_loja_da_oferta(self):
        r = regras("SOMBRA")
        res = [varredura.processar_oferta(self.con, promobit(preco=P0), self.cat, r, None, AGORA, diferir=True)]
        prioridade.despachar(self.con, r, None, AGORA)
        self.assertEqual(self.con.execute("SELECT modo FROM alertas").fetchone()[0], "sombra")
        fam = self.con.execute("SELECT chave FROM alertas ORDER BY id DESC LIMIT 1").fetchone()[0].split("|")[0]
        self.assertEqual(fam, alertas.chave_familia("elgin_12k", "WebContinental", None))
        self.assertEqual(res[0]["produto"], "elgin_12k")

    def test_LIMITACAO_oferta_sem_loja_nao_casa_com_o_alerta_de_uma_loja_na_porta_de_24h(self):
        """A porta de 24 h compara a familia produto+loja: uma oferta SEM loja (o Telegram nunca informa) nao e vista como a mesma do alerta da
        WebContinental e passa a porta. No piloto real isso nao vaza, porque Telegram e Pelando nao sao revalidaveis; fica documentado."""
        self.alerta_inicial("PILOTO")
        r = regras("PILOTO")
        kw = dict(produto="elgin_12k", vendedor=None, cupom=None, preco=P["2%"], status="PROVAVEL", classe="ALTA", regras=r, agora=minutos(250))
        self.assertEqual(alertas.gates(self.con, loja="WebContinental", **kw)[0], "suprimir")
        self.assertEqual(alertas.gates(self.con, loja=None, **kw)[0], "ok")

    def test_politica_completa_usa_90_min_e_5_por_cento(self):
        self.alerta_inicial("COMPLETO")
        self.ciclo([pelando_telegram(preco=P["4%"])], minutos(30), "COMPLETO")           # 4% em 30 min: suprimido
        self.assertEqual(len(self.caixa.msgs), 1)
        self.limpar(); self.alerta_inicial("COMPLETO")
        self.ciclo([pelando_telegram(preco=1610.0)], minutos(30), "COMPLETO")            # 5,3% em 30 min: passa
        self.assertEqual(len(self.caixa.msgs), 2, self.estados())
        self.limpar(); self.alerta_inicial("COMPLETO")
        self.ciclo([pelando_telegram(preco=P["4%"])], minutos(100), "COMPLETO")          # 4% apos 90 min: passa
        self.assertEqual(len(self.caixa.msgs), 2, self.estados())

    def test_queda_de_6_por_cento_com_r_102_de_economia_agora_alerta_dentro_da_janela(self):
        """Corrigido em 22/11/2026: antes a queda de 6% (R$ 102 sobre R$ 1.700) dentro dos 240 min era suprimida."""
        self.alerta_inicial("PILOTO")
        self.ciclo([pelando_telegram(preco=P["6%"])], minutos(30), "PILOTO")
        ultimo = self.con.execute("SELECT preco FROM alertas ORDER BY id DESC LIMIT 1").fetchone()
        self.assertEqual(ultimo["preco"], P["6%"])
        self.assertEqual(len(self.caixa.msgs), 2)

    def test_mesmo_anuncio_que_baixa_4_por_cento_e_nao_muda_e_reavaliado_quando_a_janela_acaba(self):
        """Corrigido em 22/11/2026: o anuncio X alerta a R$ 1.700, cai 4% (R$ 68) e e suprimido; quando passam os 240 min o preco continua
        igual e a oferta agora e REAVALIADA (antes era descartada como `sem_mudanca_desde_a_ultima_vez`). So reavalia uma vez por janela."""
        x = lambda preco, q: promobit(preco=preco, quando=q)            # mesmo fonte/canal/id: e o MESMO anuncio
        self.limpar()
        self.ciclo([x(P0, AGORA)], AGORA, "PILOTO")
        self.assertEqual(len(self.caixa.msgs), 1)
        self.ciclo([x(P["4%"], minutos(60))], minutos(60), "PILOTO")
        self.assertIn("suprimido_repeticao", self.estados_so())
        res, _ = self.ciclo([x(P["4%"], minutos(60))], minutos(255), "PILOTO")          # >240 min, mesmo preco
        self.assertTrue(res[0].get("reavaliada"), res[0])
        self.assertEqual(len(self.caixa.msgs), 2)
        self.ciclo([x(P["4%"], minutos(60))], minutos(265), "PILOTO")                   # ja alertou: nao repete a cada ciclo
        self.assertEqual(len(self.caixa.msgs), 2)

    def test_recomendacao_o_mesmo_anuncio_em_outra_fonte_apos_4h_ainda_alerta(self):
        """Mitigacao natural: se OUTRA fonte (outro id) publicar o mesmo preco depois dos 240 min, vira oferta nova e alerta."""
        self.limpar()
        self.ciclo([promobit(preco=P0)], AGORA, "PILOTO")
        self.ciclo([promobit(preco=P["4%"], quando=minutos(60))], minutos(60), "PILOTO")
        self.ciclo([pelando_telegram(preco=P["4%"], quando=minutos(255))], minutos(255), "PILOTO")
        self.assertEqual(len(self.caixa.msgs), 2, self.estados())


if __name__ == "__main__":
    unittest.main()
