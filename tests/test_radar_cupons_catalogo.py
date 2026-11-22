"""Motor de cupons e identificacao de produtos (casos reais citados no pedido + armadilhas conhecidas)."""

import datetime as dt
import unittest

from radar import catalogo, cupons
from radar.cupons import EXPIRADO, NAO_CONFIRMADO, PROVAVEL, VALIDADO

AGORA = dt.datetime(2026, 11, 20, 18, 0)


def um(texto, **kw):
    achados = cupons.extrair_cupons(texto, agora=AGORA, **kw)
    assert len(achados) == 1, [c.codigo for c in achados]
    return achados[0]


class ExtracaoCuponsTest(unittest.TestCase):
    def test_percentual_simples_casatech10(self):
        c = um("Use o cupom CASATECH10 e ganhe 10% de desconto no Robô K800 Pro na KaBuM")
        self.assertEqual((c.codigo, c.tipo, c.valor), ("CASATECH10", "percentual", 10.0))
        self.assertFalse(c.valor_inferido)

    def test_fixo_com_minimo_e_restricoes_70off(self):
        c = um("Cupom 70OFF: R$ 70 de desconto em compras acima de R$ 1.000, só na primeira compra pelo app")
        self.assertEqual((c.codigo, c.tipo, c.valor, c.minimo), ("70OFF", "fixo", 70.0, 1000.0))
        self.assertIn("primeira_compra", c.restricoes)
        self.assertIn("app", c.restricoes)

    def test_codigo_sozinho_nao_vira_valor_confirmado(self):
        c = um("cupom 70OFF")
        self.assertTrue(c.valor_inferido)
        self.assertEqual(c.valor, 70.0)  # e so uma pista
        r = cupons.calcular_preco_final(1200.0, 0.0, cupons.avaliar_status(c, "funcionando", "2026-11-20 17:30", agora=AGORA))
        self.assertFalse(r["cupom_aplicado"])  # pista nao entra em calculo
        self.assertIn("nao confirmado", r["motivo"])

    def test_primeira_compra_primeira20bf(self):
        c = um("Cupom PRIMEIRA20BF dá 20% off somente na primeira compra")
        self.assertEqual(c.codigo, "PRIMEIRA20BF")
        self.assertIn("primeira_compra", c.restricoes)
        c = cupons.avaliar_status(c, "funcionando", "2026-11-20 17:50", agora=AGORA)
        r = cupons.calcular_preco_final(1000.0, 0.0, c, {"primeira_compra": False, "usa_app": False, "paga_no_pix": True})
        self.assertFalse(r["cupom_aplicado"])
        self.assertIs(r["elegivel"], False)
        r2 = cupons.calcular_preco_final(1000.0, 0.0, c, {"primeira_compra": True})
        self.assertTrue(r2["cupom_aplicado"])
        self.assertEqual(r2["preco_final"], 800.0)

    def test_cupom_condicionado_25primebf_vendedor_especifico_nao_aplica(self):
        c = um("Cupom 25PRIMEBF: 25% off em itens vendidos e entregues pela Amazon")
        self.assertIn("vendedor_especifico", c.restricoes)
        c = cupons.avaliar_status(c, "funcionando", "2026-11-20 17:50", agora=AGORA)
        r = cupons.calcular_preco_final(800.0, 0.0, c)
        self.assertIsNone(r["elegivel"])  # nao inventa elegibilidade
        self.assertFalse(r["cupom_aplicado"])

    def test_pix_e_cashback_e_frete(self):
        c = um("10% off no Pix com o cupom PIX10BF, frete grátis e 5% de cashback")
        self.assertIn("pix", c.restricoes)
        self.assertTrue(c.frete_gratis)
        self.assertEqual(c.cashback_pct, 5.0)

    def test_nao_acumulavel(self):
        c = um("Cupom BEMVINDO15: 15% de desconto, não cumulativo com outras promoções")
        self.assertIs(c.acumulavel, False)

    def test_teto_do_desconto(self):
        c = um("Cupom AMAZON15X dá 15% de desconto, limitado a R$ 150 de desconto, compras acima de R$ 500")
        self.assertEqual((c.valor, c.teto, c.minimo), (15.0, 150.0, 500.0))
        c = cupons.avaliar_status(c, "funcionando", "2026-11-20 17:50", agora=AGORA)
        r = cupons.calcular_preco_final(2000.0, 0.0, c)
        self.assertEqual(r["desconto_aplicado"], 150.0)  # 15% de 2000 = 300, mas o teto e 150
        self.assertEqual(r["preco_final"], 1850.0)

    def test_validade(self):
        c = um("Cupom FRIDAY25 válido até 27/11 às 23h")
        self.assertEqual(c.validade, "2026-11-27 23:00")

    def test_placeholders_e_palavras_comuns_nao_sao_codigo(self):
        for txt in (
            "ACESSEEGANHE no app", "Aplique no link APLIQUENOLINK", "cupom funcionando agora",
            "Cupom Amazon com frete grátis", "RESGATENOLINK", "use o cupom no app",
        ):
            self.assertEqual(cupons.extrair_cupons(txt, agora=AGORA), [], txt)

    def test_varios_cupons_na_mesma_publicacao(self):
        achados = cupons.extrair_cupons(
            "Cupons: CASATECH10 (10% off) e 20TAONOROBO (R$ 20 de desconto)", agora=AGORA
        )
        self.assertEqual({c.codigo for c in achados}, {"CASATECH10", "20TAONOROBO"})


