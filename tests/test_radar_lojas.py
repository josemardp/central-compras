"""Preco anunciado x confirmado x entregue (radar/lojas.py) e a regra: cupom embutido na oferta nunca e descontado de novo."""

import copy
import datetime as dt
import json
import os
import tempfile
import unittest
from unittest import mock

from radar import alertas, catalogo, db, lojas, ranking, varredura
from radar.modelos import Oferta

AGORA = dt.datetime(2026, 11, 21, 16, 10)
CAT = catalogo.carregar()
PCAT = CAT["produtos"]["philco_18k"]
LOJAS = {"webcontinental": {"tipo": "vtex", "base": "https://loja.invalid", "vendedor_contem": "webcontinental"}}

# Resposta no formato real da API VTEX (campos reduzidos), capturada em 21/11/2026 para o PAC18FTW.
VTEX = [
    {"productName": "Ar Condicionado Split Inverter Philco com WiFi 18000 BTUs Frio 220V PAC18FTW", "link": "https://loja.invalid/p1/p",
     "items": [{"itemId": "5507051", "ean": "7891356132421", "sellers": [
         {"sellerName": "WebContinental", "commertialOffer": {"Price": 2579.0, "ListPrice": 2930.68, "AvailableQuantity": 99999}}]}]},
    {"productName": "Ar Condicionado Split Philco Inverter Frio 18000 BTUS 220V PAC18FTW", "link": "https://loja.invalid/p2/p",
     "items": [{"itemId": "5719895", "ean": "7891356132438", "sellers": [
         {"sellerName": "Ta Barato To Levando", "commertialOffer": {"Price": 3749.89, "ListPrice": 3749.89, "AvailableQuantity": 100}}]}]},
]


def baixar(resposta):
    return lambda url: json.dumps(resposta)


class VerificarTest(unittest.TestCase):
    def test_confirma_so_o_estoque_proprio_e_ignora_terceiros_mais_caros(self):
        i = lojas.verificar("philco_18k", PCAT, "WebContinental", CAT, lojas=LOJAS, baixar=baixar(VTEX), agora=AGORA)
        self.assertEqual((i["status"], i["preco_loja"], i["preco_lista"], i["vendedor"], i["disponivel"]), ("confirmado", 2579.0, 2930.68, "WebContinental", True))

    def test_loja_sem_api_publica_fica_nao_verificavel_e_nao_consulta_a_rede(self):
        chamou = mock.Mock()
        i = lojas.verificar("philco_18k", PCAT, "Amazon", CAT, lojas=LOJAS, baixar=chamou)
        self.assertEqual(i["status"], "nao_verificavel")
        chamou.assert_not_called()

    def test_outro_modelo_nunca_conta_como_o_produto_exato(self):
        outro = [{"productName": "Ar Condicionado Split Philco 12000 BTUs PAC12FTW 220V", "link": "x",
                  "items": [{"ean": "1", "sellers": [{"sellerName": "WebContinental", "commertialOffer": {"Price": 1.0, "AvailableQuantity": 5}}]}]}]
        self.assertEqual(lojas.verificar("philco_18k", PCAT, "WebContinental", CAT, lojas=LOJAS, baixar=baixar(outro))["status"], "nao_encontrado")

    def test_sem_estoque_e_indisponivel_e_erro_de_rede_nao_levanta(self):
        sem = copy.deepcopy(VTEX)
        sem[0]["items"][0]["sellers"][0]["commertialOffer"]["AvailableQuantity"] = 0
        self.assertEqual(lojas.verificar("philco_18k", PCAT, "WebContinental", CAT, lojas=LOJAS, baixar=baixar(sem))["status"], "indisponivel")

        def cai(url):
            raise ValueError("sem rede")
        self.assertEqual(lojas.verificar("philco_18k", PCAT, "WebContinental", CAT, lojas=LOJAS, baixar=cai)["status"], "erro")


