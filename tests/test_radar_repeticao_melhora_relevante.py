"""Repeticao dentro da janela do piloto: queda relevante (>= 3% E >= R$ 100) libera novo alerta, e a oferta suprimida e REAVALIADA quando a
janela de 240 min acaba (antes era descartada como `sem_mudanca_desde_a_ultima_vez`).

Regras sob teste (22/11/2026):
  - 7% de queda continua liberando (regra existente);
  - NOVO: queda adicional de pelo menos 3% E de pelo menos R$ 100 sobre o ultimo preco alertado, com preco comparavel (mesma loja ou loja
    desconhecida), produto exato, fonte revalidada;
  - mesmo preco de outra fonte nunca libera;
  - a politica completa nao muda (so o piloto liga a regra);
  - reavaliacao: so o ULTIMO candidato da oferta, so se suprimido por repeticao, so depois da janela, so se a oferta ainda esta fresca, e o novo
    candidato passa de novo por revalidacao na fonte, orcamento, limite por varredura e anti-repeticao. Oferta encerrada nao gera alerta retroativo.
Banco temporario, nenhum envio real; a ativacao local (operacao.yaml) e ignorada."""

import copy
import datetime as dt
import os
import tempfile
import unittest
from unittest import mock

from radar import alertas, catalogo, db, prioridade, ranking, varredura
from radar.modelos import Oferta

AGORA = dt.datetime(2026, 11, 22, 10, 0)
TITULO = "Ar Condicionado Split Elgin Eco Inverter III 12000 BTUs Frio 220V HJFC12C2WGCG"
ATIVA = lambda oid: (True, "ativa")


def regras(modo="PILOTO"):
    r = copy.deepcopy(ranking.carregar_regras(operacao=False))
    r["alertas"].update(enviar=True, homologado_em="2026-11-22 09:00")
    r["prioridade"]["limiar_ultimo_comum"] = 40
    r["piloto"] = {**r.get("piloto", {}), "ativo": modo == "PILOTO", "destinatario_confirmado_em": "2026-11-22 09:30"}
    return r


def minutos(m):
    return AGORA + dt.timedelta(minutes=m)


def oferta(fonte="promobit", canal="recentes-p1", ident="b9", url="https://www.promobit.com.br/oferta/elgin-12k-9/", *, loja="WebContinental",
           preco, quando=AGORA, publicado_antes_min=10, texto="oferta", cupom=None):
    return Oferta(fonte=fonte, canal=canal, id_externo=ident, titulo=TITULO, url=url, loja=loja, preco_anunciado=preco, texto=texto, cupom_codigo=cupom,
                  publicado_em=(quando - dt.timedelta(minutes=publicado_antes_min)).strftime("%Y-%m-%d %H:%M"))


def tres_fontes(preco, quando, loja="WebContinental"):
    return [oferta("pelando", "recentes", "p1", "https://www.pelando.com.br/d/elgin-abc?utm=x", loja=loja, preco=preco, quando=quando),
            oferta("telegram", "pelandobr", "901", "https://pelando.promo/Xk3Tz9", loja=None, preco=preco, quando=quando),
            oferta("promobit", "recentes-p1", "b9", "https://www.promobit.com.br/oferta/elgin-12k-9/?tag=afil", loja=loja, preco=preco, quando=quando)]


class Caixa:
    def __init__(self):
        self.msgs = []

    def __call__(self, t):
        self.msgs.append(t)
        return True, "ok"


