"""Cruzamento cupom de loja x produto. Os textos sao cupons REAIS lidos em 21/11/2026 (Meliuz, Promobit, Pelando, Gatry)."""

import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

from radar import catalogo, cruzamento as cz, cupons
from radar.modelos import Oferta

AGORA = dt.datetime(2026, 11, 21, 12, 0)
CAT = catalogo.carregar()
PRECOS = {
    "dreame_f10": [{"loja": "amazon", "preco": 1994.05, "vendedor": "DREAME LTDA"}],
    "elgin_12k": [{"loja": "amazon", "preco": 1865.60, "vendedor": "Refricril"}, {"loja": "kabum", "preco": 2299.00, "vendedor": "Engage"}],
    "tapo_rv20_max": [{"loja": "amazon", "preco": 854.05, "vendedor": "TNTinfoLoja"}],
    "xiaomi_s40c": [{"loja": "magalu", "preco": 1173.14, "vendedor": "Magazine Luiza"}],
}
PERFIL = {"primeira_compra": False, "usa_app": False, "paga_no_pix": True}


def cupom_loja(loja, titulo, texto="", codigo=None, fonte="meliuz", **kw):
    return Oferta(fonte=fonte, canal=f"cupom_loja:{loja}", id_externo=f"{loja}:{codigo or titulo[:12]}", titulo=titulo, texto=texto or titulo,
                  cupom_codigo=codigo, loja=loja, extras={"tipo": "cupom_loja"}, **kw)


def cruzar(*ofertas, precos=None):
    return cz.cruzar(list(ofertas), precos or PRECOS, CAT, PERFIL, AGORA)


def por(res, produto, loja=None):
    return [r for r in res if r["produto"] == produto and (loja is None or r["loja"] == loja)]


class InterpretacaoTest(unittest.TestCase):
    def test_regras_sem_codigo_e_teto_da_campanha(self):
        c = cupons.interpretar_regra("KaBuM!: R$ 300 de Desconto em produtos KaBuM!")
        self.assertEqual((c.tipo, c.valor, c.codigo), ("fixo", 300.0, None))
        c = cupons.interpretar_regra("Cupom Amazon de até 50% de desconto na Black dos Sonhos", codigo="CUPONSBF")
        self.assertTrue(c.valor_maximo)
        c = cupons.interpretar_regra("Ganhe até R$1.000 OFF em eletrônicos no cupom Amazon", codigo="DEVOLTA1000")
        self.assertTrue(c.valor_maximo)
        c = cupons.interpretar_regra("10% de desconto garantido", codigo="X10")
        self.assertFalse(c.valor_maximo)

    def test_valor_maximo_nunca_entra_no_preco_final(self):
        c = cupons.interpretar_regra("Cupom Amazon de até 50% de desconto", codigo="CUPONSBF")
        cupons.marcar_validado(c, "teste", AGORA)  # mesmo validado, "ate 50%" e so o teto
        r = cupons.calcular_preco_final(1000.0, 0.0, c)
        self.assertFalse(r["cupom_aplicado"])
        self.assertIn("TETO", r["motivo"])