class RelacaoTest(unittest.TestCase):
    loja = {"status": "confirmado", "preco_loja": 2579.0}

    def test_loja_mais_cara_com_cupom_e_dependencia_do_cupom(self):
        self.assertEqual(lojas.relacionar(2379.0, self.loja, "PHI200"), {"relacao": "depende_de_cupom", "diferenca": 200.0})
        self.assertEqual(lojas.relacionar(2379.0, self.loja, None)["relacao"], "loja_mais_cara")

    def test_igual_dentro_da_tolerancia_e_loja_mais_barata(self):
        self.assertEqual(lojas.relacionar(2579.0, self.loja, "X")["relacao"], "igual")
        self.assertEqual(lojas.relacionar(2600.0, self.loja, None)["relacao"], "loja_mais_barata")

    def test_sem_confirmacao_quando_a_loja_nao_foi_conferida(self):
        self.assertEqual(lojas.relacionar(2379.0, None, "PHI200")["relacao"], "sem_confirmacao")
        self.assertEqual(lojas.relacionar(2379.0, {"status": "nao_verificavel"}, "PHI200")["relacao"], "sem_confirmacao")


class ConfiancaTest(unittest.TestCase):
    def nivel(self, **kw):
        base = dict(validacao="PROVAVEL", avisos=[], loja={"status": "confirmado", "preco_loja": 100.0}, relacao="igual", cupom_proprio=None)
        base.update(kw)
        return alertas.nivel_confianca(**base)[0]

    def test_alta_exige_produto_exato_e_preco_conferido_na_loja(self):
        self.assertEqual(self.nivel(), "ALTA")
        self.assertEqual(self.nivel(loja=None, relacao="sem_confirmacao"), "MEDIA")        # loja nao conferivel
        self.assertEqual(self.nivel(avisos=["sku_nao_confirmado"]), "BAIXA")
        self.assertEqual(self.nivel(avisos=["hora_incerta"]), "MEDIA")

    def test_cupom_nao_confirmado_limita_a_media_e_validado_libera(self):
        self.assertEqual(self.nivel(relacao="depende_de_cupom", cupom_proprio="PHI200"), "MEDIA")
        self.assertEqual(self.nivel(validacao="VALIDADO", relacao="depende_de_cupom", cupom_proprio="PHI200"), "ALTA")

    def test_loja_indisponivel_e_baixa(self):
        self.assertEqual(self.nivel(loja={"status": "indisponivel"}, relacao="sem_confirmacao"), "BAIXA")