class Base(unittest.TestCase):
    P0 = 1700.0
    HIST = [1950.0, 1930.0, 1899.0, 1940.0, 1960.0]

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        p = mock.patch.dict(os.environ, {"CENTRAL_COMPRAS_DADOS_PRIVADOS": self._tmp.name})
        p.start()
        self.addCleanup(p.stop)
        self.addCleanup(self._tmp.cleanup)
        self.con = db.abrir()
        self.addCleanup(self.con.close)
        for i, preco in enumerate(self.HIST):
            t = (AGORA - dt.timedelta(days=3) + dt.timedelta(hours=12 * i)).strftime("%Y-%m-%d %H:%M")
            self.con.execute("INSERT INTO observacoes (origem, produto, coletado_em, preco_entregue, onde, hash) VALUES (?,?,?,?,?,?)",
                             ("rastreador-ares", "elgin_12k", t, preco, "WebContinental", f"h{i}"))
        self.con.commit()
        self.cat = catalogo.carregar()
        self.caixa = Caixa()

    def ciclo(self, ofertas, quando, modo="PILOTO", revalidar=ATIVA):
        r = regras(modo)
        res = [varredura.processar_oferta(self.con, o, self.cat, r, self.caixa, quando, diferir=True) for o in ofertas]
        dec = prioridade.despachar(self.con, r, self.caixa, quando, revalidar=revalidar)
        return res, dec

    def estados(self):
        return sorted((x["fonte"], x["estado"]) for x in self.con.execute("SELECT fonte, estado FROM candidatos_alerta"))

    def ultimo_estado(self):
        return self.con.execute("SELECT estado, motivo FROM candidatos_alerta ORDER BY id DESC LIMIT 1").fetchone()

    def alerta_inicial(self, preco=None, modo="PILOTO"):
        self.ciclo([oferta(preco=preco or self.P0)], AGORA, modo)
        self.assertEqual(len(self.caixa.msgs), 1, self.estados())

    def gastar_orcamento_comum(self, n):
        for i in range(n):
            self.con.execute("INSERT INTO candidatos_alerta (produto, familia, classe, score, componentes_json, preco_final, mensagem, estado, motivo, criado_em, expira_em, decidido_em) "
                             "VALUES ('outro','f','ALTA',80,'{}',100,'x','enviado','orcamento:comum',?,?,?)", ("2026-11-22 08:00:00", "2026-11-22 08:30:00", "2026-11-22 08:00:00"))
        self.con.commit()


class Linha:
    """Linha minima de `alertas` para testar `_repete` sem banco."""
    def __init__(self, preco, minutos_atras=30, loja=None):
        self.d = {"preco": preco, "enviado_em": (AGORA - dt.timedelta(minutes=minutos_atras)).strftime("%Y-%m-%d %H:%M:%S"), "loja": loja}

    def __getitem__(self, k):
        return self.d[k]


def repete(ultimo, novo, *, minutos_atras=30, loja_ult=None, loja=None, extra=True, janela=240.0, pct7=7.0):
    kw = dict(queda_extra_pct=3, queda_extra_reais=100, loja=loja) if extra else {}
    return prioridade._repete(Linha(ultimo, minutos_atras, loja_ult), novo, AGORA, janela, pct7, **kw)


class RegraDeQuedaTest(unittest.TestCase):
    """A regra pura, sem banco: quedas de 2% a 7% e economias de R$ 50, 99, 100 e 150."""

    def test_tabela_de_economias_absolutas_e_percentuais(self):
        casos = [  # (ultimo, novo, repete?, por que)
            (1700.0, 1650.0, True, "R$ 50 (2,9%): pouco em reais e em %"),
            (3300.0, 3201.0, True, "R$ 99 (3,0%): falta R$ 1"),
            (3300.0, 3200.0, False, "R$ 100 (3,03%): libera"),
            (5000.0, 4850.0, False, "R$ 150 (3,0%): libera"),
            (5000.0, 4851.0, True, "R$ 149 (2,98%): falta pct e R$ 1"),
            (10000.0, 9800.0, True, "R$ 200, mas so 2%: nao libera"),
            (10000.0, 9700.0, False, "R$ 300 (3%): libera"),
            (2000.0, 1900.0, False, "R$ 100 (5%): libera"),
            (2000.0, 1920.0, True, "R$ 80 (4%): nao libera"),
            (4000.0, 3880.0, False, "R$ 120 (3%): libera"),
            (4000.0, 3881.0, True, "R$ 119 (2,98%): nao libera"),
            (1000.0, 930.0, False, "R$ 70, mas 7%: libera pela regra dos 7%"),
            (1000.0, 931.0, True, "6,9% e R$ 69: nao libera"),
            (3333.33, 3233.33, False, "R$ 100,00 exatos (3,0%): borda inclusiva"),
        ]
        for ultimo, novo, esperado, porque in casos:
            with self.subTest(porque):
                self.assertIs(repete(ultimo, novo), esperado, porque)

    def test_quedas_de_2_a_7_por_cento_em_quatro_bases(self):
        """Matriz independente: libera se >= 7% OU (>= 3% E >= R$ 100)."""
        for ultimo in (1700.0, 2000.0, 3300.0, 5000.0):
            for pct in (2, 3, 4, 5, 6, 7):
                novo = round(ultimo * (1 - pct / 100.0), 2)
                queda = round(ultimo - novo, 2)
                libera = pct >= 7 or (pct >= 3 and queda >= 100)
                with self.subTest(ultimo=ultimo, pct=pct, queda=queda):
                    self.assertIs(repete(ultimo, novo), not libera)

    def test_o_mesmo_preco_nunca_libera_e_preco_maior_tambem_nao(self):
        for novo in (3300.0, 3350.0):
            self.assertTrue(repete(3300.0, novo))

    def test_politica_completa_nao_muda_sem_a_regra_nova(self):
        self.assertTrue(repete(3300.0, 3200.0, extra=False))         # R$ 100 e 3%: so o piloto libera
        self.assertFalse(repete(3300.0, 3100.0, extra=False, janela=90.0, pct7=5.0))    # 6% com a regra de 5% da politica completa
        self.assertTrue(repete(3300.0, 3200.0, extra=False, janela=90.0, pct7=5.0))     # 3% e R$ 100 nao bastam na politica completa

    def test_fora_da_janela_nunca_repete(self):
        self.assertFalse(repete(3300.0, 3300.0, minutos_atras=241))
        self.assertTrue(repete(3300.0, 3300.0, minutos_atras=239))

    def test_preco_comparavel_exige_mesma_loja_ou_loja_desconhecida(self):
        self.assertTrue(repete(3300.0, 3200.0, loja_ult="Amazon", loja="WebContinental"))      # lojas diferentes: nao comparavel
        self.assertFalse(repete(3300.0, 3200.0, loja_ult="webcontinental", loja="WebContinental"))
        self.assertFalse(repete(3300.0, 3200.0, loja_ult="Amazon", loja=None))                  # Telegram nao informa a loja
        self.assertFalse(repete(3300.0, 3200.0, loja_ult=None, loja="Amazon"))
        self.assertFalse(repete(3300.0, 3000.0, loja_ult="Amazon", loja="WebContinental"))      # 9%: a regra dos 7% nao exige loja


