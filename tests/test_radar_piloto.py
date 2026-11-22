"""MODO PILOTO (radar/piloto.py): SOMBRA nunca envia; PILOTO so envia o que passa em todas as barreiras e com limites bem menores."""

import copy
import datetime as dt
import json
import os
import tempfile
import unittest
from unittest import mock

from radar import db, piloto, prioridade, ranking

AGORA = dt.datetime(2026, 11, 22, 10, 0)


def regras(modo="PILOTO", **pil):
    r = copy.deepcopy(ranking.carregar_regras())
    r["alertas"].update(enviar=modo != "SOMBRA", homologado_em="2026-11-22 09:00" if modo != "SOMBRA" else None)
    r["prioridade"]["limiar_ultimo_comum"] = 40
    r["piloto"] = {**r.get("piloto", {}), "ativo": modo == "PILOTO", "destinatario_confirmado_em": "2026-11-22 09:30", **pil}
    return r


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
        self.addCleanup(self._tmp.cleanup)
        self.addCleanup(lambda: self.con.close())
        self.addCleanup(p.stop)
        self.con = db.abrir()
        self.n = 0

    def cand(self, produto="k800_pro_127v", score=80.0, classe="ALTA", preco=1000.0, confianca="ALTA", avisos=(), url="https://x/1", hora_incerta=False,
             quando=AGORA, oferta_id=None, r=None):
        self.n += 1
        comp = {"economia_reais": 100.0, "economia_pct": 10.0, "confianca": [confianca, ["motivo"]], "avisos": list(avisos)}
        return prioridade.registrar_candidato(
            self.con, oferta_id=oferta_id, produto=produto, loja="L", vendedor=None, classe=classe, score=score, componentes=comp, preco_final=preco,
            status_cupom="PROVAVEL", cupom=None, fonte="promobit", hora_incerta=hora_incerta, mensagem=f"MSG {produto} {self.n}", url=url,
            regras=r or regras(), agora=quando)

    def estado(self, cid):
        x = self.con.execute("SELECT estado, motivo FROM candidatos_alerta WHERE id=?", (cid,)).fetchone()
        return x["estado"], x["motivo"]


class ModoTest(unittest.TestCase):
    def test_tres_modos(self):
        self.assertEqual(piloto.modo(regras("SOMBRA")), "SOMBRA")
        self.assertEqual(piloto.modo(regras("PILOTO")), "PILOTO")
        self.assertEqual(piloto.modo(regras("COMPLETO")), "COMPLETO")

    def test_piloto_ativo_sem_enviar_continua_sombra(self):
        r = regras("PILOTO")
        r["alertas"].update(enviar=False)
        self.assertEqual(piloto.modo(r), "SOMBRA")
        r = regras("PILOTO")
        r["alertas"].update(homologado_em=None)
        self.assertEqual(piloto.modo(r), "SOMBRA")

    def test_configuracao_real_esta_em_sombra_e_o_piloto_e_conservador(self):
        # O arquivo VERSIONADO (o que vai ao GitHub e o que uma instalacao nova recebe) e sempre SOMBRA; a ativacao vive so no
        # estado operacional local (operacao.yaml), por isso aqui se le sem a camada local. Serve de trava contra commitar a ativacao.
        real = ranking.carregar_regras(operacao=False)
        self.assertEqual(piloto.modo(real), "SOMBRA")
        pil = piloto.config(real)
        self.assertFalse(pil["ativo"])
        dest = pil["destinatario_confirmado_em"]                 # preenchido por ordem do usuario (21/11 21:21); se um dia voltar a vazio, tambem vale
        self.assertTrue(dest is None or __import__("datetime").datetime.strptime(str(dest), "%Y-%m-%d %H:%M"))
        self.assertFalse(real["alertas"]["enviar"] or real["alertas"]["homologado_em"])   # o destinatario confirmado NAO liga nada: segue SOMBRA
        self.assertTrue(all(pil[k] <= t for k, t in piloto.TETO_CONSERVADOR.items()))
        self.assertNotIn("xiaomi_s40_pro_py", pil["produtos_exatos"])     # produto em USD (Paraguai) fora do piloto
        self.assertLess(pil["orcamento_diario"], real["prioridade"]["orcamento_diario"])