class CupomEmbutidoTest(unittest.TestCase):
    """O caso REAL de 21/11/2026: Promobit anuncia R$ 2.379 com cupom PHI200; a loja cobra R$ 2.579."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        p = mock.patch.dict(os.environ, {"CENTRAL_COMPRAS_DADOS_PRIVADOS": self._tmp.name})
        p.start()
        self.con = db.abrir()
        self.addCleanup(self._tmp.cleanup)
        self.addCleanup(self.con.close)
        self.addCleanup(p.stop)
        for i, preco in enumerate((2569.0, 2569.0, 2699.0, 2718.0, 2569.0)):
            t = (AGORA - dt.timedelta(days=3) + dt.timedelta(hours=12 * i)).strftime("%Y-%m-%d %H:%M")
            self.con.execute("INSERT INTO observacoes (origem, produto, coletado_em, preco_entregue, onde, hash) VALUES (?,?,?,?,?,?)", ("t", "philco_18k", t, preco, "L", f"h{i}"))
        self.con.commit()
        self.regras = copy.deepcopy(ranking.carregar_regras())

    def oferta(self, **kw):
        base = dict(fonte="promobit", canal="recentes-p1", id_externo="3238582", loja="WebContinental", preco_anunciado=2379.0, cupom_codigo="PHI200",
                    publicado_em="2026-11-21 16:00", url="https://www.promobit.com.br/oferta/x/",
                    titulo="Ar Condicionado Split Inverter Philco com WiFi 18000 BTUs Frio 220V PAC18FTW")
        base.update(kw)
        return Oferta(**base)

    def conferir(self, produto, pcat, loja):
        return lojas.verificar(produto, pcat, loja, CAT, lojas=LOJAS, baixar=baixar(VTEX), agora=AGORA)

    def test_sem_conferir_a_loja_o_cupom_embutido_nao_desconta_e_a_confianca_e_media(self):
        r = varredura.processar_oferta(self.con, self.oferta(), CAT, self.regras, None, AGORA, diferir=True)
        linha = self.con.execute("SELECT preco_anunciado, preco_final, status_cupom FROM ofertas").fetchone()
        self.assertEqual((linha["preco_anunciado"], linha["preco_final"], linha["status_cupom"]), (2379.0, 2379.0, "NAO_CONFIRMADO"))  # nao desconta de novo
        self.assertEqual((r["confianca"], r["relacao_loja"]), ("MEDIA", "sem_confirmacao"))

    def test_com_a_loja_cobrando_mais_o_preco_depende_do_cupom_e_nao_vira_alerta(self):
        r = varredura.processar_oferta(self.con, self.oferta(), CAT, self.regras, None, AGORA, diferir=True, verificar_loja=self.conferir)
        self.assertEqual((r["loja"], r["relacao_loja"], r["confianca"]), ("confirmado", "depende_de_cupom", "MEDIA"))
        self.assertEqual(r["classe"], "MEDIA")                      # preco depende de cupom nao confirmado: nao e oferta urgente
        self.assertIn("so vale com um cupom NAO confirmado", r["motivo"])  # o motivo diz a causa certa (nao "voltagem/modelo")
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM candidatos_alerta").fetchone()[0], 0)

    def test_com_validacao_manual_no_carrinho_o_preco_anunciado_passa_a_valer(self):
        varredura.processar_oferta(self.con, self.oferta(), CAT, self.regras, None, AGORA, diferir=True, verificar_loja=self.conferir)
        oid = self.con.execute("SELECT id FROM ofertas").fetchone()["id"]
        self.con.execute("INSERT INTO validacoes_manuais (oferta_id, em, por, preco_validado) VALUES (?,?,?,?)", (oid, AGORA.strftime("%Y-%m-%d %H:%M:%S"), "carrinho (teste)", 2379.0))
        self.con.commit()
        r = varredura.processar_oferta(self.con, self.oferta(), CAT, self.regras, None, AGORA + dt.timedelta(minutes=1), diferir=True, verificar_loja=self.conferir)
        self.assertEqual((r["validacao"], r["confianca"]), ("VALIDADO", "ALTA"))

    def test_loja_igual_ao_anunciado_da_confianca_alta_mesmo_com_cupom_no_campo(self):
        igual = copy.deepcopy(VTEX)
        igual[0]["items"][0]["sellers"][0]["commertialOffer"]["Price"] = 2379.0
        r = varredura.processar_oferta(self.con, self.oferta(), CAT, self.regras, None, AGORA, diferir=True,
                                       verificar_loja=lambda p, c, l: lojas.verificar(p, c, l, CAT, lojas=LOJAS, baixar=baixar(igual), agora=AGORA))
        self.assertEqual((r["relacao_loja"], r["confianca"]), ("igual", "ALTA"))

    def test_mensagem_mostra_os_tres_niveis_de_preco_e_a_confianca(self):
        self.regras["alertas"].update(enviar=True, homologado_em="x")
        niveis = {"anunciado": 2379.0, "cupom_incluso": "PHI200", "loja": self.conferir("philco_18k", PCAT, "WebContinental"), "entregue": None}
        msg = alertas.montar_mensagem(nome_produto="Philco", loja="WebContinental", preco_anunciado=2379.0, cupom="PHI200", preco_final=2379.0, estimado=True,
                                      stats={}, fonte="promobit", canal="recentes-p1", detectado_em="21/11 16:00", status="PROVAVEL", url="https://x", classe="ALTA",
                                      motivo="m", avisos=["preco_depende_de_cupom_nao_confirmado"], frete_conhecido=False, niveis_preco=niveis,
                                      confianca=("MEDIA", ["o preço na loja é R$ 2.579,00 sem cupom"]))
        for trecho in ("Preço anunciado: R$ 2.379,00", "já embutido no preço anunciado; NÃO confirmado", "Confirmado na loja: R$ 2.579,00 sem cupom",
                       "Preço entregue (com frete): não confirmado", "Confiança: MEDIA", "só vale COM o cupom"):
            self.assertIn(trecho, msg)


if __name__ == "__main__":
    unittest.main()