class QuedaNaJanelaTest(Base):
    P0 = 3300.0
    HIST = [3750.0, 3720.0, 3690.0, 3730.0, 3760.0]

    def test_matriz_de_quedas_pelo_fluxo_real(self):
        """3300: 2% (R$ 66) e 3% com R$ 99 seguem suprimidos; R$ 100, 4%, 5%, 6% e 7% liberam. Um novo alerta so por caso."""
        casos = [(3234.0, False), (3201.0, False), (3200.0, True), (3168.0, True), (3135.0, True), (3102.0, True), (3069.0, True)]
        for preco, alerta in casos:
            with self.subTest(preco=preco):
                for tab in ("alertas", "candidatos_alerta", "ofertas", "outbox"):
                    self.con.execute(f"DELETE FROM {tab}")
                self.con.commit()
                self.caixa.msgs.clear()
                self.alerta_inicial()
                self.ciclo([oferta(preco=preco, quando=minutos(30))], minutos(30))
                self.assertEqual(len(self.caixa.msgs), 2 if alerta else 1, (preco, self.estados()))

    def test_mesma_oferta_nas_tres_fontes_com_queda_relevante_gera_um_unico_alerta_novo(self):
        self.alerta_inicial()
        self.ciclo(tres_fontes(3168.0, minutos(30)), minutos(30))                 # as tres fontes anunciam o mesmo preco (R$ 132 abaixo)
        self.assertEqual(len(self.caixa.msgs), 2, self.estados())
        self.assertEqual(sorted(e for _, e in self.estados())[-2:], ["substituido", "substituido"])
        self.ciclo(tres_fontes(3168.0, minutos(40)), minutos(40))                 # e continuam anunciando: nada novo
        self.assertEqual(len(self.caixa.msgs), 2, self.estados())

    def test_nova_fonte_com_o_mesmo_preco_nao_alerta(self):
        self.alerta_inicial()
        self.ciclo([oferta("telegram", "pelandobr", "901", "https://pelando.promo/Xk3Tz9", loja=None, preco=3300.0, quando=minutos(30))], minutos(30))
        self.ciclo([oferta("pelando", "recentes", "p1", "https://www.pelando.com.br/d/x", preco=3300.0, quando=minutos(35))], minutos(35))
        self.assertEqual(len(self.caixa.msgs), 1)

    def test_politica_completa_nao_e_alterada_pelo_fluxo_real(self):
        """Fora do piloto (90 min e 5%) a queda de 3% com R$ 100 NAO libera: a regra nova e so do piloto."""
        self.alerta_inicial(modo="COMPLETO")
        self.ciclo([oferta(preco=3200.0, quando=minutos(30))], minutos(30), "COMPLETO")      # R$ 100 e 3,03% em 30 min: segue suprimido
        self.assertEqual(len(self.caixa.msgs), 1, self.estados())
        self.ciclo([oferta(preco=3130.0, quando=minutos(40))], minutos(40), "COMPLETO")      # 5,15%: passa pela regra de 5% da politica completa
        self.assertEqual(len(self.caixa.msgs), 2, self.estados())

    def test_cupom_novo_so_alerta_se_o_preco_final_cair_o_suficiente(self):
        self.alerta_inicial()
        r = regras()
        for preco, esperado in ((3201.0, "suprimido_repeticao"), (3200.0, "enviado")):
            cid = prioridade.registrar_candidato(
                self.con, oferta_id=None, produto="elgin_12k", loja=None, vendedor=None, classe="ALTA", score=80.0,
                componentes={"economia_reais": 100.0, "economia_pct": 3.0, "confianca": ["ALTA", ["m"]], "avisos": []}, preco_final=preco,
                status_cupom="PROVAVEL", cupom="NOVO10", fonte="telegram", hora_incerta=False, mensagem="MSG", url="https://x/1", regras=r,
                agora=minutos(30))
            prioridade.despachar(self.con, r, self.caixa, minutos(30))
            self.assertEqual(self.con.execute("SELECT estado FROM candidatos_alerta WHERE id=?", (cid,)).fetchone()[0], esperado, preco)

    def test_cupom_expirado_nao_gera_alerta_mesmo_com_queda_grande(self):
        self.alerta_inicial()
        res, _ = self.ciclo([oferta(preco=2900.0, quando=minutos(30), cupom="ELGIN10", texto="cupom ELGIN10 expirado, nao funciona mais")], minutos(30))
        self.assertIn(res[0]["classe"], ("BAIXA",), res[0])
        self.assertEqual(len(self.caixa.msgs), 1)

    def test_loja_diferente_nao_e_comparavel_para_a_regra_nova(self):
        self.alerta_inicial()
        self.ciclo([oferta("promobit", "recentes-p1", "z1", "https://www.promobit.com.br/oferta/z1/", loja="Amazon", preco=3200.0, quando=minutos(30))], minutos(30))
        self.assertEqual(len(self.caixa.msgs), 1, self.estados())           # R$ 100 e 3,03%, mas lojas conhecidas e diferentes
        self.ciclo([oferta("promobit", "recentes-p1", "z2", "https://www.promobit.com.br/oferta/z2/", loja="WebContinental", preco=3200.0, quando=minutos(40))], minutos(40))
        self.assertEqual(len(self.caixa.msgs), 2, self.estados())           # mesma loja: libera

    def test_fonte_encerrada_na_revalidacao_nao_alerta_nem_com_queda_grande(self):
        self.alerta_inicial()
        self.ciclo([oferta(preco=3100.0, quando=minutos(30))], minutos(30), revalidar=lambda oid: (False, "encerrada na fonte (FINISHED)"))
        self.assertEqual(len(self.caixa.msgs), 1)
        self.assertEqual(self.ultimo_estado()["estado"], "expirado")

    def test_produto_nao_exato_nao_passa_mesmo_com_queda_grande(self):
        self.alerta_inicial()
        r = regras()
        cid = prioridade.registrar_candidato(
            self.con, oferta_id=None, produto="elgin_12k", loja=None, vendedor=None, classe="ALTA", score=80.0,
            componentes={"economia_reais": 300.0, "economia_pct": 10.0, "confianca": ["ALTA", ["m"]], "avisos": ["tensao_ambigua"]}, preco_final=3000.0,
            status_cupom="PROVAVEL", cupom=None, fonte="telegram", hora_incerta=False, mensagem="MSG", url="https://x/1", regras=r, agora=minutos(30))
        prioridade.despachar(self.con, r, self.caixa, minutos(30))
        self.assertEqual(self.con.execute("SELECT estado FROM candidatos_alerta WHERE id=?", (cid,)).fetchone()[0], "nao_selecionado")
        self.assertEqual(len(self.caixa.msgs), 1)

    def test_orcamento_diario_vale_para_o_alerta_liberado_pela_queda(self):
        """Piloto: 2 comuns por dia. 1o alerta, 2o pela queda; o 3o (nova queda de R$ 100+) fica retido pelo orcamento."""
        self.alerta_inicial()
        self.ciclo([oferta(preco=3168.0, quando=minutos(30))], minutos(30))
        self.assertEqual(len(self.caixa.msgs), 2)
        self.ciclo([oferta(preco=3050.0, quando=minutos(60))], minutos(60))
        self.assertEqual(len(self.caixa.msgs), 2, self.estados())
        self.assertEqual(self.ultimo_estado()["estado"], "retida_orcamento")

    def test_um_alerta_por_varredura_mesmo_com_dois_produtos_liberados_pela_queda(self):
        r = regras()
        for prod, preco in (("elgin_12k", 3300.0), ("philco_18k", 3900.0)):
            alertas.registrar(self.con, oferta_id=None, produto=prod, loja="WebContinental", vendedor=None, cupom=None, preco=preco, url="https://x/" + prod,
                              classe="ALTA", status="PROVAVEL", modo="real", detalhe="t", agora=AGORA)
        ids = []
        for prod, preco, score in (("elgin_12k", 3168.0, 80.0), ("philco_18k", 3700.0, 85.0)):
            ids.append(prioridade.registrar_candidato(
                self.con, oferta_id=None, produto=prod, loja=None, vendedor=None, classe="ALTA", score=score,
                componentes={"economia_reais": 200.0, "economia_pct": 5.0, "confianca": ["ALTA", ["m"]], "avisos": []}, preco_final=preco,
                status_cupom="PROVAVEL", cupom=None, fonte="telegram", hora_incerta=False, mensagem="MSG " + prod, url="https://x/" + prod, regras=r,
                agora=minutos(30)))
        prioridade.despachar(self.con, r, self.caixa, minutos(30))
        self.assertEqual(len(self.caixa.msgs), 1)                                     # 1 por varredura no TOTAL
        self.assertIn("philco_18k", self.caixa.msgs[0])                               # a de maior pontuacao