class BarreirasTest(Base):
    def passa(self, **kw):
        cid = self.cand(**kw)
        row = self.con.execute("SELECT * FROM candidatos_alerta WHERE id=?", (cid,)).fetchone()
        return piloto.avaliar_candidato(row, piloto.config(regras()))

    def test_candidato_limpo_passa(self):
        self.assertEqual(self.passa(), (True, "dentro do piloto"))

    def test_cada_barreira_bloqueia_com_motivo(self):
        casos = {
            "produto fora da lista": dict(produto="xiaomi_s40_pro_py"),
            "confianca BAIXA": dict(confianca="BAIXA"),
            "aviso de voltagem": dict(avisos=["tensao_nao_informada"]),
            "cupom nao confirmado": dict(avisos=["preco_depende_de_cupom_nao_confirmado"]),
            "hora incerta": dict(hora_incerta=True),
            "sem link": dict(url=None),
        }
        for nome, kw in casos.items():
            ok, motivo = self.passa(**kw)
            self.assertFalse(ok, nome)
            self.assertTrue(motivo, nome)

    def test_confianca_media_passa_com_minima_media_e_nao_com_minima_alta(self):
        cid = self.cand(confianca="MEDIA")
        row = self.con.execute("SELECT * FROM candidatos_alerta WHERE id=?", (cid,)).fetchone()
        self.assertTrue(piloto.avaliar_candidato(row, piloto.config(regras()))[0])
        self.assertFalse(piloto.avaliar_candidato(row, piloto.config(regras(confianca_minima="ALTA")))[0])

    def test_sem_destinatario_confirmado_nada_passa(self):
        cid = self.cand()
        row = self.con.execute("SELECT * FROM candidatos_alerta WHERE id=?", (cid,)).fetchone()
        ok, motivo = piloto.avaliar_candidato(row, piloto.config(regras(destinatario_confirmado_em=None)))
        self.assertFalse(ok)
        self.assertIn("NAO confirmado", motivo)