class CuponsReaisTest(unittest.TestCase):
    def test_black150_unico_irrestrito_vira_candidato_e_respeita_o_minimo(self):
        of = cupom_loja("amazon", "amazon: Sua compra com R$150 de desconto Amazon válido (R$ 150)",
                        "Sua compra com R$150 de desconto Amazon válido. R$150 de desconto em compras acima de R$1.499. Aplique o cupom na página do produto. Válido enquanto durar.",
                        "BLACK150")
        res = cruzar(of)
        d = por(res, "dreame_f10", "amazon")[0]
        self.assertEqual(d["aplicabilidade"], cz.CANDIDATO)
        self.assertEqual((d["preco_com_cupom_estimado"], d["economia_estimada"], d["melhor_que_atual"]), (1844.05, 150.0, True))
        self.assertFalse(d["confirmado"])
        self.assertEqual(d["status_cupom"], cupons.NAO_CONFIRMADO)  # elegivel/candidato nao e confirmacao
        t = por(res, "tapo_rv20_max", "amazon")[0]
        self.assertEqual(t["aplicabilidade"], cz.INAPLICAVEL)  # R$ 854 < minimo de R$ 1.499
        self.assertIn("minima", t["motivo"])
        self.assertEqual(por(res, "elgin_12k", "kabum"), [])  # loja do cupom != loja do preco

    def test_cartao_generico_do_promobit_sem_regra_e_indeterminado_nunca_candidato(self):
        res = cruzar(cupom_loja("Amazon", "Amazon: 20% de Desconto em produtos Amazon", fonte="promobit"))
        self.assertTrue(res)
        self.assertEqual({r["aplicabilidade"] for r in res}, {cz.INDETERMINADO})

    def test_primeira_compra_e_app_sao_inaplicaveis(self):
        of = cupom_loja("amazon", "amazon: Exclusivo Prime: todo o site com R$25 OFF (R$ 25)",
                        "Exclusivo Prime: todo o site com R$25 OFF. Apenas para clientes selecionados que estão realizando a primeira compra na Amazon via aplicativo. Aplicável em compras a partir de R$40.",
                        "25PRIMEBF")
        self.assertEqual({r["aplicabilidade"] for r in cruzar(of)}, {cz.INAPLICAVEL})

    def test_iphone_jogos_notebooks_sao_outra_categoria(self):
        casos = [("amazon", "amazon: Ganhe até R$1.000 OFF em eletrônicos no cupom Amazon", "Válido para compra de Iphone 18, vendidos e entregues via Amazon.", "DEVOLTA1000"),
                 ("amazon", "amazon: GTA VI e outros jogos com 5% OFF", "GTA VI e outros jogos com 5% OFF. Seleção no link.", "PRIMEGAME5"),
                 ("amazon", "amazon: Leve 2 bebidas alcoólicas e ganhe 20% OFF", "Compre 2 bebidas alcoólicas participantes pelo app.", "USEOLINK")]
        for loja, t, tx, cod in casos:
            res = cruzar(cupom_loja(loja, t, tx, cod))
            self.assertEqual({r["aplicabilidade"] for r in res}, {cz.INAPLICAVEL}, cod)

    def test_codigo_que_denuncia_a_categoria_e_indeterminado(self):
        of = cupom_loja("kabum", "kabum: Válido agora: cupom KaBuM! com R$200 de desconto + 1% cashback (R$ 200)",
                        "Válido agora: cupom KaBuM! com R$200 de desconto + 1% cashback.", "TV200")
        d = por(cruzar(of), "elgin_12k", "kabum")[0]
        self.assertEqual(d["aplicabilidade"], cz.INDETERMINADO)
        self.assertIn("TV200", d["motivo"])

    def test_percentual_alto_sem_teto_e_indeterminado_heuristica(self):
        of = cupom_loja("magalu", "magalu: Código Magazine Luiza oferece 30% de desconto + até 8% cashback", codigo="CUPOM30")
        d = por(cruzar(of), "xiaomi_s40c", "magalu")[0]
        self.assertEqual(d["aplicabilidade"], cz.INDETERMINADO)
        self.assertIn("heuristica", d["motivo"])

    def test_desconto_em_subconjunto_e_seletivo(self):
        of = cupom_loja("magalu", "magalu: Voucher Magazine Luiza com 5% de desconto em bikes elétricas + até 8% cashback", codigo="BIKEPOP")
        self.assertEqual({r["aplicabilidade"] for r in cruzar(of)}, {cz.INDETERMINADO})

    def test_ate_x_so_mostra_o_teto(self):
        of = cupom_loja("amazon", "amazon: Cupom Amazon de até 50% de desconto na Black dos Sonhos (50%)",
                        "Cupom Amazon de até 50% de desconto na Black dos Sonhos. Aproveite cupons Amazon de diversas categorias.", "CUPONSBF")
        d = por(cruzar(of), "dreame_f10", "amazon")[0]
        self.assertEqual(d["aplicabilidade"], cz.INDETERMINADO)
        self.assertIsNone(d["preco_com_cupom_estimado"])
        self.assertIsNotNone(d["teto_da_campanha"])

    def test_itens_selecionados_e_indeterminado(self):
        of = cupom_loja("kabum", "kabum: Cupom KaBuM! rende R$100 de economia + 1% cashback (R$100)",
                        "Cupom KaBuM! rende R$100 de economia pra você. Economize em itens selecionados aplicando o cupom ao finalizar a compra.", "LU100")
        self.assertEqual({r["aplicabilidade"] for r in cruzar(of)}, {cz.INDETERMINADO})

    def test_expirado_e_inaplicavel(self):
        of = cupom_loja("amazon", "amazon: R$ 150 de desconto", "R$150 de desconto em compras acima de R$1.499. Expirou, não funciona mais.", "OLD150")
        self.assertEqual({r["aplicabilidade"] for r in cruzar(of)}, {cz.INAPLICAVEL})

    def test_cupom_repetido_em_duas_fontes_gera_um_par_so(self):
        a = cupom_loja("amazon", "amazon: Sua compra com R$150 de desconto", "R$150 de desconto em compras acima de R$1.499. Aplique o cupom.", "BLACK150")
        b = cupom_loja("amazon", "amazon: Sua compra com R$150 de desconto", "R$150 de desconto em compras acima de R$1.499. Aplique o cupom.", "BLACK150", fonte="gatry")
        self.assertEqual(len(por(cruzar(a, b), "dreame_f10", "amazon")), 1)

    def test_vendedor_terceiro_barra_cupom_de_vendido_pela_loja(self):
        of = cupom_loja("amazon", "amazon: 10% OFF", "10% OFF em produtos vendidos e entregues pela Amazon. Aplique o cupom.", "AMZ10")
        d = por(cruzar(of), "dreame_f10", "amazon")[0]  # preco monitorado e do vendedor DREAME LTDA
        self.assertEqual(d["aplicabilidade"], cz.INAPLICAVEL)

    def test_resumo_separa_candidatos_e_oportunidades(self):
        a = cupom_loja("amazon", "amazon: Sua compra com R$150 de desconto", "R$150 de desconto em compras acima de R$1.499. Aplique o cupom.", "BLACK150")
        rs = cz.resumo(cruzar(a))
        self.assertEqual(rs[cz.CANDIDATO], 2)  # dreame (1994) e elgin_12k (1865) na Amazon; tapo (854) nao atinge o minimo
        self.assertEqual(len(rs["oportunidades"]), 2)

    def test_so_cupom_de_loja_entra_publicacao_de_produto_nao(self):
        prod = Oferta(fonte="promobit", canal="recentes", id_externo="1", titulo="Robô Dreame F10", loja="Amazon", preco_anunciado=1100.0)
        self.assertEqual(cruzar(prod), [])


