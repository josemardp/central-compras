"""Politica de prioridade e orcamento de notificacoes (radar/prioridade.py). Nada e enviado de verdade."""

import copy
import datetime as dt
import os
import tempfile
import unittest
from unittest import mock

from radar import alertas, catalogo, db, outbox, prioridade, ranking, varredura
from radar.modelos import Oferta

AGORA = dt.datetime(2026, 11, 21, 10, 0)
STATS = {"observacoes_validas": 20, "cobertura_dias": 3,
         "historico_total": {"menor": 1000.0, "maior": 1300.0, "mediana": 1150.0},
         "ultimos_30_dias": {"menor": 1000.0, "maior": 1300.0, "mediana": 1150.0}}


def regras(real=False, **prio):
    r = copy.deepcopy(ranking.carregar_regras())
    r["alertas"].update(enviar=real, homologado_em="2026-11-21 09:00" if real else None)
    r["prioridade"] = {**r.get("prioridade", {}), "limiar_ultimo_comum": 40, **prio}  # limiar desligado por padrao: testa o orcamento puro
    return r


class Caixa:
    def __init__(self, falha=False):
        self.msgs, self.falha = [], falha

    def __call__(self, t):
        if self.falha:
            return False, "canal fora (simulado)"
        self.msgs.append(t)
        return True, "ok"


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        p = mock.patch.dict(os.environ, {"CENTRAL_COMPRAS_DADOS_PRIVADOS": self._tmp.name})
        p.start()
        self.addCleanup(self._tmp.cleanup)       # LIFO: roda por ULTIMO (depois de fechar o banco)
        self.addCleanup(lambda: self.con.close())
        self.addCleanup(p.stop)
        self.con = db.abrir()
        self.n = 0

    def cand(self, produto="k800_pro_127v", score=70.0, classe="ALTA", preco=1000.0, quando=AGORA, r=None, **kw):
        self.n += 1
        return prioridade.registrar_candidato(
            self.con, oferta_id=kw.get("oferta_id"), produto=produto, loja=f"L{self.n}", vendedor=None, classe=classe, score=score,
            componentes={"economia_reais": 100.0, "economia_pct": 10.0}, preco_final=preco, status_cupom="PROVAVEL", cupom=None,
            fonte="promobit", hora_incerta=False, mensagem=f"MSG {produto} {preco} score {score}", url=None, regras=r or regras(), agora=quando)

    def estados(self):
        return {r["id"]: (r["estado"], r["motivo"]) for r in self.con.execute("SELECT id, estado, motivo FROM candidatos_alerta")}


class PontuacaoTest(unittest.TestCase):
    def pont(self, preco=950.0, ref=1000.0, validacao="PROVAVEL", avisos=(), idade=0.2, incerta=False, rep=0):
        return prioridade.pontuar(preco_final=preco, preco_ref=ref, stats=STATS, validacao=validacao, avisos=list(avisos), idade_horas=idade,
                                  hora_incerta=incerta, repeticoes_24h=rep, regras=regras())

    def test_economia_maior_pontua_mais_e_a_explicacao_mostra_os_numeros(self):
        pequena, grande = self.pont(preco=970.0)[0], self.pont(preco=800.0)[0]
        self.assertGreater(grande, pequena)
        _, comp = self.pont(preco=800.0)
        self.assertEqual((comp["economia_reais"], comp["economia_pct"], comp["base_de_comparacao"]), (200.0, 20.0, "melhor preco atual"))

    def test_validado_vale_mais_que_provavel_e_exatidao_penaliza_aviso(self):
        self.assertGreater(self.pont(validacao="VALIDADO")[0], self.pont(validacao="PROVAVEL")[0])
        self.assertGreater(self.pont()[0], self.pont(avisos=["tensao_nao_informada"])[0])
        self.assertGreater(self.pont(avisos=["sku_nao_confirmado"])[0], self.pont(avisos=["nome_alternativo"])[0])

    def test_hora_incerta_nao_ganha_urgencia_nem_confianca_cheia(self):
        certa, incerta = self.pont(idade=0.2), self.pont(idade=None, incerta=True)
        self.assertEqual(incerta[1]["pontos"]["urgencia"], 0.0)
        self.assertGreater(certa[0], incerta[0])
        self.assertGreater(certa[1]["pontos"]["urgencia"], 0)

    def test_repeticao_recente_do_mesmo_produto_reduz_a_pontuacao(self):
        self.assertEqual(round(self.pont()[0] - self.pont(rep=1)[0], 1), 8.0)
        self.assertEqual(round(self.pont()[0] - self.pont(rep=5)[0], 1), 16.0)  # limitada a 2

    def test_sem_referencia_usa_a_mediana_do_historico(self):
        s, c = self.pont(ref=None)
        self.assertEqual(c["base_de_comparacao"], "mediana do historico")

    def test_pontuacao_fica_entre_0_e_100(self):
        self.assertLessEqual(self.pont(preco=1.0, validacao="VALIDADO")[0], 100.0)
        self.assertGreaterEqual(self.pont(preco=5000.0, rep=9)[0], 0.0)