class DespachoNoPilotoTest(Base):
    def test_piloto_envia_o_limpo_e_registra_o_resto_como_fora_do_piloto(self):
        caixa = Caixa()
        bom = self.cand(produto="k800_pro_127v", score=85)
        aviso = self.cand(produto="philco_18k", score=90, avisos=["preco_depende_de_cupom_nao_confirmado"], confianca="MEDIA")
        outro = self.cand(produto="xiaomi_s40_pro_py", score=95)
        prioridade.despachar(self.con, regras(), caixa, AGORA)
        self.assertEqual(self.estado(bom)[0], "enviado")
        self.assertEqual(self.estado(aviso)[0], "nao_selecionado")
        self.assertIn("fora do piloto: ha avisos", self.estado(aviso)[1])
        self.assertIn("fora do piloto: produto xiaomi_s40_pro_py", self.estado(outro)[1])
        self.assertEqual(len(caixa.msgs), 1)

    def test_limites_do_piloto_sao_bem_menores_que_os_da_politica_completa(self):
        caixa = Caixa()
        ids = [self.cand(produto=p, score=80 - i) for i, p in enumerate(("k800_pro_127v", "dreame_f10", "tapo_rv20_max", "elgin_12k"))]
        prioridade.despachar(self.con, regras(), caixa, AGORA)                                 # 1 por varredura
        self.assertEqual(len(caixa.msgs), 1)
        prioridade.despachar(self.con, regras(), caixa, AGORA + dt.timedelta(minutes=10))
        self.assertEqual(len(caixa.msgs), 2)
        prioridade.despachar(self.con, regras(), caixa, AGORA + dt.timedelta(minutes=20))      # orcamento diario de 2 acabou
        self.assertEqual(len(caixa.msgs), 2)
        self.assertEqual({self.estado(i)[0] for i in ids} - {"enviado", "substituido"}, {"retida_orcamento"})

    def test_mesma_oferta_nao_se_repete_dentro_de_4_horas_sem_melhora_de_7_por_cento(self):
        caixa = Caixa()
        self.cand(produto="k800_pro_127v", preco=1000.0)
        prioridade.despachar(self.con, regras(), caixa, AGORA)
        t = AGORA + dt.timedelta(minutes=60)
        igual = self.cand(produto="k800_pro_127v", preco=960.0, quando=t)                        # 4% melhor: nao basta
        prioridade.despachar(self.con, regras(), caixa, t)
        self.assertEqual(self.estado(igual)[0], "suprimido_repeticao")
        t2 = AGORA + dt.timedelta(minutes=90)
        melhor = self.cand(produto="k800_pro_127v", preco=900.0, quando=t2)                       # 10% melhor: passa
        prioridade.despachar(self.con, regras(), caixa, t2)
        self.assertEqual(self.estado(melhor)[0], "enviado")

    def test_fonte_e_revalidada_sempre_no_piloto_mesmo_com_candidato_recem_criado(self):
        caixa = Caixa()
        cid = self.cand(oferta_id=7)
        chamadas = []
        prioridade.despachar(self.con, regras(), caixa, AGORA, revalidar=lambda oid: (chamadas.append(oid) or (False, "encerrada na fonte (FINISHED)")))
        self.assertEqual(chamadas, [7])                      # na politica completa so revalida quem esperou mais de 5 min
        self.assertEqual(self.estado(cid)[0], "expirado")
        self.assertEqual(caixa.msgs, [])

    def test_na_politica_completa_candidato_recem_criado_nao_e_revalidado(self):
        caixa = Caixa()
        self.cand(oferta_id=7)
        chamadas = []
        prioridade.despachar(self.con, regras("COMPLETO"), caixa, AGORA, revalidar=lambda oid: (chamadas.append(oid) or (True, "ativa")))
        self.assertEqual(chamadas, [])
        self.assertEqual(len(caixa.msgs), 1)

    def test_em_sombra_com_piloto_ativo_nada_e_enviado(self):
        caixa = Caixa()
        r = regras("SOMBRA")
        r["piloto"]["ativo"] = True
        cid = self.cand()
        prioridade.despachar(self.con, r, caixa, AGORA)
        self.assertEqual((self.estado(cid)[0], caixa.msgs), ("selecionado_sombra", []))

    def test_painel_mostra_modo_limites_e_o_que_ficou_fora(self):
        self.cand(produto="xiaomi_s40_pro_py")
        prioridade.despachar(self.con, regras(), Caixa(), AGORA)
        txt = piloto.painel(self.con, regras(), AGORA)
        for trecho in ("modo atual: PILOTO", "2 comum + 1 critico + 0 excecao", "fora do piloto: xiaomi_s40_pro_py", "ativacao --desligar"):
            self.assertIn(trecho, txt)