class PrecosAtuaisTest(unittest.TestCase):
    def test_extrai_preco_por_loja_do_estado(self):
        estado = {"modelos": {"elgin_12k": {"amazon": {"preco": 1865.6, "total": 1865.6, "vendedor": "Refricril"},
                                            "kabum": {"preco_pix": 2299, "vendedor": "Engage"}, "frigelar": {"total": None},
                                            "zoom": {"menor_preco": 898.0, "loja": "Magazine Luiza"}}}}
        r = {p["loja"]: p["preco"] for p in cz.precos_por_loja(estado)["elgin_12k"]}
        self.assertEqual(r, {"amazon": 1865.6, "kabum": 2299.0, "magalu": 898.0})

    def test_usa_a_ultima_coleta_boa_e_a_correcao_versionada(self):
        with tempfile.TemporaryDirectory() as tmp:
            pasta = Path(tmp) / "rastreador-chuveiro"
            pasta.mkdir()
            boa = {"coletado_em": "2026-11-20 08:03", "modelos": {"loren_shower_6800_220v": {"melhor_preco": 60.65, "leroy": {"total": 60.65}, "amazon": {"total": 122.45}}}}
            ruim = {"coletado_em": "2026-11-20 14:44", "modelos": {"loren_shower_6800_220v": {"melhor_preco": None, "amazon": {"erro": "Timeout 25000ms", "total": None},
                                                                                              "leroy": {"erro": "Timeout 25000ms", "total": None}, "zoom": {"erro": "Timeout", "menor_preco": None}}}}
            (pasta / "historico.jsonl").write_text("\n".join(json.dumps(x) for x in (boa, ruim)), encoding="utf-8")
            precos, datas = cz.carregar_precos_atuais(Path(tmp))
            self.assertEqual(datas["loren_shower_6800_220v"], "2026-11-20 08:03")  # a rodada ruim foi ignorada
            self.assertTrue(precos["loren_shower_6800_220v"])


if __name__ == "__main__":
    unittest.main()