class OrdemEOrcamentoTest(Base):
    def test_ordena_por_pontuacao_e_respeita_o_maximo_por_ciclo(self):
        ids = [self.cand(produto=p, score=s) for p, s in (("a", 50), ("b", 90), ("c", 60), ("d", 75))]
        dec = prioridade.despachar(self.con, regras(), None, AGORA)
        sel = [d["id"] for d in dec if d["estado"] == "selecionado_sombra"]
        self.assertEqual(sel, [ids[1], ids[3]])                      # 90 e 75: os dois melhores, nao os primeiros que chegaram
        self.assertEqual(self.estados()[ids[2]][0], "substituido")   # 60 esta 30 pontos abaixo do topo (90): perde a vez
        self.assertEqual(self.estados()[ids[0]][0], "substituido")   # 50 idem

    def test_oferta_muito_superior_substitui_candidato_menor_ainda_nao_enviado(self):
        r = regras(max_por_ciclo=1)
        fraca = self.cand(produto="a", score=45, r=r)
        forte = self.cand(produto="b", score=90, r=r)
        prioridade.despachar(self.con, r, None, AGORA)
        e = self.estados()
        self.assertEqual(e[forte][0], "selecionado_sombra")
        self.assertEqual(e[fraca][0], "substituido")                 # 45 + 15 <= 90
        self.assertIn("superior", e[fraca][1])

    def test_candidato_proximo_do_topo_nao_e_substituido_e_espera(self):
        r = regras(max_por_ciclo=1)
        quase = self.cand(produto="a", score=80, r=r)
        topo = self.cand(produto="b", score=90, r=r)
        prioridade.despachar(self.con, r, None, AGORA)
        self.assertEqual(self.estados()[quase][0], "pendente")

    def test_so_a_melhor_oferta_de_cada_produto_por_despacho(self):
        a = self.cand(produto="k800_pro_127v", score=60)
        b = self.cand(produto="k800_pro_127v", score=85)
        prioridade.despachar(self.con, regras(), None, AGORA)
        e = self.estados()
        self.assertEqual((e[b][0], e[a][0]), ("selecionado_sombra", "substituido"))

    def test_orcamento_diario_esgota_e_so_excecao_de_alta_pontuacao_passa(self):
        r = regras(orcamento_diario=2, orcamento_excecao_diario=1, max_por_ciclo=9)
        for i in range(2):
            self.cand(produto=f"p{i}", score=60, r=r)
        prioridade.despachar(self.con, r, None, AGORA)
        media = self.cand(produto="m", score=70, r=r, quando=AGORA + dt.timedelta(minutes=10))
        otima = self.cand(produto="o", score=88, r=r, quando=AGORA + dt.timedelta(minutes=10))
        outra_otima = self.cand(produto="o2", score=92, r=r, quando=AGORA + dt.timedelta(minutes=10))
        prioridade.despachar(self.con, r, None, AGORA + dt.timedelta(minutes=10))
        e = self.estados()
        self.assertEqual(e[media][0], "retida_orcamento")
        self.assertIn("orcamento diario esgotado", e[media][1])
        self.assertEqual(e[outra_otima][0], "selecionado_sombra")    # 92 usa a unica excecao
        self.assertTrue(e[outra_otima][1].startswith("orcamento:excecao"))
        self.assertEqual(e[otima][0], "retida_orcamento")              # excecao ja usada

    def test_pontuacao_abaixo_do_minimo_nao_vira_alerta_mesmo_sobrando_orcamento(self):
        c = self.cand(score=30)
        prioridade.despachar(self.con, regras(), None, AGORA)
        self.assertEqual(self.estados()[c][0], "nao_selecionado")

    def test_candidato_vencido_expira_e_fora_do_horario_adia(self):
        velho = self.cand(quando=AGORA - dt.timedelta(minutes=45))
        prioridade.despachar(self.con, regras(), None, AGORA)
        self.assertEqual(self.estados()[velho][0], "expirado")
        novo = self.cand(quando=AGORA)
        dec = prioridade.despachar(self.con, regras(), None, AGORA.replace(hour=2))  # 02:00
        self.assertEqual(dec[-1]["estado"], "adiado")
        self.assertEqual(self.estados()[novo][0], "pendente")


