"""Adaptadores Gatry (API JSON) e Pelando (HTML/JSON-LD) com fixtures no formato real observado em 21/11/2026."""

import datetime as dt
import json
import unittest

from radar.fontes import gatry, pelando
from radar.fontes.base import FonteErro

AGORA = dt.datetime(2026, 11, 21, 10, 30)


def item(**kw):
    base = {"id": "924fbd5f-6acd-4178-b66b-5e68ec606e6e", "kind": "promotion", "title": "Robô Aspirador KaBuM Smart K800 Pro 127V",
            "description": "", "slug": "robo-k800", "store_name": "Kabum", "url": "https://tidd.ly/abc", "status": "active",
            "price_cents": 109990, "old_price_cents": 149990, "code": None, "discount_text": None, "valid_until": None,
            "created_at": "2026-11-21T12:06:13.114669Z", "approved_at": "2026-11-21T12:07:16.083835Z", "free_shipping": False,
            "requires_coupon_at_checkout": False, "app_only": False, "comment_count": 2, "last_comment_body": "funcionando aqui"}
    base.update(kw)
    return base


def api(promos=None, cupons=None):
    def baixar(url):
        if "kind=coupon" in url:
            return json.dumps({"promotions": cupons or []})
        return json.dumps({"promotions": promos if "offset=0" in url else []})
    return baixar


class GatryTest(unittest.TestCase):
    def test_campos_estruturados_viram_oferta(self):
        of = gatry.parse_item(item(code="casatech10", discount_text="10% OFF", app_only=True, free_shipping=True,
                                   requires_coupon_at_checkout=True, valid_until="2026-11-26T13:00:00Z"))
        self.assertEqual((of.preco_anunciado, of.cupom_codigo, of.loja), (1099.90, "CASATECH10", "Kabum"))
        self.assertEqual(of.extras["preco_antigo"], 1499.90)
        self.assertEqual(of.comentarios, ["funcionando aqui"])
        for trecho in ("10% OFF", "somente no app", "frete gratis", "cupom aplicado no carrinho", "valido ate 26/11/2026"):
            self.assertIn(trecho, of.texto)
        self.assertEqual(of.publicado_em[:10], "2026-11-21")

    def test_no_link_nao_e_codigo(self):
        self.assertIsNone(gatry.parse_item(item(code="NO LINK")).cupom_codigo)
        self.assertIsNone(gatry.parse_item(item(code="")).cupom_codigo)

    def test_cupom_de_loja_e_marcado(self):
        of = gatry.parse_item(item(kind="coupon", title="Amazon", code="CUPONSBF", price_cents=None))
        self.assertEqual((of.extras["tipo"], of.canal, of.preco_anunciado), ("cupom_loja", "cupons", None))

    def test_coletar_ignora_inativas_e_isola_erro_de_uma_pagina(self):
        r = gatry.coletar({"paginas_promocoes": 1}, api([item(), item(id="x2", status="expired")], [item(id="c1", kind="coupon", code="ABCD10")]))
        self.assertEqual(sorted(o.id_externo for o in r), ["924fbd5f-6acd-4178-b66b-5e68ec606e6e", "c1"])

        def meio_fora(url):
            if "kind=coupon" in url:
                raise FonteErro("HTTP 503")
            return json.dumps({"promotions": [item()]})
        self.assertEqual(len(gatry.coletar({"paginas_promocoes": 1}, meio_fora)), 1)

        def tudo_fora(url):
            raise FonteErro("HTTP 503")
        with self.assertRaises(FonteErro):
            gatry.coletar({"paginas_promocoes": 1}, tudo_fora)

    def test_contrato_quebrado_e_erro_explicito(self):
        with self.assertRaises(FonteErro):
            gatry.coletar({"paginas_promocoes": 1}, lambda u: json.dumps({"dados": []}))

    def test_revalidar(self):
        ok = lambda **kw: (lambda u: json.dumps(item(**kw)))
        self.assertTrue(gatry.revalidar("i", 1099.9, ok())[0])
        self.assertFalse(gatry.revalidar("i", 1099.9, ok(status="expired"))[0])
        self.assertIn("subiu", gatry.revalidar("i", 900.0, ok(price_cents=109990))[1])
        self.assertIn("validade", gatry.revalidar("i", None, ok(valid_until="2020-01-01T00:00:00Z"))[1])

        def fora(u):
            raise FonteErro("HTTP 404")
        self.assertFalse(gatry.revalidar("i", 1.0, fora)[0])