class TetoTotalPorVarreduraTest(Base):
    """Decisao do Josemar (21/11): orcamento 2 comuns + 1 critico por dia, mas UM alerta por varredura no TOTAL. Critico tem preferencia."""

    def ciclo(self, minutos, caixa, r=None):
        decs = prioridade.despachar(self.con, r or regras(), caixa, AGORA + dt.timedelta(minutes=minutos))
        return [(d["produto"], d["classe"]) for d in decs if d.get("estado") == "enviado"]

    def test_critico_tem_preferencia_mesmo_com_pontuacao_menor_e_o_comum_espera(self):
        caixa = Caixa()
        comum = self.cand(produto="dreame_f10", classe="ALTA", score=90)
        crit = self.cand(produto="k800_pro_127v", classe="CRITICA", score=70)
        self.assertEqual(self.ciclo(0, caixa), [("k800_pro_127v", "CRITICA")])           # so 1 na varredura, e e o critico
        self.assertEqual(self.estado(comum), ("pendente", "aguardando vaga no proximo ciclo"))
        self.assertEqual(self.estado(crit)[0], "enviado")
        self.assertEqual(self.ciclo(10, caixa), [("dreame_f10", "ALTA")])               # o comum sai no ciclo seguinte
        self.assertEqual(len(caixa.msgs), 2)

    def test_comum_nao_e_apagado_por_um_critico_muito_melhor_so_espera(self):
        caixa = Caixa()
        comum = self.cand(produto="dreame_f10", classe="ALTA", score=55)
        self.cand(produto="k800_pro_127v", classe="CRITICA", score=98)                   # 43 pontos acima: na politica completa substituiria
        self.ciclo(0, caixa)
        self.assertEqual(self.estado(comum)[0], "pendente")                             # aqui NAO substitui: categorias diferentes
        self.assertEqual(self.ciclo(10, caixa), [("dreame_f10", "ALTA")])

    def test_comum_muito_inferior_a_outro_comum_selecionado_continua_sendo_substituido(self):
        caixa = Caixa()
        fraco = self.cand(produto="dreame_f10", classe="ALTA", score=50)
        self.cand(produto="k800_pro_127v", classe="ALTA", score=90)
        self.ciclo(0, caixa)
        self.assertEqual(self.estado(fraco)[0], "substituido")                          # mesma categoria: vale a prioridade

    def test_nunca_mais_de_um_por_varredura_e_o_dia_fecha_em_2_comuns_mais_1_critico(self):
        caixa = Caixa()
        for p, c, s in (("dreame_f10", "ALTA", 90), ("k800_pro_127v", "ALTA", 85), ("tapo_rv20_max", "ALTA", 80), ("xiaomi_s40c", "CRITICA", 95), ("elgin_12k", "CRITICA", 92)):
            self.cand(produto=p, classe=c, score=s)
        por_ciclo = [self.ciclo(10 * i, caixa) for i in range(8)]
        self.assertTrue(all(len(x) <= 1 for x in por_ciclo), por_ciclo)
        enviados = [e for x in por_ciclo for e in x]
        self.assertEqual(sorted(c for _, c in enviados), ["ALTA", "ALTA", "CRITICA"])   # orcamento do dia preservado: 2 comuns + 1 critico
        self.assertEqual(enviados[0][1], "CRITICA")                                     # o critico saiu primeiro

    def test_comum_que_esperou_alem_da_validade_fica_retido_e_visivel(self):
        caixa = Caixa()
        r = regras(orcamento_critico_diario=9)
        r["prioridade"]["validade_candidato_min"] = 15                                    # o candidato comum vence em 15 min
        comum = self.cand(produto="dreame_f10", classe="ALTA", score=70, r=r)
        for i, p in enumerate(("k800_pro_127v", "tapo_rv20_max")):                       # criticos novos a cada ciclo ocupam a vaga unica
            self.cand(produto=p, classe="CRITICA", score=90, r=r, quando=AGORA + dt.timedelta(minutes=10 * i))
            self.ciclo(10 * i, caixa, r)
        self.assertEqual(self.estado(comum)[0], "pendente")
        self.ciclo(20, caixa, r)                                                          # 20 min: o comum ja venceu esperando
        self.assertEqual(self.estado(comum)[0], "retida_orcamento")
        self.assertIn("venceu aguardando vaga", self.estado(comum)[1])
        self.assertEqual([x["produto"] for x in prioridade.retidas(self.con, AGORA + dt.timedelta(minutes=21))], ["dreame_f10"])

    def test_orcamento_e_deduplicacao_continuam_valendo_com_o_teto_total(self):
        caixa = Caixa()
        self.cand(produto="dreame_f10", classe="ALTA", score=90, preco=1000.0)
        self.assertEqual(self.ciclo(0, caixa), [("dreame_f10", "ALTA")])
        repetido = self.cand(produto="dreame_f10", classe="ALTA", score=90, preco=980.0, quando=AGORA + dt.timedelta(minutes=10))
        self.assertEqual(self.ciclo(10, caixa), [])
        self.assertEqual(self.estado(repetido)[0], "suprimido_repeticao")              # 2% melhor, dentro de 4 h: deduplicado

    def test_politica_completa_nao_mudou_comum_e_critico_saem_juntos(self):
        caixa = Caixa()
        self.cand(produto="dreame_f10", classe="ALTA", score=90, r=regras("COMPLETO"))
        self.cand(produto="k800_pro_127v", classe="CRITICA", score=70, r=regras("COMPLETO"))
        self.assertEqual(len(self.ciclo(0, caixa, regras("COMPLETO"))), 2)

    def test_configuracao_real_do_piloto_tem_teto_total_de_1(self):
        self.assertEqual(piloto.config(ranking.carregar_regras())["max_total_por_ciclo"], 1)
        self.assertEqual(prioridade.config(ranking.carregar_regras()).get("max_total_por_ciclo"), None)   # politica completa sem teto total


if __name__ == "__main__":
    unittest.main()