class LimiarDoMomentoTest(Base):
    """A vaga N do dia exige mais pontos que a vaga 1: oferta mediana cedo nao gasta o orcamento da melhor da tarde."""

    def test_formula_sobe_linear_da_pontuacao_minima_ate_o_limiar_da_ultima_vaga(self):
        p = prioridade.config(regras(orcamento_diario=6, limiar_ultimo_comum=65))
        self.assertEqual([prioridade.limiar_do_momento(p, k) for k in range(6)], [40.0, 45.0, 50.0, 55.0, 60.0, 65.0])
        self.assertEqual(prioridade.limiar_do_momento(p, 99), 65.0)                       # nunca passa do limiar da ultima vaga
        desligado = prioridade.config(regras(limiar_ultimo_comum=40))
        self.assertEqual(prioridade.limiar_do_momento(desligado, 5), 40.0)

    def test_mediana_cedo_nao_come_a_vaga_da_oferta_melhor_que_chega_depois(self):
        r = regras(orcamento_diario=3, limiar_ultimo_comum=70, max_por_ciclo=9, orcamento_excecao_diario=0)
        ids = []
        for i, s in enumerate((45, 48, 50, 75, 72)):      # chegam um por vez, 10 min entre eles
            q = AGORA + dt.timedelta(minutes=10 * i)
            ids.append(self.cand(produto=f"p{i}", score=s, r=r, quando=q))
            prioridade.despachar(self.con, r, None, q)
        e = self.estados()
        self.assertEqual(e[ids[0]][0], "selecionado_sombra")   # 45 >= 40 (1a vaga)
        self.assertEqual(e[ids[1]][0], "retida_orcamento")      # 48 < 55 (2a vaga)
        self.assertIn("limiar do momento", e[ids[1]][1])
        self.assertEqual(e[ids[2]][0], "retida_orcamento")      # 50 < 55
        self.assertEqual(e[ids[3]][0], "selecionado_sombra")   # 75 usa a 2a vaga
        self.assertEqual(e[ids[4]][0], "selecionado_sombra")   # 72 >= 70 usa a 3a: as vagas foram para as melhores, nao para as primeiras
        self.assertEqual(sum(1 for v in e.values() if v[0] == "selecionado_sombra"), 3)

    def test_o_que_o_limiar_segura_aparece_nas_retidas(self):
        r = regras(orcamento_diario=2, limiar_ultimo_comum=70, max_por_ciclo=9, orcamento_excecao_diario=0)
        a = self.cand(produto="a", score=45, r=r)
        self.cand(produto="b", score=50, r=r)
        prioridade.despachar(self.con, r, None, AGORA + dt.timedelta(minutes=2))   # b (melhor) pega a 1a vaga; a fica abaixo do limiar da 2a
        self.assertEqual([x["id"] for x in prioridade.retidas(self.con, AGORA + dt.timedelta(minutes=3))], [a])

    def test_oferta_acima_da_excecao_nunca_e_barrada_pelo_limiar(self):
        r = regras(orcamento_diario=2, limiar_ultimo_comum=95, max_por_ciclo=9)
        c = self.cand(produto="a", score=85, r=r)
        prioridade.despachar(self.con, r, None, AGORA)
        self.assertEqual(self.estados()[c][0], "selecionado_sombra")