class ElegibilidadePrecedenciaTest(unittest.TestCase):
    """Cupom REAL do Meliuz (25PRIMEBF): primeira compra + app + 'clientes selecionados'."""

    TEXTO = ("Exclusivo Prime: todo o site com R$25 OFF. Apenas para clientes selecionados que estão realizando a primeira compra "
             "na Amazon via aplicativo. Aplicável em compras a partir de R$40.")

    def test_restricao_impeditiva_conhecida_vence_a_incerteza_de_selecao(self):
        c = cupons.interpretar_regra(self.TEXTO, loja="amazon", codigo="25PRIMEBF")
        self.assertIn("selecionados", c.restricoes)
        eleg, motivo = cupons.elegibilidade(c, {"primeira_compra": False, "usa_app": False, "paga_no_pix": True})
        self.assertIs(eleg, False)
        self.assertIn("primeira compra", motivo)

    def test_se_o_perfil_atende_as_restricoes_conhecidas_sobra_a_incerteza(self):
        c = cupons.interpretar_regra(self.TEXTO, loja="amazon", codigo="25PRIMEBF")
        eleg, _ = cupons.elegibilidade(c, {"primeira_compra": True, "usa_app": True, "paga_no_pix": True})
        self.assertIsNone(eleg)


class StatusCupomTest(unittest.TestCase):
    def _c(self):
        return um("cupom CASATECH10 10% de desconto")

    def test_publicacao_antiga_sem_confirmacao_e_nao_confirmado(self):
        c = cupons.avaliar_status(self._c(), "ótimo cupom", "2026-11-19 10:00", agora=AGORA)
        self.assertEqual(c.status, NAO_CONFIRMADO)

    def test_recente_com_relato_de_funcionamento_e_provavel_nunca_validado(self):
        c = cupons.avaliar_status(self._c(), "funcionando, consegui aplicar", "2026-11-20 17:00", agora=AGORA)
        self.assertEqual(c.status, PROVAVEL)
        self.assertNotEqual(c.status, VALIDADO)

    def test_verificado_pela_fonte_recentemente_e_provavel(self):
        c = cupons.avaliar_status(self._c(), "", None, verificado_em="2026-11-20 15:30", agora=AGORA)
        self.assertEqual(c.status, PROVAVEL)

    def test_comentarios_de_expirado_vencem(self):
        c = cupons.avaliar_status(self._c(), "expirou, não funciona mais", "2026-11-20 17:50", agora=AGORA)
        self.assertEqual(c.status, EXPIRADO)

    def test_validade_vencida_expira(self):
        c = um("cupom FRIDAY25 25% off válido até 19/11")
        self.assertEqual(cupons.avaliar_status(c, "funcionando", "2026-11-20 17:50", agora=AGORA).status, EXPIRADO)

    def test_so_o_marcador_explicito_valida(self):
        c = cupons.marcar_validado(self._c(), "carrinho Amazon", agora=AGORA)
        self.assertEqual(c.status, VALIDADO)
        r = cupons.calcular_preco_final(1000.0, 0.0, c)
        self.assertEqual(r["preco_final"], 900.0)
        self.assertFalse(r["estimado"])

    def test_cupom_nao_confirmado_nao_entra_no_preco(self):
        r = cupons.calcular_preco_final(1000.0, 50.0, self._c())
        self.assertFalse(r["cupom_aplicado"])
        self.assertEqual(r["preco_final"], 1050.0)  # preco + frete, sem desconto


class PrecoFinalTest(unittest.TestCase):
    def test_formula_preco_menos_desconto_mais_frete(self):
        c = cupons.marcar_validado(um("cupom CASATECH10 10% de desconto"), "teste", AGORA)
        r = cupons.calcular_preco_final(1199.99, 25.0, c)
        self.assertEqual(r["desconto_aplicado"], 120.0)
        self.assertEqual(r["preco_final"], round(1199.99 - 120.0 + 25.0, 2))

    def test_compra_minima_nao_atingida(self):
        c = cupons.marcar_validado(um("cupom 70OFF R$ 70 de desconto em compras acima de R$ 1.000"), "teste", AGORA)
        r = cupons.calcular_preco_final(850.0, 0.0, c)
        self.assertFalse(r["cupom_aplicado"])
        self.assertIn("minima", r["motivo"])

    def test_escolhe_um_unico_cupom_sem_somar(self):
        a = cupons.marcar_validado(um("cupom AAAA10 10% de desconto"), "t", AGORA)
        b = cupons.marcar_validado(um("cupom BBBB20 20% de desconto"), "t", AGORA)
        escolhido, r = cupons.melhor_cupom(1000.0, 0.0, [a, b])
        self.assertEqual(escolhido.codigo, "BBBB20")
        self.assertEqual(r["preco_final"], 800.0)  # nao 700


