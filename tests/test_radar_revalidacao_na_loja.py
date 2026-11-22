"""Revalidacao NA LOJA, independente da fonte de descoberta (Telegram, Pelando site, Promobit...).

Garante que a oferta descoberta so no Telegram ou no Pelando PODE gerar alerta quando a loja confirma produto exato, vendedor proprio,
disponibilidade, preco e cupom, e que uma postagem ainda acessivel NUNCA e prova de que o desconto vale. Quando a loja nao pode ser verificada
a oferta fica PENDENTE (nunca 'expirada' por isso). Tudo com HTTP falso e banco temporario: nenhuma rede, nenhum envio real, nenhuma compra."""

import copy
import datetime as dt
import json
import os
import tempfile
import unittest
from unittest import mock

from radar import catalogo, db, lojas, prioridade, ranking, varredura
from radar.fontes.base import FonteErro
from radar.modelos import Oferta

AGORA = dt.datetime(2026, 11, 22, 10, 0)
ELGIN = "Ar Condicionado Split Elgin Eco Inverter III 12000 BTUs Frio 220V HJFC12C2WGCG"
ELGIN18 = "Ar Condicionado Split Elgin Eco Inverter III 18000 BTUs Frio 220V"
PHILCO = "Ar Condicionado Split Philco Inverter Frio 18000 BTUS 220V PAC18FTW"
BASE_WC = "https://www.webcontinental.com.br"


def minutos(m):
    return AGORA + dt.timedelta(minutes=m)


def regras(modo="PILOTO"):
    r = copy.deepcopy(ranking.carregar_regras(operacao=False))
    r["alertas"].update(enviar=True, homologado_em="2026-11-22 09:00")
    r["prioridade"]["limiar_ultimo_comum"] = 40
    r["piloto"] = {**r.get("piloto", {}), "ativo": modo == "PILOTO", "destinatario_confirmado_em": "2026-11-22 09:30"}
    return r


def busca_json(nome, preco=1700.0, qtd=10, vendedor="WebContinental", seller_id="1", item_id="9001"):
    return json.dumps([{"productName": nome, "link": f"{BASE_WC}/x/p", "items": [{"itemId": item_id, "ean": "789", "sellers": [
        {"sellerId": seller_id, "sellerName": vendedor, "commertialOffer": {"Price": preco, "ListPrice": preco, "AvailableQuantity": qtd}}]}]}])


def sim_json(preco, cupom_aplicado=None, desconto=0.0, disponivel=True, msgs=()):
    return json.dumps({"items": [{"id": "9001", "quantity": 1, "sellingPrice": int(round(preco * 100)), "availability": "available" if disponivel else "unavailable"}],
                       "totals": [{"id": "Items", "value": int(round(preco * 100))}, {"id": "Discounts", "value": -int(round(desconto * 100))}],
                       "marketingData": {"coupon": cupom_aplicado} if cupom_aplicado else None, "messages": [{"text": m} for m in msgs]})


class LojaFalsa:
    """API publica VTEX falsa: busca por SKU e simulacao de carrinho. Guarda tudo que foi consultado (para provar que o link de afiliado nao e seguido)."""

    def __init__(self):
        self.gets, self.posts = [], []
        self.catalogo = {"HJFC12C2WGCG": busca_json(ELGIN, 1700.0), "PAC18FTW": busca_json(PHILCO, 2500.0)}
        self.cupons: dict[str, float] = {}      # codigo -> desconto em reais que o carrinho aceita
        self.fora = False                       # loja fora do ar
        self.sim_fora = False                   # so a simulacao fora do ar

    def baixar(self, url):
        self.gets.append(url)
        if self.fora:
            raise FonteErro(f"{url}: HTTP 503")
        sku = url.split("ft=")[-1]
        return self.catalogo.get(sku, "[]")

    def postar(self, url, corpo, **kw):
        self.posts.append((url, corpo))
        if self.fora or self.sim_fora:
            raise FonteErro(f"{url}: HTTP 503")
        item = json.loads(self.catalogo["HJFC12C2WGCG"])[0]["items"][0]
        preco = item["sellers"][0]["commertialOffer"]["Price"]
        cupom = (corpo.get("marketingData") or {}).get("coupon")
        if cupom and cupom in self.cupons:
            return sim_json(preco, cupom_aplicado=cupom, desconto=self.cupons[cupom])
        if cupom:
            return sim_json(preco, msgs=[f"Cupom {cupom} inválido"])
        return sim_json(preco)