class PerdaSilenciosaTest(Base):
    """O orcamento nunca faz uma boa oferta sumir sem deixar rastro visivel."""

    def test_quem_vence_esperando_vaga_vira_retida_e_nao_expirada(self):
        r = regras(max_por_ciclo=1, validade_candidato_min=25)
        a = self.cand(produto="a", score=85, r=r)
        b = self.cand(produto="b", score=80, r=r)         # 5 pontos abaixo: nao e substituida, so espera
        prioridade.despachar(self.con, r, None, AGORA)
        self.assertEqual(self.estados()[b], ("pendente", "aguardando vaga no proximo ciclo"))
        # ciclos seguintes: o produto "a" ja usou a vaga do ciclo seguinte? nao: cada ciclo tem a sua. Para forcar a espera, esgota o orcamento.
        r2 = regras(max_por_ciclo=1, validade_candidato_min=25, orcamento_diario=1, orcamento_excecao_diario=0)
        prioridade.despachar(self.con, r2, None, AGORA + dt.timedelta(minutes=10))
        self.assertEqual(self.estados()[b][0], "retida_orcamento")
        self.assertIn("NAO entregue", self.estados()[b][1])

    def test_pendente_que_vence_aguardando_vaga_aparece_nas_retidas(self):
        r = regras(max_por_ciclo=1, validade_candidato_min=15)
        self.cand(produto="a", score=85, r=r)
        b = self.cand(produto="b", score=80, r=r)
        prioridade.despachar(self.con, r, None, AGORA)                                    # b espera
        prioridade.despachar(self.con, regras(max_por_ciclo=0), None, AGORA + dt.timedelta(minutes=20))   # venceu
        e = self.estados()[b]
        self.assertEqual(e[0], "retida_orcamento")
        self.assertIn("venceu aguardando vaga", e[1])
        self.assertEqual([x["id"] for x in prioridade.retidas(self.con, AGORA + dt.timedelta(minutes=21))], [b])

    def test_oferta_excepcional_sem_excecao_sobrando_fica_retida_com_o_motivo_certo(self):
        r = regras(orcamento_diario=0, orcamento_excecao_diario=0, max_por_ciclo=9)
        c = self.cand(produto="a", score=95, r=r)
        prioridade.despachar(self.con, r, None, AGORA)
        e = self.estados()[c]
        self.assertEqual(e[0], "retida_orcamento")
        self.assertIn("excecao esgotado", e[1])

    def test_bloco_do_relatorio_so_existe_com_alertas_reais_e_filtra_a_familia(self):
        r = regras(real=True, orcamento_diario=0, orcamento_excecao_diario=0)
        self.cand(produto="dreame_f10", score=90, r=r)
        self.cand(produto="elgin_12k", score=88, r=r)
        prioridade.despachar(self.con, r, Caixa(), AGORA)
        sombra = regras(real=False)
        self.assertEqual(prioridade.bloco_retidas(self.con, sombra, "rastreador-robos", AGORA), "")   # sombra: relatorio inalterado
        robos = prioridade.bloco_retidas(self.con, r, "rastreador-robos", AGORA)
        self.assertIn("dreame_f10", robos)
        self.assertNotIn("elgin_12k", robos)
        self.assertIn("elgin_12k", prioridade.bloco_retidas(self.con, r, "rastreador-ares", AGORA))
        self.assertEqual(prioridade.bloco_retidas(self.con, r, "rastreador-chuveiro", AGORA), "")      # nada retido nessa familia