class CatalogoTest(unittest.TestCase):
    def setUp(self):
        self.cat = catalogo.carregar()

    def id(self, texto):
        c = catalogo.identificar(texto, self.cat)
        return c.produto_id if c else None

    def test_robos_do_catalogo(self):
        casos = {
            "Robô Aspirador KaBuM Smart K800 Pro Mapeamento a Laser 127V Preto": "k800_pro_127v",
            "Robô Aspirador Dreame F10 com Mop": "dreame_f10",
            "Robô Aspirador TP-Link Tapo RV20 Max": "tapo_rv20_max",
            "Robô Aspirador Xiaomi Robot Vacuum S40C": "xiaomi_s40c",
            "Xiaomi Robot Vacuum S40 Pro OV71GL": "xiaomi_s40_pro_py",
        }
        for texto, esperado in casos.items():
            self.assertEqual(self.id(texto), esperado, texto)

    def test_nunca_mistura_127v_com_220v(self):
        self.assertIsNone(self.id("Robô Aspirador KaBuM K800 Pro 220V"))
        self.assertEqual(self.id("Robô KaBuM K800 Pro 127V"), "k800_pro_127v")
        amb = catalogo.identificar("Robô KaBuM K800 Pro bivolt 127V/220V", self.cat)
        self.assertIn("tensao_ambigua", amb.avisos)

    def test_variantes_nao_se_confundem(self):
        for texto in ("Tapo RV20 Mop", "TP-Link Tapo RV30 Plus", "Xiaomi Robot Vacuum S40", "Dreame F10 Pro", "Dreame L10 Ultra"):
            self.assertIsNone(self.id(texto), texto)

    def test_s40c_nao_vira_s40_pro_e_vice_versa(self):
        self.assertEqual(self.id("Xiaomi S40C"), "xiaomi_s40c")
        self.assertEqual(self.id("Xiaomi S40 Pro"), "xiaomi_s40_pro_py")

    def test_ares_por_sku_e_por_nome(self):
        casos = {
            "Ar Condicionado Split Inverter Elgin Eco Inverter III 12000 BTU Frio 220V HJFC12C2WGCG": "elgin_12k",
            "Split Elgin Eco Inverter III 18.000 BTUs Frio 220V": "elgin_18k",
            "Agratto Kyn Top 12.000 BTU KNICST12F-02": "agratto_12k",
            "Midea AirVolution Lite 12000 BTU 42EBVCB12M5": "midea_lite_12k",
            "Midea AI Ecomaster 12000 BTU": "midea_ecomaster_12k",
            "Philco Eco Inverter 18000 BTU PAC18FTW": "philco_18k",
        }
        for texto, esperado in casos.items():
            self.assertEqual(self.id(texto), esperado, texto)

    def test_btu_errado_e_quente_frio_sao_recusados(self):
        self.assertIsNone(self.id("Elgin Eco Inverter III 18.000 BTU HJFC12C2WGCG"))  # sku de 12k com 18k no titulo
        self.assertIsNone(self.id("Elgin Eco Inverter III 12000 BTU Quente e Frio"))
        self.assertIsNone(self.id("Midea AirVolution Lite 12000 BTU 127V"))  # produto e 220V

    def test_chuveiro(self):
        self.assertEqual(self.id("Chuveiro Lorenzetti Loren Shower Eletrônico 6800W 220V"), "loren_shower_6800_220v")
        self.assertIsNone(self.id("Chuveiro Loren Shower Multitemperaturas 7500W 220V"))
        self.assertIsNone(self.id("Chuveiro Loren Shower Eletrônico 6800W 127V"))

    def test_acessorio_nao_e_produto_completo(self):
        self.assertIsNone(self.id("Filtro HEPA para Dreame F10"))
        self.assertIsNone(self.id("Escova lateral compatível com Xiaomi S40C"))

    def test_aviso_de_importado_para_produto_nacional(self):
        c = catalogo.identificar("Dreame F10 versão global importado", self.cat)
        self.assertIn("possivel_importado", c.avisos)

    def test_todo_produto_do_catalogo_mapeia_para_chave_de_rastreador(self):
        for pid, p in self.cat["produtos"].items():
            self.assertEqual(p["chave_rastreador"], pid)


if __name__ == "__main__":
    unittest.main()