def tg(canal, ident, texto, url, preco, quando=AGORA, cupom=None):
    """Oferta como o parser do Telegram publico a monta: sem loja, sem vendedor, link original da postagem."""
    return Oferta(fonte="telegram", canal=canal, id_externo=ident, titulo=texto.split("\n")[0][:200], texto=texto, url=url, preco_anunciado=preco, cupom_codigo=cupom,
                  publicado_em=(quando - dt.timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M"))


def pelando_site(preco=1700.0, quando=AGORA, titulo=ELGIN, loja="WebContinental", cupom=None):
    return Oferta(fonte="pelando", canal="recentes", id_externo="p1", titulo=titulo, url="https://www.pelando.com.br/d/elgin-abc?utm_source=feed", loja=loja,
                  preco_anunciado=preco, texto="oferta", cupom_codigo=cupom, publicado_em=(quando - dt.timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M"))


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
        for prod, hist in (("elgin_12k", [1950.0, 1930.0, 1899.0, 1940.0, 1960.0]), ("philco_18k", [2850.0, 2830.0, 2799.0, 2840.0, 2860.0])):
            for i, preco in enumerate(hist):
                t = (AGORA - dt.timedelta(days=3) + dt.timedelta(hours=12 * i)).strftime("%Y-%m-%d %H:%M")
                self.con.execute("INSERT INTO observacoes (origem, produto, coletado_em, preco_entregue, onde, hash) VALUES (?,?,?,?,?,?)",
                                 ("rastreador-ares", prod, t, preco, "WebContinental", f"{prod}{i}"))
        self.con.commit()
        self.cat = catalogo.carregar()
        self.caixa = Caixa()
        self.loja = LojaFalsa()
        self.lojas_cfg = lojas.carregar()

    def revalidar(self, oid):
        return varredura.revalidar_oferta(self.con, oid, loja_baixar=self.loja.baixar, loja_postar=self.loja.postar, lojas_cfg=self.lojas_cfg)

    def ciclo(self, ofertas, quando, modo="PILOTO", revalidar=None):
        r = regras(modo)
        res = [varredura.processar_oferta(self.con, o, self.cat, r, self.caixa, quando, diferir=True) for o in ofertas]
        dec = prioridade.despachar(self.con, r, self.caixa, quando, revalidar=revalidar or self.revalidar)
        return res, dec

    def estados(self):
        return [(x["fonte"], x["estado"]) for x in self.con.execute("SELECT fonte, estado FROM candidatos_alerta ORDER BY id")]

    def ultimo(self):
        return self.con.execute("SELECT estado, motivo FROM candidatos_alerta ORDER BY id DESC LIMIT 1").fetchone()


# ---------------------------------------------------------------------------------------------------------------- unidades
class InferirLojaTest(unittest.TestCase):
    def setUp(self):
        self.cfg = lojas.carregar()

    def test_loja_configurada_citada_no_texto_ou_no_dominio_direto(self):
        f = lambda t, u=None: lojas.inferir_loja(t, u, self.cfg)
        self.assertEqual(f("Split Elgin Por R$ 1.579,00 na WebContinental"), "WebContinental")
        self.assertEqual(f("💰 R$ 1.700 📍 Web Continental ➡️"), "WebContinental")
        self.assertEqual(f("oferta Frio Peças R$ 2.948"), "FrioPecas")
        self.assertEqual(f("sem loja no texto", "https://www.webcontinental.com.br/ar-condicionado/p"), "WebContinental")
        self.assertEqual(f("sem loja no texto", "https://loja.friopecas.com.br/x"), "FrioPecas")

    def test_loja_nao_configurada_ou_link_de_afiliado_nao_identifica_nada(self):
        f = lambda t, u=None: lojas.inferir_loja(t, u, self.cfg)
        self.assertIsNone(f("Ar condicionado na Amazon", "https://link.amazon/B05XYZ"))
        self.assertIsNone(f("oferta", "https://pelando.promo/Xk3Tz9"))          # encurtador: nunca e resolvido
        self.assertIsNone(f("oferta", "https://meli.la/1abc"))
        self.assertIsNone(f("", None))


class SimularCarrinhoTest(unittest.TestCase):
    cfg = {"base": BASE_WC}

    def sim(self, resposta, cupom="C10", itens=None):
        postar = (lambda url, corpo, **kw: resposta) if not isinstance(resposta, Exception) else mock.Mock(side_effect=resposta)
        return lojas.simular_carrinho(self.cfg, "9001", "1", cupom, postar=postar)

    def test_cupom_aceito_com_desconto(self):
        r = self.sim(sim_json(1700.0, cupom_aplicado="C10", desconto=100.0))
        self.assertEqual((r["ok"], r["cupom_aplicado"], r["disponivel"], r["preco"]), (True, True, True, 1600.0))

    def test_cupom_invalido_traz_a_mensagem_da_loja(self):
        r = self.sim(sim_json(1700.0, msgs=["Cupom C10 inválido"]))
        self.assertEqual((r["ok"], r["cupom_aplicado"]), (True, False))
        self.assertIn("inválido", r["mensagens"][0])

    def test_indisponivel_e_falha_de_rede(self):
        self.assertFalse(self.sim(sim_json(1700.0, cupom_aplicado="C10", disponivel=False))["disponivel"])
        r = self.sim(FonteErro("HTTP 503"))
        self.assertEqual(r["ok"], False)
        self.assertEqual(self.sim("isto nao e json")["ok"], False)

    def test_nunca_envia_cep_nem_dado_pessoal(self):
        corpos = []
        lojas.simular_carrinho(self.cfg, "9001", "1", "C10", postar=lambda url, corpo, **kw: (corpos.append(corpo) or sim_json(1700.0)))
        self.assertEqual(set(corpos[0]), {"items", "country", "marketingData"})
        self.assertNotIn("postalCode", json.dumps(corpos[0]))
        self.assertEqual(corpos[0]["items"][0]["quantity"], 1)


class RevalidarNaLojaTest(unittest.TestCase):
    """A decisao pura, com linha de oferta falsa e loja falsa."""

    def setUp(self):
        self.loja = LojaFalsa()
        self.cfg = lojas.carregar()

    def rv(self, **row):
        base = {"produto": "elgin_12k", "loja": "WebContinental", "titulo": ELGIN, "url": "https://pelando.promo/x", "preco_anunciado": 1700.0,
                "preco_final": 1700.0, "cupom_codigo": None}
        return lojas.revalidar_na_loja({**base, **row}, lojas=self.cfg, baixar=self.loja.baixar, postar=self.loja.postar)

    def test_confirmada_quando_o_produto_exato_esta_na_loja_pelo_preco_prometido(self):
        r = self.rv()
        self.assertEqual(r["resultado"], "confirmada", r)
        self.assertEqual(r["preco_loja"], 1700.0)

    def test_loja_mais_barata_que_o_prometido_tambem_confirma(self):
        self.loja.catalogo["HJFC12C2WGCG"] = busca_json(ELGIN, 1650.0)
        self.assertEqual(self.rv()["resultado"], "confirmada")

    def test_anuncio_encerrado_sem_estoque_ou_ausente(self):
        self.loja.catalogo["HJFC12C2WGCG"] = busca_json(ELGIN, 0.0, qtd=0)
        self.assertEqual(self.rv()["resultado"], "encerrada")
        self.loja.catalogo["HJFC12C2WGCG"] = "[]"
        r = self.rv()
        self.assertEqual(r["resultado"], "encerrada")
        self.assertIn("nao encontrado", r["motivo"])

    def test_produto_errado_modelo_ou_voltagem_nao_confirma(self):
        self.loja.catalogo["HJFC12C2WGCG"] = busca_json(ELGIN18, 1700.0)                       # outro modelo para o mesmo SKU buscado
        self.assertEqual(self.rv()["resultado"], "encerrada")
        self.loja.catalogo["HJFC12C2WGCG"] = busca_json(ELGIN.replace("220V", "127V"), 1700.0)  # voltagem errada
        self.assertNotEqual(self.rv()["resultado"], "confirmada")

    def test_vendedor_terceiro_nao_conta(self):
        self.loja.catalogo["HJFC12C2WGCG"] = busca_json(ELGIN, 1500.0, vendedor="Lojas Mm", seller_id="002647")
        r = self.rv()
        self.assertEqual(r["resultado"], "encerrada")
        self.assertIn("PROPRIO", r["motivo"])

    def test_preco_diferente_no_carrinho_sem_cupom_e_divergente(self):
        self.loja.catalogo["HJFC12C2WGCG"] = busca_json(ELGIN, 1850.0)
        r = self.rv()
        self.assertEqual(r["resultado"], "divergente")
        self.assertIn("1850.00", r["motivo"])

    def test_cupom_valido_confirma_pelo_preco_com_cupom_na_simulacao(self):
        self.loja.catalogo["HJFC12C2WGCG"] = busca_json(ELGIN, 1850.0)
        self.loja.cupons["ELGIN10"] = 150.0
        r = self.rv(cupom_codigo="ELGIN10")
        self.assertEqual(r["resultado"], "confirmada", r)
        self.assertEqual(r["cupom_simulado"]["preco"], 1700.0)
        self.assertEqual(self.loja.posts[0][1]["marketingData"], {"coupon": "ELGIN10"})

    def test_cupom_invalido_e_divergente(self):
        self.loja.catalogo["HJFC12C2WGCG"] = busca_json(ELGIN, 1850.0)
        r = self.rv(cupom_codigo="ELGINXX")
        self.assertEqual(r["resultado"], "divergente")
        self.assertIn("invalido", r["motivo"])

    def test_cupom_aceito_mas_sem_efeito_suficiente_e_divergente(self):
        self.loja.catalogo["HJFC12C2WGCG"] = busca_json(ELGIN, 1850.0)
        self.loja.cupons["ELGIN10"] = 50.0
        r = self.rv(cupom_codigo="ELGIN10")
        self.assertEqual(r["resultado"], "divergente")
        self.assertIn("1800.00", r["motivo"])

    def test_loja_fora_do_ar_e_pendente_nunca_encerrada(self):
        self.loja.fora = True
        r = self.rv()
        self.assertEqual(r["resultado"], "pendente", r)
        self.assertIn("PENDENTE", r["motivo"])

    def test_simulacao_fora_do_ar_deixa_pendente_sem_inventar_preco(self):
        self.loja.catalogo["HJFC12C2WGCG"] = busca_json(ELGIN, 1850.0)
        self.loja.sim_fora = True
        r = self.rv(cupom_codigo="ELGIN10")
        self.assertEqual(r["resultado"], "pendente")
        self.assertNotIn("cupom_simulado", r)

    def test_loja_sem_verificacao_publica_ou_sem_loja_e_pendente(self):
        self.assertEqual(self.rv(loja="Amazon")["resultado"], "pendente")
        self.assertEqual(self.rv(loja=None, titulo=ELGIN, url="https://link.amazon/x")["resultado"], "pendente")
        self.assertEqual(self.loja.gets, [])                                    # nem consulta quando nao ha loja verificavel

    def test_loja_inferida_do_texto_quando_a_fonte_nao_informa(self):
        r = self.rv(loja=None, titulo=ELGIN + " na WebContinental")
        self.assertEqual(r["resultado"], "confirmada", r)

    def test_produto_fora_do_catalogo_ou_em_dolar_e_pendente(self):
        self.assertEqual(self.rv(produto=None)["resultado"], "pendente")
        self.assertEqual(self.rv(produto="xiaomi_s40_pro_py")["resultado"], "pendente")


# ---------------------------------------------------------------------------------------------------------------- pipeline
class CanaisExclusivosTest(Base):
    def alerta_pelo_canal(self, oferta, quando=AGORA):
        res, _ = self.ciclo([oferta], quando)
        return res[0]

    def test_exclusiva_do_telegram_promobit_com_loja_no_texto_gera_alerta(self):
        o = tg("cupons_desconto", "84701", f"{ELGIN}\nPor R$ 1.700,00 na WebContinental", "https://tidd.ly/abc123", 1700.0)
        self.alerta_pelo_canal(o)
        self.assertEqual(len(self.caixa.msgs), 1, self.estados())
        self.assertIn("WebContinental", self.caixa.msgs[0])
        self.assertEqual(self.estados(), [("telegram", "enviado")])

    def test_exclusiva_do_telegram_pelando_com_loja_no_texto_gera_alerta(self):
        o = tg("pelandobr", "901", f"{ELGIN}\n💰 R$ 1700,00 📍 WebContinental ➡️ https://pelando.promo/Xk3Tz9", "https://pelando.promo/Xk3Tz9", 1700.0)
        self.alerta_pelo_canal(o)
        self.assertEqual(len(self.caixa.msgs), 1, self.estados())

    def test_exclusiva_do_telegram_thautec_amazon_fica_pendente_e_nao_alerta(self):
        o = tg("ofertasthautec", "7001", f"{ELGIN}\n🔥 R$ 1.700 na Amazon\nhttps://link.amazon/B05XYZ", "https://link.amazon/B05XYZ", 1700.0)
        self.alerta_pelo_canal(o)
        self.assertEqual(len(self.caixa.msgs), 0)
        self.assertEqual(self.estados(), [("telegram", "pendente")])               # NAO e 'expirado'
        self.assertIn("aguardando confirmacao na loja", self.ultimo()["motivo"])
        self.assertEqual(self.loja.gets, [])                                         # sem loja verificavel: nao consulta nada
        self.ciclo([], minutos(40))                                                  # passou a validade do candidato (30 min)
        self.assertEqual(self.ultimo()["estado"], "nao_confirmada")
        self.assertIn("NAO e prova de que a oferta acabou", self.ultimo()["motivo"])
        self.assertEqual(len(self.caixa.msgs), 0)

    def test_exclusiva_do_pelando_site_gera_alerta(self):
        self.alerta_pelo_canal(pelando_site())
        self.assertEqual(len(self.caixa.msgs), 1, self.estados())

    def test_link_de_afiliado_nunca_e_seguido(self):
        for o in (tg("pelandobr", "901", f"{ELGIN}\n📍 WebContinental ➡️ https://pelando.promo/Xk3", "https://pelando.promo/Xk3", 1700.0), pelando_site()):
            self.ciclo([o], AGORA)
            self.loja.gets.append("--")
        consultados = [u for u in self.loja.gets + [p[0] for p in self.loja.posts] if u != "--"]
        self.assertTrue(consultados)
        self.assertTrue(all(u.startswith(BASE_WC) for u in consultados), consultados)    # so a API da loja: nunca pelando.promo, tidd.ly, link.amazon...

    def test_nada_e_comprado_so_consulta_e_simulacao(self):
        self.loja.catalogo["HJFC12C2WGCG"] = busca_json(ELGIN, 1850.0)
        self.loja.cupons["ELGIN10"] = 150.0
        self.ciclo([pelando_site(preco=1700.0, cupom="ELGIN10")], AGORA)
        urls = [p[0] for p in self.loja.posts]
        self.assertTrue(all(u.endswith("/api/checkout/pub/orderForms/simulation") for u in urls), urls)       # simulacao, nunca pedido
        self.assertFalse(any("order" in u and "simulation" not in u for u in urls))


class OfertaNaoConfirmadaTest(Base):
    def test_anuncio_encerrado_nao_alerta(self):
        self.loja.catalogo["HJFC12C2WGCG"] = busca_json(ELGIN, 0.0, qtd=0)
        self.ciclo([pelando_site()], AGORA)
        self.assertEqual((len(self.caixa.msgs), self.ultimo()["estado"]), (0, "expirado"))
        self.assertIn("sem estoque", self.ultimo()["motivo"])

    def test_preco_diferente_no_carrinho_nao_alerta(self):
        self.loja.catalogo["HJFC12C2WGCG"] = busca_json(ELGIN, 1850.0)
        self.ciclo([pelando_site(preco=1700.0)], AGORA)
        self.assertEqual((len(self.caixa.msgs), self.ultimo()["estado"]), (0, "expirado"))
        self.assertIn("1850.00", self.ultimo()["motivo"])

    def test_cupom_invalido_nao_alerta(self):
        self.loja.catalogo["HJFC12C2WGCG"] = busca_json(ELGIN, 1850.0)
        self.ciclo([pelando_site(preco=1700.0, cupom="CUPOMXX")], AGORA)
        self.assertEqual((len(self.caixa.msgs), self.ultimo()["estado"]), (0, "expirado"))
        self.assertIn("invalido", self.ultimo()["motivo"])

    def test_cupom_valido_confirmado_no_carrinho_alerta(self):
        self.loja.catalogo["HJFC12C2WGCG"] = busca_json(ELGIN, 1850.0)
        self.loja.cupons["ELGIN10"] = 150.0
        self.ciclo([pelando_site(preco=1700.0, cupom="ELGIN10")], AGORA)
        self.assertEqual(len(self.caixa.msgs), 1, self.estados())

    def test_produto_errado_na_loja_nao_alerta(self):
        self.loja.catalogo["HJFC12C2WGCG"] = busca_json(ELGIN18, 1700.0)
        self.ciclo([pelando_site()], AGORA)
        self.assertEqual((len(self.caixa.msgs), self.ultimo()["estado"]), (0, "expirado"))

    def test_fonte_indisponivel_fica_pendente_e_alerta_quando_a_loja_volta(self):
        self.loja.fora = True
        self.ciclo([pelando_site()], AGORA)
        self.assertEqual((len(self.caixa.msgs), self.ultimo()["estado"]), (0, "pendente"))        # NAO expirou
        self.loja.fora = False
        self.ciclo([], minutos(10))                                                              # proximo ciclo: reconfere o MESMO candidato
        self.assertEqual(len(self.caixa.msgs), 1, self.estados())
        self.assertEqual(self.ultimo()["estado"], "enviado")

    def test_loja_que_nao_volta_ate_a_validade_vira_nao_confirmada_e_nao_expirada(self):
        self.loja.fora = True
        self.ciclo([pelando_site()], AGORA)
        self.ciclo([], minutos(10))
        self.ciclo([], minutos(45))
        self.assertEqual(self.ultimo()["estado"], "nao_confirmada")
        self.assertEqual(len(self.caixa.msgs), 0)

    def test_nao_confirmada_nao_inventa_preco_confirmado(self):
        self.loja.fora = True
        self.ciclo([pelando_site()], AGORA)
        pend = self.con.execute("SELECT mensagem FROM candidatos_alerta").fetchone()[0]
        self.assertIn("Confirmado na loja: não", pend)                      # a mensagem do candidato pendente nao afirma preco confirmado
        self.assertNotIn("Confiança: ALTA", pend)
        self.assertEqual(self.caixa.msgs, [])

    def test_alerta_de_oferta_so_do_telegram_sai_com_a_conferencia_da_loja_na_mensagem(self):
        """Na varredura real `executar` liga `verificar_loja`; como a loja do Telegram e inferida antes, a mensagem traz o preco conferido na loja."""
        vl = lambda produto, pcat, loja: lojas.verificar(produto, pcat, loja, self.cat, lojas=self.lojas_cfg, baixar=self.loja.baixar, agora=AGORA)
        o = tg("pelandobr", "901", f"{ELGIN}\n📍 WebContinental ➡️ https://pelando.promo/Xk3", "https://pelando.promo/Xk3", 1700.0)
        r = regras()
        varredura.processar_oferta(self.con, o, self.cat, r, self.caixa, AGORA, diferir=True, verificar_loja=vl)
        prioridade.despachar(self.con, r, self.caixa, AGORA, revalidar=self.revalidar)
        self.assertEqual(len(self.caixa.msgs), 1)
        self.assertNotIn("Confirmado na loja: não", self.caixa.msgs[0])
        self.assertIn("1.700,00", self.caixa.msgs[0])


class CoberturaSemPerderOportunidadeTest(Base):
    def test_candidato_pendente_nao_engole_a_oferta_confirmavel_do_mesmo_produto(self):
        """O Thautec (Amazon, nao verificavel) tem pontuacao maior; o Pelando site (WebContinental, confirmavel) tem que alertar mesmo assim."""
        amazon = tg("ofertasthautec", "7001", f"{ELGIN}\n🔥 R$ 1.650 na Amazon\nhttps://link.amazon/B05XYZ", "https://link.amazon/B05XYZ", 1650.0)
        wc = pelando_site(preco=1700.0)
        self.ciclo([amazon, wc], AGORA)
        sc = dict(self.con.execute("SELECT fonte, score FROM candidatos_alerta").fetchall())
        self.assertGreater(sc["telegram"], sc["pelando"])                       # premissa: o pendente tem a maior pontuacao
        self.assertEqual(len(self.caixa.msgs), 1, self.estados())
        self.assertIn("WebContinental", self.caixa.msgs[0])
        self.assertEqual(sorted(self.estados()), [("pelando", "enviado"), ("telegram", "pendente")])

    def test_candidato_encerrado_nao_engole_o_valido_do_mesmo_produto(self):
        vendido_fora = pelando_site(preco=1700.0)
        outro = tg("pelandobr", "901", f"{ELGIN}\n📍 WebContinental ➡️ https://pelando.promo/Xk3", "https://pelando.promo/Xk3", 1700.0)
        self.ciclo([vendido_fora, outro], AGORA, revalidar=lambda oid: (False, "encerrada") if oid == 1 else self.revalidar(oid))
        self.assertEqual(len(self.caixa.msgs), 1, self.estados())

    def test_tres_canais_com_a_mesma_oferta_geram_um_unico_alerta(self):
        t = f"{ELGIN}\nPor R$ 1.700,00 na WebContinental"
        ofs = [tg("cupons_desconto", "1", t, "https://tidd.ly/a", 1700.0), tg("pelandobr", "2", t, "https://pelando.promo/b", 1700.0), pelando_site()]
        self.ciclo(ofs, AGORA)
        self.assertEqual(len(self.caixa.msgs), 1, self.estados())
        self.assertEqual(sorted(e for _, e in self.estados()), ["enviado", "substituido", "substituido"])

    def test_limite_de_um_alerta_por_varredura_vale_para_ofertas_so_do_telegram(self):
        self.loja.catalogo["PAC18FTW"] = busca_json(PHILCO, 2500.0)
        a = tg("pelandobr", "1", f"{ELGIN}\n📍 WebContinental ➡️ https://pelando.promo/a", "https://pelando.promo/a", 1700.0)
        b = tg("cupons_desconto", "2", f"{PHILCO}\nPor R$ 2.500,00 na WebContinental", "https://tidd.ly/b", 2500.0)
        self.ciclo([a, b], AGORA)
        self.assertEqual(len(self.caixa.msgs), 1, self.estados())               # 1 por varredura no TOTAL
        self.ciclo([], minutos(10))
        self.assertEqual(len(self.caixa.msgs), 2, self.estados())               # o outro sai na varredura seguinte

    def test_orcamento_diario_de_2_comuns_vale_para_ofertas_so_do_telegram(self):
        self.gastar_orcamento(2)
        self.ciclo([tg("pelandobr", "1", f"{ELGIN}\n📍 WebContinental ➡️ https://pelando.promo/a", "https://pelando.promo/a", 1700.0)], AGORA)
        self.assertEqual(len(self.caixa.msgs), 0)
        self.assertEqual(self.ultimo()["estado"], "retida_orcamento")

    def gastar_orcamento(self, n):
        for _ in range(n):
            self.con.execute("INSERT INTO candidatos_alerta (produto, familia, classe, score, componentes_json, preco_final, mensagem, estado, motivo, criado_em, expira_em, decidido_em) "
                             "VALUES ('outro','f','ALTA',80,'{}',100,'x','enviado','orcamento:comum','2026-11-22 08:00:00','2026-11-22 08:30:00','2026-11-22 08:00:00')")
        self.con.commit()

    def test_o_piloto_continua_exigindo_produto_exato_sem_avisos(self):
        """Titulo sem SKU: o catalogo avisa `sku_nao_confirmado` e o piloto nao deixa sair, mesmo com a loja confirmando."""
        sem_sku = pelando_site(titulo="Ar Condicionado Split Elgin Eco Inverter III 12000 BTUs Frio 220V")
        self.ciclo([sem_sku], AGORA)
        self.assertEqual(len(self.caixa.msgs), 0)
        self.assertEqual(self.ultimo()["estado"], "nao_selecionado")


class FontesComRevalidacaoPropriaTest(Base):
    """Promobit e Gatry continuam validando a publicacao, e agora a loja tambem tem voz (uma publicacao acessivel nao prova o desconto)."""

    def promobit_row(self):
        from radar.modelos import Oferta as O
        return O(fonte="promobit", canal="recentes-p1", id_externo="b9", titulo=ELGIN, url="https://www.promobit.com.br/oferta/elgin-9/", loja="WebContinental",
                 preco_anunciado=1700.0, texto="oferta", publicado_em=(AGORA - dt.timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M"))

    def oid(self):
        return self.con.execute("SELECT id FROM ofertas").fetchone()[0]

    def rv(self, fonte_resposta, **loja_ajustes):
        self.ciclo([self.promobit_row()], AGORA, revalidar=lambda o: (None, "x"))     # cria a oferta sem enviar
        for k, v in loja_ajustes.items():
            setattr(self.loja, k, v)
        with mock.patch("radar.fontes.promobit.revalidar", return_value=fonte_resposta):
            return self.revalidar(self.oid())

    def test_publicacao_ativa_e_loja_confirma(self):
        self.assertTrue(self.rv((True, "ativa na fonte"))[0])

    def test_publicacao_ativa_mas_loja_cobra_mais_nao_confirma(self):
        self.loja.catalogo["HJFC12C2WGCG"] = busca_json(ELGIN, 1850.0)
        ok, motivo = self.rv((True, "ativa na fonte"))
        self.assertIs(ok, False)
        self.assertIn("divergente", motivo)

    def test_publicacao_ativa_e_loja_nao_verificavel_segue_como_antes(self):
        self.loja.fora = True
        ok, motivo = self.rv((True, "ativa na fonte"))
        self.assertIs(ok, True)
        self.assertIn("loja nao verificada", motivo)

    def test_publicacao_encerrada_manda_mais_que_a_loja(self):
        self.assertIs(self.rv((False, "oferta encerrada na fonte (status FINISHED)"))[0], False)

    def test_publicacao_que_nao_abriu_e_nao_verificavel_nao_encerrada(self):
        ok, _ = self.rv((None, "nao consegui reabrir a oferta"), fora=True)
        self.assertIsNone(ok)

    def test_publicacao_que_nao_abriu_mas_a_loja_confirma_alerta(self):
        self.assertIs(self.rv((None, "nao consegui reabrir a oferta"))[0], True)


class ValidacaoManualTest(Base):
    """`radar validar`: o preco que voce viu no SEU carrinho vale mais que a simulacao anonima da loja, mas so para preco/cupom."""

    def oferta_divergente(self):
        self.loja.catalogo["HJFC12C2WGCG"] = busca_json(ELGIN, 1850.0)
        self.ciclo([pelando_site(preco=1700.0, cupom="CUPOMXX")], AGORA)
        self.assertEqual(self.ultimo()["estado"], "expirado")
        return self.con.execute("SELECT id FROM ofertas").fetchone()[0]

    def validar(self, oid, preco):
        self.con.execute("INSERT OR REPLACE INTO validacoes_manuais (oferta_id, por, em, preco_validado) VALUES (?,?,?,?)", (oid, "Josemar", "2026-11-22 10:00", preco))
        self.con.commit()

    def test_sem_validacao_manual_a_divergencia_barra(self):
        oid = self.oferta_divergente()
        self.assertIs(self.revalidar(oid)[0], False)

    def test_validacao_manual_vale_quando_o_preco_nao_piorou(self):
        oid = self.oferta_divergente()
        self.validar(oid, 1700.0)
        ok, motivo = self.revalidar(oid)
        self.assertIs(ok, True)
        self.assertIn("VALIDADO por Josemar", motivo)

    def test_validacao_manual_vale_dentro_de_2_por_cento(self):
        oid = self.oferta_divergente()
        self.validar(oid, 1670.0)                      # 1700 <= 1670 * 1.02
        self.assertIs(self.revalidar(oid)[0], True)

    def test_validacao_manual_nao_vale_se_o_preco_piorou_mais_de_2_por_cento(self):
        oid = self.oferta_divergente()
        self.validar(oid, 1600.0)
        self.assertIs(self.revalidar(oid)[0], False)

    def test_validacao_manual_nunca_vence_anuncio_encerrado(self):
        oid = self.oferta_divergente()
        self.validar(oid, 1700.0)
        self.loja.catalogo["HJFC12C2WGCG"] = busca_json(ELGIN, 0.0, qtd=0)
        ok, motivo = self.revalidar(oid)
        self.assertIs(ok, False)
        self.assertIn("encerrada", motivo)


class FonteNaoAbreNaoEExpiradaTest(unittest.TestCase):
    def test_promobit_e_gatry_devolvem_none_quando_a_pagina_nao_abre(self):
        from radar.fontes import gatry, promobit

        def cai(url):
            raise FonteErro("sem rede")
        self.assertIsNone(promobit.revalidar("u", 1.0, cai)[0])
        self.assertIsNone(gatry.revalidar("i", 1.0, cai)[0])


if __name__ == "__main__":
    unittest.main()