class CriticosTest(Base):
    def test_critica_passa_do_orcamento_comum_mas_tem_orcamento_e_rajada_proprios(self):
        r = regras(orcamento_diario=0, orcamento_critico_diario=3, max_criticos_por_ciclo=2, max_por_ciclo=9)
        c = [self.cand(produto=f"p{i}", classe="CRITICA", score=90 - i, r=r) for i in range(3)]
        prioridade.despachar(self.con, r, None, AGORA)
        e = self.estados()
        self.assertEqual([e[x][0] for x in c], ["selecionado_sombra", "selecionado_sombra", "pendente"])  # 2 por ciclo (anti-rajada)
        prioridade.despachar(self.con, r, None, AGORA + dt.timedelta(minutes=10))
        self.assertEqual(self.estados()[c[2]][0], "selecionado_sombra")                                  # o 3o sai no ciclo seguinte
        extra = self.cand(produto="p9", classe="CRITICA", score=99, r=r, quando=AGORA + dt.timedelta(minutes=20))
        prioridade.despachar(self.con, r, None, AGORA + dt.timedelta(minutes=20))
        self.assertEqual(self.estados()[extra][0], "retida_orcamento")                                    # orcamento critico (3) esgotado
        self.assertIn("CRITICO", self.estados()[extra][1])

    def test_critico_nao_se_repete_sem_melhora_mas_repete_com_melhora_de_5_por_cento(self):
        r = regras(orcamento_critico_diario=9)
        primeira = self.cand(produto="k", classe="CRITICA", score=95, preco=1000.0, r=r)
        prioridade.despachar(self.con, r, None, AGORA)
        t1 = AGORA + dt.timedelta(minutes=10)
        igual = self.cand(produto="k", classe="CRITICA", score=95, preco=990.0, r=r, quando=t1)   # so 1% melhor
        prioridade.despachar(self.con, r, None, t1)
        self.assertEqual(self.estados()[igual][0], "suprimido_repeticao")
        t2 = AGORA + dt.timedelta(minutes=20)
        melhor = self.cand(produto="k", classe="CRITICA", score=95, preco=900.0, r=r, quando=t2)  # 10% melhor
        prioridade.despachar(self.con, r, None, t2)
        self.assertEqual(self.estados()[melhor][0], "selecionado_sombra")
        t3 = AGORA + dt.timedelta(minutes=60)  # 40 min depois do ultimo alerta (t2): passou o intervalo de 30 min
        depois = self.cand(produto="k", classe="CRITICA", score=95, preco=899.0, r=r, quando=t3)
        prioridade.despachar(self.con, r, None, t3)
        self.assertEqual(self.estados()[depois][0], "selecionado_sombra")

    def test_comum_repetido_em_90_min_e_suprimido(self):
        r = regras()
        self.cand(produto="k", score=80, preco=1000.0, r=r)
        prioridade.despachar(self.con, r, None, AGORA)
        t = AGORA + dt.timedelta(minutes=30)
        de_novo = self.cand(produto="k", score=80, preco=995.0, r=r, quando=t)
        prioridade.despachar(self.con, r, None, t)
        self.assertEqual(self.estados()[de_novo][0], "suprimido_repeticao")