class PromobitCursorTest(unittest.TestCase):
    """`?page=N` devolvia sempre os mesmos 12 itens (9 min de cobertura). O Promobit pagina por cursor (?after=)."""

    @staticmethod
    def pagina(ids, after):
        ofertas = [{"offerId": i, "offerTitle": f"Oferta {i}", "offerPrice": 10.0, "offerSlug": f"o-{i}", "offerPublished": "2026-11-21T10:00:00-0300"} for i in ids]
        dados = {"props": {"pageProps": {"serverOffers": {"offers": ofertas, "after": after}}}}
        return f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(dados)}</script>'

    def test_segue_o_cursor_ate_o_numero_de_paginas_e_nao_repete(self):
        from radar.fontes import promobit
        chamadas = []
        paginas = {"": self.pagina(range(1, 13), "C1"), "C1": self.pagina(range(13, 25), "C2"), "C2": self.pagina(range(25, 37), "C3"),
                   "C3": self.pagina(range(37, 49), "C4")}

        def baixar(url):
            chamadas.append(url)
            return paginas[url.split("after=")[1] if "after=" in url else ""]

        r = promobit.coletar({"paginas_recentes": 3, "lojas": []}, baixar)
        self.assertEqual(len(r), 36)  # 3 paginas x 12, todas diferentes
        self.assertEqual([c.split("promocoes/")[1] for c in chamadas], ["recentes/", "recentes/?after=C1", "recentes/?after=C2"])
        self.assertFalse(any("page=" in c for c in chamadas))  # nunca ?page=N

    def test_para_quando_o_cursor_acaba_ou_a_pagina_nao_traz_nada_novo(self):
        from radar.fontes import promobit
        n = []
        mesma = self.pagina(range(1, 13), "C1")

        def baixar(url):
            n.append(url)
            return mesma  # servidor ignora o cursor e devolve a mesma pagina: nao pode entrar em laco

        self.assertEqual(len(promobit.coletar({"paginas_recentes": 5, "lojas": []}, baixar)), 12)
        self.assertEqual(len(n), 2)

    def test_cobertura_e_o_buraco_sao_medidos_em_minutos(self):
        from radar import qualidade
        from radar.modelos import Oferta
        agora = dt.datetime(2026, 11, 21, 10, 10)
        itens = [Oferta(fonte="promobit", canal="recentes-p1", id_externo="a", titulo="x", publicado_em="2026-11-21 10:01"),
                 Oferta(fonte="promobit", canal="loja-amazon", id_externo="b", titulo="y", publicado_em="2026-11-19 10:00")]  # loja: antiga, ignorada
        self.assertEqual(qualidade.cobertura_min(itens, agora), 9.0)


def card(did, titulo, loja, preco, idade, inativo="false"):
    return (f'<article data-deal-id="{did}" data-inactive="{inativo}" data-share-title="{titulo}" data-temperature-level="normal">'
            f'<h2>{titulo}</h2><span>{idade}</span><div>Vendido por</div><div>{loja}</div><div>R$</div><div>{preco}</div>'
            f'<div>Vendido por</div><div>{loja}</div><div>20°</div></article><button data-deal-id="{did}"></button>')


def pagina(*cards, partes=None):
    ld = {"@context": "https://schema.org", "@type": "WebPage", "mainEntity": {"@type": "ItemList", "hasPart": partes or []}}
    return f'<script type="application/ld+json">{json.dumps(ld)}</script>' + "".join(cards)


class PelandoTest(unittest.TestCase):
    def test_card_vira_oferta_com_url_loja_preco_e_hora(self):
        html = pagina(card("id1", "Robô Aspirador Dreame F10", "Amazon", "1.102", "há 5 min"),
                      partes=[{"url": "https://www.pelando.com.br/d/dreame-f10-aaaa", "name": "Robô Aspirador Dreame F10"}])
        o = pelando.parse_pagina(html, AGORA)[0]
        self.assertEqual((o.id_externo, o.loja, o.preco_anunciado, o.url), ("id1", "Amazon", 1102.0, "https://www.pelando.com.br/d/dreame-f10-aaaa"))
        self.assertEqual(o.publicado_em, "2026-11-21 10:25")

    def test_agora_horas_e_dias(self):
        for txt, esperado in (("agora", "2026-11-21 10:30"), ("há 2 h", "2026-11-21 08:30"), ("3 d", "2026-11-18 10:30")):
            o = pelando.parse_pagina(pagina(card("a", "Produto X", "Loja", "10", txt)), AGORA)[0]
            self.assertEqual(o.publicado_em, esperado, txt)

    def test_inativa_na_fonte_e_ignorada_e_cupom_nao_vira_preco(self):
        html = pagina(card("a", "Produto Velho", "Loja", "10", "agora", inativo="true"),
                      card("b", "Cupom Pague Menos - R$40 OFF acima de R$350", "Pague Menos", "40", "agora"))
        r = pelando.parse_pagina(html, AGORA)
        self.assertEqual([o.id_externo for o in r], ["b"])
        self.assertEqual((r[0].preco_anunciado, r[0].extras["tipo"]), (None, "cupom_loja"))

    def test_guid_com_digitos_e_d_nao_vira_idade_em_dias(self):
        """Regressao real de 21/11/2026: GUID 'fd0d8a59-894d-...' fazia um item de 4 min parecer ter 894 dias."""
        guid = "fd0d8a59-894d-436b-aaa5-3855a2bf85b7"
        o = pelando.parse_pagina(pagina(card(guid, "Kit Limpa Telas 100ml Rodabrill", "Amazon", "10,90", "4 min")), AGORA)[0]
        self.assertEqual(o.publicado_em, "2026-11-21 10:26")
        # mesmo sem idade no card, o GUID sozinho nunca pode produzir uma hora
        sem_idade = pelando.parse_pagina(pagina(card(guid, "Produto X", "Loja", "10", "")), AGORA)[0]
        self.assertIsNone(sem_idade.publicado_em)

    def test_preco_com_centavos(self):
        o = pelando.parse_pagina(pagina(card("a", "Produto", "Loja", "23,65", "agora")), AGORA)[0]
        self.assertEqual(o.preco_anunciado, 23.65)

    def test_bloqueio_do_waf_vira_erro_explicito_sem_tentar_contornar(self):
        with self.assertRaises(FonteErro) as cm:
            pelando.parse_pagina("<html>Sorry, you have been blocked. You are unable to access pelando.com.br</html>", AGORA)
        self.assertIn("bloqueou", str(cm.exception))

    def test_layout_mudou(self):
        with self.assertRaises(FonteErro):
            pelando.parse_pagina("<html><body>sem cards</body></html>", AGORA)


if __name__ == "__main__":
    unittest.main()