class ReavaliacaoTest(Base):
    """Base R$ 1.700: 4% (R$ 68) e suprimido na janela (nao chega a R$ 100) e e reavaliado quando os 240 min acabam."""
    SUP = 1632.0

    def suprimir(self, modo="PILOTO"):
        self.alerta_inicial(modo=modo)
        self.ciclo([oferta(preco=self.SUP, quando=minutos(60))], minutos(60), modo)
        self.assertEqual(self.ultimo_estado()["estado"], "suprimido_repeticao")

    def test_oferta_valida_e_reavaliada_apos_a_janela_e_alerta_uma_vez(self):
        self.suprimir()
        res, _ = self.ciclo([oferta(preco=self.SUP, quando=minutos(60))], minutos(255))
        self.assertTrue(res[0].get("reavaliada"), res[0])
        self.assertEqual(len(self.caixa.msgs), 2)
        self.assertEqual(self.ultimo_estado()["estado"], "enviado")
        res, _ = self.ciclo([oferta(preco=self.SUP, quando=minutos(60))], minutos(265))
        self.assertFalse(res[0].get("reavaliada"))
        self.assertEqual(len(self.caixa.msgs), 2)

    def test_nao_reavalia_antes_da_janela_terminar(self):
        self.suprimir()
        res, _ = self.ciclo([oferta(preco=self.SUP, quando=minutos(60))], minutos(200))
        self.assertFalse(res[0].get("reavaliada"), res[0])
        self.assertEqual(res[0]["descarte"], "sem_mudanca_desde_a_ultima_vez")
        self.assertEqual(len(self.caixa.msgs), 1)

    def test_oferta_relampago_encerrada_antes_da_reavaliacao_nao_gera_alerta_retroativo(self):
        self.suprimir()
        res, _ = self.ciclo([oferta(preco=self.SUP, quando=minutos(60))], minutos(255), revalidar=lambda oid: (False, "encerrada na fonte (FINISHED)"))
        self.assertTrue(res[0].get("reavaliada"))
        self.assertEqual(len(self.caixa.msgs), 1)
        self.assertEqual(self.ultimo_estado()["estado"], "expirado")
        self.ciclo([oferta(preco=self.SUP, quando=minutos(60))], minutos(265), revalidar=ATIVA)      # nem depois: o ultimo candidato ja nao e o suprimido
        self.assertEqual(len(self.caixa.msgs), 1)

    def test_oferta_que_saiu_da_lista_nao_e_reavaliada(self):
        self.suprimir()
        self.ciclo([], minutos(255))                                                # a fonte nao a lista mais: nada a reavaliar
        self.assertEqual(len(self.caixa.msgs), 1)

    def test_oferta_velha_demais_nao_e_reavaliada(self):
        self.ciclo([oferta(preco=self.P0, publicado_antes_min=300)], AGORA)         # publicada ha 5 h: ainda fresca (<= 6 h)
        self.assertEqual(len(self.caixa.msgs), 1)
        self.ciclo([oferta(preco=self.SUP, quando=minutos(60), publicado_antes_min=360)], minutos(60))
        self.assertEqual(self.ultimo_estado()["estado"], "suprimido_repeticao")
        res, _ = self.ciclo([oferta(preco=self.SUP, quando=minutos(60), publicado_antes_min=360)], minutos(255))
        self.assertEqual(res[0]["acao"], "sem_alerta")
        self.assertEqual(res[0]["descarte"], "oferta_antiga")
        self.assertEqual(len(self.caixa.msgs), 1)

    def test_reavaliacao_respeita_o_orcamento_diario(self):
        self.suprimir()
        self.gastar_orcamento_comum(1)                                              # o alerta inicial ja gastou 1; com mais 1 o dia fecha em 2
        res, _ = self.ciclo([oferta(preco=self.SUP, quando=minutos(60))], minutos(255))
        self.assertTrue(res[0].get("reavaliada"))
        self.assertEqual(len(self.caixa.msgs), 1)
        self.assertEqual(self.ultimo_estado()["estado"], "retida_orcamento")

    def test_tres_fontes_reavaliadas_juntas_geram_um_unico_alerta(self):
        self.alerta_inicial()
        self.ciclo(tres_fontes(self.SUP, minutos(60)), minutos(60))
        self.assertEqual(len(self.caixa.msgs), 1)
        res, _ = self.ciclo(tres_fontes(self.SUP, minutos(60)), minutos(255))
        self.assertGreaterEqual(sum(1 for r in res if r.get("reavaliada")), 1)      # so o melhor de cada ciclo foi suprimido; os outros foram substituidos
        self.assertEqual(len(self.caixa.msgs), 2, self.estados())                   # um unico alerta novo, nao tres
        self.ciclo(tres_fontes(self.SUP, minutos(60)), minutos(265))
        self.assertEqual(len(self.caixa.msgs), 2, self.estados())

    def test_queda_menor_que_3_por_cento_nao_vira_alerta_na_reavaliacao(self):
        self.alerta_inicial()
        self.ciclo([oferta(preco=1666.0, quando=minutos(60))], minutos(60))         # 2%: a porta de 24 h ja segura (nem chega a candidato)
        self.ciclo([oferta(preco=1666.0, quando=minutos(60))], minutos(255))
        self.assertEqual(len(self.caixa.msgs), 1, self.estados())

    def test_politica_completa_tambem_reavalia_apos_90_min(self):
        self.suprimir(modo="COMPLETO")                                              # 4% em 60 min: abaixo dos 5% da politica completa
        res, _ = self.ciclo([oferta(preco=self.SUP, quando=minutos(60))], minutos(100), "COMPLETO")
        self.assertTrue(res[0].get("reavaliada"), res[0])
        self.assertEqual(len(self.caixa.msgs), 2)


class LimitacaoDeRevalidacaoTest(Base):
    def test_LIMITACAO_telegram_e_pelando_nao_sao_revalidaveis_e_expiram_no_piloto_real(self):
        """Na varredura real o piloto revalida a fonte antes de enviar, mas so Promobit e Gatry sabem se revalidar. Uma oferta que so aparece
        no Telegram ou no Pelando vira `expirado: fonte ... nao permite revalidar` e NAO gera alerta (documentado; nao e alterado aqui)."""
        revalidar_real = lambda oid: varredura.revalidar_oferta(self.con, oid)
        self.ciclo([oferta("telegram", "pelandobr", "901", "https://pelando.promo/Xk3Tz9", loja=None, preco=self.P0)], AGORA, revalidar=revalidar_real)
        self.assertEqual(len(self.caixa.msgs), 0)
        ultimo = self.ultimo_estado()
        self.assertEqual(ultimo["estado"], "expirado")
        self.assertIn("nao permite revalidar", ultimo["motivo"])


if __name__ == "__main__":
    unittest.main()