class EnvioRevalidacaoETest(Base):
    def test_em_sombra_nada_e_enviado_e_em_modo_real_envia_so_o_selecionado(self):
        self.cand(produto="a", score=80)
        caixa = Caixa()
        prioridade.despachar(self.con, regras(real=False), caixa, AGORA)
        self.assertEqual(caixa.msgs, [])                      # alertas desligados: sombra, mesmo com canal disponivel
        self.cand(produto="b", score=82, quando=AGORA + dt.timedelta(minutes=10))
        prioridade.despachar(self.con, regras(real=True), caixa, AGORA + dt.timedelta(minutes=10))
        self.assertEqual(len(caixa.msgs), 1)
        self.assertIn("MSG b", caixa.msgs[0])

    def test_falha_de_envio_guarda_na_fila_com_validade_e_nao_consome_orcamento_real(self):
        c = self.cand(produto="a", score=80)
        prioridade.despachar(self.con, regras(real=True), Caixa(falha=True), AGORA)
        self.assertEqual(self.estados()[c][0], "falha_envio")
        pend = outbox.pendentes(self.con, tipo="alerta", agora_dt=AGORA)
        self.assertEqual(len(pend), 1)
        self.assertEqual(pend[0]["expira_em"], "2026-11-21 10:30:00")

    def test_candidato_que_esperou_e_revalidado_antes_de_ser_entregue(self):
        c = self.cand(produto="a", score=80, oferta_id=7, quando=AGORA)
        caixa = Caixa()
        dec = prioridade.despachar(self.con, regras(real=True), caixa, AGORA + dt.timedelta(minutes=10),
                                   revalidar=lambda oid: (False, "oferta encerrada na fonte (status FINISHED)"))
        self.assertEqual(self.estados()[c][0], "expirado")
        self.assertEqual(caixa.msgs, [])                       # oferta encerrada nunca e apresentada como ativa
        c2 = self.cand(produto="b", score=80, oferta_id=8, quando=AGORA)
        prioridade.despachar(self.con, regras(real=True), caixa, AGORA + dt.timedelta(minutes=10), revalidar=lambda oid: (True, "ativa"))
        self.assertEqual(self.estados()[c2][0], "enviado")

    def test_revalidacao_que_quebra_nao_entrega(self):
        c = self.cand(produto="a", score=80, oferta_id=7)
        caixa = Caixa()
        prioridade.despachar(self.con, regras(real=True), caixa, AGORA + dt.timedelta(minutes=10), revalidar=lambda oid: 1 / 0)
        self.assertEqual((self.estados()[c][0], caixa.msgs), ("expirado", []))


class FluxoCompletoNaVarreduraTest(Base):
    """Fontes falsas -> ofertas -> candidatos -> despacho por prioridade, sem rede e sem envio."""

    def setUp(self):
        super().setUp()
        for prod, base in (("k800_pro_127v", 1260.0), ("tapo_rv20_max", 860.0), ("dreame_f10", 1994.05)):
            for i, p in enumerate([base * 1.02, base * 1.01, base, base * 1.03, base]):
                t = (AGORA - dt.timedelta(days=3) + dt.timedelta(hours=12 * i)).strftime("%Y-%m-%d %H:%M")
                self.con.execute("INSERT INTO observacoes (origem, produto, coletado_em, preco_entregue, onde, hash) VALUES (?,?,?,?,?,?)",
                                 ("t", prod, t, p, "L", f"{prod}{i}"))
        self.con.commit()

    def test_a_melhor_oferta_ganha_do_que_chegou_primeiro(self):
        pub = (AGORA - dt.timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M")

        def fonte(cfg):
            return [  # a fraca chega PRIMEIRO
                Oferta(fonte="promobit", canal="recentes-p1", id_externo="1", titulo="Robô Aspirador TP-Link Tapo RV20 Max", loja="Amazon",
                       preco_anunciado=800.0, publicado_em=pub, texto="oferta"),
                Oferta(fonte="promobit", canal="recentes-p1", id_externo="2", titulo="Robô Aspirador Dreame F10 Passa Pano", loja="Amazon",
                       preco_anunciado=1102.0, publicado_em=pub, texto="oferta"),
                Oferta(fonte="promobit", canal="recentes-p1", id_externo="3", titulo="Robô Aspirador KaBuM Smart K800 Pro 127V Preto", loja="KaBuM",
                       preco_anunciado=959.0, publicado_em=pub, texto="oferta"),
            ]
        r = regras(max_por_ciclo=2)
        with mock.patch("builtins.print"), mock.patch("radar.varredura.ranking.carregar_regras", return_value=r):
            varredura.executar(enviar=False, coletores={"promobit": fonte}, fontes_cfg={"promobit": {}}, agora=AGORA)
        linhas = self.con.execute("SELECT produto, score, estado FROM candidatos_alerta ORDER BY score DESC").fetchall()
        self.assertEqual([x["produto"] for x in linhas][:2], ["dreame_f10", "k800_pro_127v"])    # 45% e 24% de economia
        self.assertEqual([x["estado"] for x in linhas][:2], ["selecionado_sombra", "selecionado_sombra"])
        self.assertNotEqual(linhas[2]["estado"], "selecionado_sombra")                           # o Tapo (7% abaixo) ficou para depois


if __name__ == "__main__":
    unittest.main()
