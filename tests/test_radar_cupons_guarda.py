"""Regras estritas de cupom: economia hipotetica NUNCA vira preco garantido nem alerta. BLACK150 continua NAO_CONFIRMADO."""

import ast
import copy
import datetime as dt
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from radar import catalogo, cruzamento as cz, cupons, db, ranking, varredura
from radar.modelos import Oferta

from tests.test_radar_cruzamento import CAT, PERFIL, PRECOS, cupom_loja

AGORA = dt.datetime(2026, 11, 21, 12, 0)
RADAR = Path(__file__).resolve().parents[1] / "radar"
TEXTO_BLACK150 = ("Sua compra com R$150 de desconto Amazon válido. R$150 de desconto em compras acima de R$1.499. "
                  "Aplique o cupom na página do produto. Válido enquanto durar.")


class IsolamentoDoCaminhoDeAlertaTest(unittest.TestCase):
    def test_cruzamento_e_equivalentes_sao_so_informativos(self):
        """Quem decide alerta (varredura, alertas, prioridade, outbox, ciclo, ranking, historico) nao pode importar o cruzamento
        (economia ESTIMADA com cupom de loja) nem os equivalentes (produtos parecidos)."""
        for nome in ("varredura", "alertas", "prioridade", "outbox", "ciclo", "ranking", "historico", "recuperacao"):
            arvore = ast.parse((RADAR / f"{nome}.py").read_text(encoding="utf-8"))
            importados = set()
            for no in ast.walk(arvore):
                if isinstance(no, ast.ImportFrom):
                    importados |= {a.name for a in no.names} | ({no.module} if no.module else set())
                elif isinstance(no, ast.Import):
                    importados |= {a.name for a in no.names}
            self.assertFalse({"cruzamento", "equivalentes"} & {i.split(".")[-1] for i in importados}, nome)


class BlackCentoECinquentaTest(unittest.TestCase):
    def test_sai_do_cruzamento_como_candidato_a_teste_nunca_confirmado(self):
        res = cz.cruzar([cupom_loja("amazon", "amazon: Sua compra com R$150 de desconto", TEXTO_BLACK150, "BLACK150")], PRECOS, CAT, PERFIL, AGORA)
        self.assertTrue(res)
        self.assertTrue(all(r["confirmado"] is False for r in res))
        self.assertTrue(all(r["status_cupom"] == cupons.NAO_CONFIRMADO for r in res))
        cand = [r for r in res if r["aplicabilidade"] == cz.CANDIDATO]
        self.assertTrue(cand)
        self.assertTrue(all("nada confirmado" in r["motivo"] for r in cand))

    def test_resultado_do_cruzamento_nunca_afirma_confirmacao_em_nenhum_caso(self):
        ofertas = [
            cupom_loja("amazon", "amazon: R$150 OFF", TEXTO_BLACK150, "BLACK150"),
            cupom_loja("amazon", "Cupom Amazon de até 50% de desconto", "até 50% de desconto", "CUPONSBF"),
            cupom_loja("kabum", "KaBuM!: R$ 300 de Desconto em produtos KaBuM!"),
            cupom_loja("amazon", "10% de desconto garantido", "10% de desconto garantido", "X10", fonte="gatry"),
        ]
        for r in cz.cruzar(ofertas, PRECOS, CAT, PERFIL, AGORA):
            self.assertIs(r["confirmado"], False)
            self.assertNotEqual(r["status_cupom"], cupons.VALIDADO)  # so `radar validar` (manual) chega a VALIDADO

    def test_cupom_nao_confirmado_nao_desconta_do_preco_final(self):
        c = cupons.interpretar_regra(TEXTO_BLACK150, loja="amazon", codigo="BLACK150", agora=AGORA)
        cupons.avaliar_status(c, TEXTO_BLACK150, "2026-11-21 11:50", None, AGORA)  # publicado agora, sem comentario de funcionamento
        self.assertEqual(c.status, cupons.NAO_CONFIRMADO)
        r = cupons.calcular_preco_final(1844.05 + 150.0, 0.0, c)
        self.assertFalse(r["cupom_aplicado"])
        self.assertEqual(r["preco_final"], 1994.05)
        self.assertIn("nao aplicado", r["motivo"])


class EstagiosDoCupomTest(unittest.TestCase):
    """Descoberto, potencialmente elegivel, validado e expirado nunca se misturam."""

    def cruzar(self, *ofs):
        return cz.cruzar(list(ofs), PRECOS, CAT, PERFIL, AGORA)

    def test_black150_para_em_potencialmente_elegivel(self):
        res = self.cruzar(cupom_loja("amazon", "amazon: R$150 OFF", TEXTO_BLACK150, "BLACK150"))
        cand = [r for r in res if r["aplicabilidade"] == cz.CANDIDATO]
        self.assertTrue(cand)
        self.assertEqual({r["estagio"] for r in cand}, {"potencialmente_elegivel"})
        self.assertFalse([r for r in res if r["estagio"] == "validado"])
        self.assertTrue(all(r["confirmado"] is False for r in res))

    def test_so_a_validacao_manual_leva_ao_estagio_validado(self):
        of = cupom_loja("amazon", "amazon: R$150 OFF", TEXTO_BLACK150, "BLACK150")
        c = cupons.interpretar_regra(f"{of.titulo}. {of.texto}", loja="amazon", codigo="BLACK150", agora=AGORA)
        cupons.avaliar_status(c, of.texto, of.publicado_em, of.verificado_em, AGORA)
        par = lambda: cz.avaliar_par(of, c, "dreame_f10", CAT["produtos"]["dreame_f10"], PRECOS["dreame_f10"][0], 1994.05, PERFIL, AGORA)
        self.assertEqual(par()["estagio"], "potencialmente_elegivel")
        cupons.marcar_validado(c, "carrinho Amazon (simulado em teste)", AGORA)
        self.assertEqual(par()["estagio"], "validado")

    def test_expirado_e_descoberto(self):
        exp = self.cruzar(cupom_loja("amazon", "amazon: cupom expirado", "R$150 de desconto. Cupom expirado, nao funciona mais.", "VELHO150"))
        self.assertTrue(exp and all(r["estagio"] == "expirado" for r in exp))
        sem_codigo = self.cruzar(cupom_loja("kabum", "KaBuM!: R$ 300 de Desconto em produtos KaBuM!"))
        self.assertTrue(sem_codigo and all(r["estagio"] == "descoberto" for r in sem_codigo))

    def test_codigo_que_denuncia_outra_categoria_nao_e_potencialmente_elegivel(self):
        """Achado ao vivo em 21/11/2026: `100IMPRESSORA` (KaBuM, R$100) saia como candidato para robo aspirador."""
        res = self.cruzar(cupom_loja("kabum", "kabum: Compre com cupom KaBuM! e ganhe R$100 de desconto + 1% cashback",
                                     "Compre com cupom KaBuM! e ganhe R$100 de desconto + 1% cashback", "100IMPRESSORA"))
        self.assertTrue(res)
        self.assertEqual({r["estagio"] for r in res}, {"descoberto"})
        self.assertTrue(all("sugere outra categoria" in r["motivo"] for r in res))

    def test_codigos_de_casa_e_eletro_nao_sao_barrados_pela_heuristica(self):
        for cod in ("BLACK150", "ASPIRADOR100", "CASA50", "ELETRO20", "KABUM100"):
            self.assertIsNone(cz.CODIGO_SUGESTIVO.search(cod), cod)

    def test_resumo_conta_os_estagios(self):
        res = self.cruzar(cupom_loja("amazon", "amazon: R$150 OFF", TEXTO_BLACK150, "BLACK150"), cupom_loja("kabum", "KaBuM!: R$ 300 de Desconto em produtos KaBuM!"))
        rs = cz.resumo(res)
        self.assertEqual(sum(rs["estagios"].values()), rs["pares_cupom_produto"])
        self.assertGreater(rs["estagios"]["potencialmente_elegivel"], 0)
        self.assertEqual(rs["estagios"]["validado"], 0)


class CupomDeLojaNaoGeraAlertaTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        p = mock.patch.dict(os.environ, {"CENTRAL_COMPRAS_DADOS_PRIVADOS": self._tmp.name})
        p.start()
        self.con = db.abrir()
        self.addCleanup(self._tmp.cleanup)
        self.addCleanup(self.con.close)
        self.addCleanup(p.stop)
        self.regras = copy.deepcopy(ranking.carregar_regras())
        self.regras["alertas"].update(enviar=True, homologado_em="2026-11-21 09:00")  # mesmo LIGADO, cupom de loja nao vira alerta

    def _candidatos(self):
        return self.con.execute("SELECT COUNT(*) FROM candidatos_alerta").fetchone()[0]

    def test_cupom_de_loja_sem_produto_nao_vira_candidato_nem_envio(self):
        of = cupom_loja("amazon", "amazon: Sua compra com R$150 de desconto", TEXTO_BLACK150, "BLACK150", publicado_em="2026-11-21 11:55")
        caixa = mock.Mock(return_value=(True, "ok"))
        r = varredura.processar_oferta(self.con, of, catalogo.carregar(), self.regras, caixa, AGORA, diferir=True)
        self.assertEqual(self._candidatos(), 0)
        caixa.assert_not_called()
        self.assertNotIn("candidato", str(r.get("acao")))

    def test_oferta_de_produto_com_cupom_nao_confirmado_nao_conta_a_economia_do_cupom(self):
        texto = f"Robô Aspirador KaBuM Smart K800 Pro 127V Preto KSAR81010PT R$ 1.844,05 com cupom BLACK150. {TEXTO_BLACK150}"
        of = Oferta(fonte="promobit", canal="recentes-p1", id_externo="77", titulo="Robô Aspirador KaBuM Smart K800 Pro 127V Preto KSAR81010PT",
                    texto=texto, loja="Amazon", preco_anunciado=1844.05, cupom_codigo="BLACK150", publicado_em="2026-11-21 11:55")
        varredura.processar_oferta(self.con, of, catalogo.carregar(), self.regras, None, AGORA, diferir=True)
        linha = self.con.execute("SELECT preco_anunciado, preco_final, status_cupom FROM ofertas WHERE id_externo='77'").fetchone()
        self.assertIsNotNone(linha)
        self.assertEqual(linha["status_cupom"], cupons.NAO_CONFIRMADO)
        self.assertEqual(linha["preco_final"], linha["preco_anunciado"])  # nenhum desconto do cupom foi contado
        for c in self.con.execute("SELECT mensagem FROM candidatos_alerta"):
            self.assertNotIn("garantido", c["mensagem"].lower())


if __name__ == "__main__":
    unittest.main()
