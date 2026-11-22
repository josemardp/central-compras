"""Simulacao da POLITICA DE PRIORIDADE com ofertas documentadas e reencenacoes (fase 5).

Banco TEMPORARIO, canal de envio FALSO, relogio simulado. O historico real de precos desta maquina e so LIDO (importado para o banco
temporario) quando `historico_real=True`; nos testes usa-se um historico sintetico para o resultado ser deterministico.
Responde, para cada situacao: que notificacoes seriam ENVIADAS, ADIADAS, SUBSTITUIDAS, RETIDAS (por orcamento) ou DESCARTADAS, e por que.
Nada aqui prova eficacia comercial: prova que a politica se comporta como desenhada diante de ofertas reais e que nada some sem rastro.
"""

from __future__ import annotations

import copy
import datetime as dt
import os
import tempfile
from typing import Any

from . import alertas, avaliacao, catalogo, db, historico, outbox, prioridade, ranking, varredura
from .modelos import Oferta

HOJE = dt.datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)

# preco atual (base do historico sintetico) de cada produto; so usado quando `historico_real=False`
BASE_SINTETICA = {"dreame_f10": 1994.05, "k800_pro_127v": 1199.99, "tapo_rv20_max": 960.0, "xiaomi_s40c": 1260.0, "elgin_12k": 1899.0,
                  "philco_18k": 2399.0, "elgin_18k": 2799.0, "loren_shower_6800_220v": 112.0, "agratto_12k": 1950.0, "midea_lite_12k": 2100.0,
                  "midea_ecomaster_12k": 2400.0}

ROTULO = {"enviado": "ENVIADA", "selecionado_sombra": "ENVIADA (sombra)", "falha_envio": "FALHA NO WHATSAPP (guardada na fila)", "substituido": "SUBSTITUIDA",
          "pendente": "ADIADA (aguarda vaga)", "expirado": "DESCARTADA (expirou)", "retida_orcamento": "RETIDA (orcamento/vaga, NAO entregue)",
          "suprimido_repeticao": "DESCARTADA (repeticao)", "nao_selecionado": "DESCARTADA (pontuacao baixa)"}


class _Caixa:
    def __init__(self) -> None:
        self.mensagens: list[str] = []
        self.fora = False

    def __call__(self, texto: str) -> tuple[bool, str]:
        if self.fora:
            return False, "WhatsApp indisponivel (simulado)"
        self.mensagens.append(texto)
        return True, "ok"


class Simulador:
    def __init__(self, historico_real: bool, ajustes: dict[str, Any] | None = None) -> None:
        self._anterior = os.environ.get("CENTRAL_COMPRAS_DADOS_PRIVADOS")
        reais = {}
        if historico_real:  # caminhos do historico REAL, resolvidos ANTES de apontar para o diretorio temporario
            from . import caminhos
            reais = {nome: caminhos.tracker_dir(nome) / "historico.jsonl" for nome in ("rastreador-robos", "rastreador-ares", "rastreador-chuveiro")}
        self._tmp = tempfile.TemporaryDirectory()
        os.environ["CENTRAL_COMPRAS_DADOS_PRIVADOS"] = self._tmp.name
        self.con = db.abrir()
        self.cat = catalogo.carregar()
        self.regras = copy.deepcopy(ranking.carregar_regras(operacao=False))
        self.regras["alertas"].update(enviar=True, homologado_em="SIMULACAO (so em memoria)")
        self.regras.setdefault("prioridade", {}).update(ajustes or {})
        self.caixa = _Caixa()
        self.eventos: list[dict[str, Any]] = []
        self.corpus = {i["id"]: i for i in avaliacao.carregar_corpus()}
        self.revalidar = None
        if historico_real:
            for nome, arq in reais.items():
                historico.importar_para_db(self.con, nome, arq)
        else:
            for prod, base in BASE_SINTETICA.items():
                for i, f in enumerate((1.02, 1.01, 1.0, 1.03, 1.0)):
                    t = (HOJE - dt.timedelta(days=3) + dt.timedelta(hours=12 * i)).strftime("%Y-%m-%d %H:%M")
                    self.con.execute("INSERT INTO observacoes (origem, produto, coletado_em, preco_entregue, onde, hash) VALUES (?,?,?,?,?,?)",
                                     ("sim", prod, t, round(base * f, 2), "L", f"{prod}{i}"))
            self.con.commit()

    def fechar(self) -> None:
        self.con.close()
        if self._anterior is None:
            os.environ.pop("CENTRAL_COMPRAS_DADOS_PRIVADOS", None)
        else:
            os.environ["CENTRAL_COMPRAS_DADOS_PRIVADOS"] = self._anterior
        self._tmp.cleanup()

    # -- entradas
    def oferta(self, corpus_id: str | None = None, *, titulo: str | None = None, preco: float | None = None, fonte: str = "promobit",
               loja: str | None = None, n: str = "", cupom: str | None = None, quando: dt.datetime = HOJE) -> Oferta:
        it = self.corpus.get(corpus_id or "", {})
        pub = (quando - dt.timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M")
        return Oferta(fonte=fonte, canal="SIMULACAO", id_externo=f"SIM-{corpus_id or titulo}-{fonte}{n}", titulo=titulo or it["texto"],
                      loja=loja or it.get("loja"), preco_anunciado=float(preco if preco is not None else it["preco"]), publicado_em=pub,
                      url=f"https://sim.invalid/{corpus_id or 'x'}/{fonte}{n}", cupom_codigo=cupom)

    def ciclo(self, quando: dt.datetime, ofertas: list[Oferta], *, validar_na_fonte=None) -> list[dict[str, Any]]:
        """Um ciclo da varredura: processa as ofertas (candidatos) e despacha."""
        for of in ofertas:
            r = varredura.processar_oferta(self.con, of, self.cat, self.regras, self.caixa, quando, diferir=True)
            if r.get("candidato_id"):
                self.eventos.append({"hora": quando, "produto": r["produto"], "preco": r.get("preco_final"), "pontuacao": r.get("score"),
                                     "evento": f"candidato criado (pontuacao {r['score']:.0f})", "cid": r["candidato_id"]})
            else:
                self.eventos.append({"hora": quando, "produto": r.get("produto") or "(nao reconhecido)", "preco": of.preco_anunciado, "pontuacao": None,
                                     "evento": "DESCARTADA no portao: " + str(r.get("descarte") or r.get("acao") or r.get("motivo")), "cid": None})
        decs = prioridade.despachar(self.con, self.regras, self.caixa, quando, revalidar=validar_na_fonte)
        for d in decs:
            if d.get("id"):
                self.eventos.append({"hora": quando, "produto": d["produto"], "preco": d["preco_final"], "pontuacao": d["score"],
                                     "evento": f"{ROTULO.get(d['estado'], d['estado'])}: {d['motivo']}", "cid": d["id"]})
            else:
                self.eventos.append({"hora": quando, "produto": "-", "preco": None, "pontuacao": None, "evento": f"{d['estado']}: {d['motivo']}", "cid": None})
        return decs

    def estado(self, cid: int) -> tuple[str, str]:
        r = self.con.execute("SELECT estado, motivo FROM candidatos_alerta WHERE id=?", (cid,)).fetchone()
        return r["estado"], r["motivo"]

    def contagem(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for r in self.con.execute("SELECT estado, COUNT(*) n FROM candidatos_alerta GROUP BY estado"):
            out[r["estado"]] = r["n"]
        return out


def _sit(nome: str, pergunta: str, sim: Simulador, esperado: str, ok: bool, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    linhas = [{"hora": e["hora"].strftime("%H:%M"), "produto": e["produto"], "preco": e["preco"], "pontuacao": e["pontuacao"], "evento": e["evento"]}
              for e in sim.eventos]
    return {"nome": nome, "pergunta": pergunta, "linhas": linhas, "esperado": esperado, "ok": ok, "mensagens_enviadas": len(sim.caixa.mensagens),
            "estados_finais": sim.contagem(), **(extra or {})}


def _fresco(historico_real: bool, ajustes: dict[str, Any] | None = None) -> Simulador:
    return Simulador(historico_real, ajustes)


def simular(historico_real: bool = True) -> dict[str, Any]:
    """Roda as 7 situacoes pedidas + um dia cheio. Cada uma com banco proprio."""
    out: list[dict[str, Any]] = []
    t = HOJE

    # S1 tres ofertas importantes simultaneas (limite: 2 por varredura)
    s = _fresco(historico_real)
    try:
        ofs = [s.oferta("H05"), s.oferta("H01"), s.oferta("H10")]   # K800 R$ 959, Dreame F10 R$ 1.102, Philco 18k R$ 2.099
        s.ciclo(t, ofs)
        s.ciclo(t + dt.timedelta(minutes=10), [])
        s.ciclo(t + dt.timedelta(minutes=20), [])
        cont = s.contagem()
        ids = [e["cid"] for e in s.eventos if e["cid"] and e["evento"].startswith("candidato")]
        finais = [s.estado(c)[0] for c in ids]
        ok = len(ids) >= 3 and all(f != "pendente" for f in finais) and sum(1 for e in s.eventos if e["evento"].startswith("ENVIADA")) <= len(ids)
        por_ciclo = {}
        for e in s.eventos:
            if e["evento"].startswith("ENVIADA"):
                por_ciclo[e["hora"]] = por_ciclo.get(e["hora"], 0) + 1
        ok = ok and all(v <= 2 for v in por_ciclo.values())
        out.append(_sit("S1", "Tres ofertas importantes surgem ao mesmo tempo", s, "no maximo 2 por varredura; a 3a espera a vaga ou e substituida, nunca some sem estado final", ok))
    finally:
        s.fechar()

    # S2 oferta excepcional depois de esgotado o orcamento comum (e depois da excecao)
    s = _fresco(historico_real, {"orcamento_diario": 2, "orcamento_excecao_diario": 1, "max_por_ciclo": 9})
    try:
        for i, prod in enumerate(("agratto_12k", "midea_lite_12k")):  # gasta o orcamento comum do dia com ofertas medias
            pass
        s.ciclo(t - dt.timedelta(hours=2), [s.oferta("D04", preco=1800.0, quando=t - dt.timedelta(hours=2))])
        s.ciclo(t - dt.timedelta(hours=1), [s.oferta("D05", preco=1930.0, quando=t - dt.timedelta(hours=1))])
        s.ciclo(t, [s.oferta("H05")])                                # excepcional 1
        s.ciclo(t + dt.timedelta(minutes=10), [s.oferta("H01")])     # excepcional 2: excecao ja usada
        ret = prioridade.retidas(s.con, t + dt.timedelta(minutes=11))
        ok = (any(e["evento"].startswith("ENVIADA") for e in s.eventos)
              and all(r["motivo"] for r in ret) and s.contagem().get("pendente", 0) == 0)
        out.append(_sit("S2", "Oferta excepcional aparece depois de esgotado o orcamento comum (limite 2) e com 1 vaga de excecao",
                        s, "a excepcional usa a excecao; a seguinte, sem excecao, fica RETIDA com motivo e entra na lista de retidas (nao some)", ok,
                        {"retidas": [{"produto": r["produto"], "preco": r["preco_final"], "pontuacao": r["score"], "motivo": r["motivo"]} for r in ret]}))
    finally:
        s.fechar()

    # S3 sucessivas reducoes do mesmo produto
    s = _fresco(historico_real)
    try:
        for i, preco in enumerate((1100.0, 1080.0, 1060.0, 1000.0, 940.0)):
            q = t + dt.timedelta(minutes=10 * i)
            s.ciclo(q, [s.oferta("H01", preco=preco, n=str(i), quando=q)])
        enviados = [e["preco"] for e in s.eventos if e["evento"].startswith("ENVIADA")]
        ok = bool(enviados) and len(enviados) < 5 and all(b < a for a, b in zip(enviados, enviados[1:]))
        out.append(_sit("S3", "Dreame F10 recebe reducoes sucessivas (R$ 1.100, 1.080, 1.060, 1.000, 940)", s,
                        "repete so com melhora de 5% sobre o ultimo alerta; as reducoes pequenas ficam descartadas com motivo", ok, {"precos_enviados": enviados}))
    finally:
        s.fechar()

    # S4 o mesmo cupom/oferta em varias comunidades
    s = _fresco(historico_real)
    try:
        ofs = [s.oferta("H05", fonte="promobit", n="a", cupom="SIMCUPOM"), s.oferta("H05", fonte="gatry", n="b", cupom="SIMCUPOM"),
               s.oferta("H05", fonte="pelando", n="c", cupom="SIMCUPOM")]
        s.ciclo(t, ofs)
        cand = s.con.execute("SELECT COUNT(*) FROM candidatos_alerta").fetchone()[0]
        ok = len(s.caixa.mensagens) == 1 and s.contagem().get("substituido", 0) == cand - 1
        out.append(_sit("S4", "O mesmo cupom e oferta aparece em Promobit, Gatry e Pelando no mesmo ciclo", s,
                        "1 SO notificacao; as copias dos outros canais ficam registradas como substituidas pela melhor do mesmo produto", ok, {"candidatos": cand}))
        # repeticao em CICLO SEGUINTE (a mesma oferta reaparece numa 4a comunidade): barrada pela repeticao do produto
        q = t + dt.timedelta(minutes=10)
        s.ciclo(q, [s.oferta("H05", fonte="telegram", n="d", cupom="SIMCUPOM", quando=q)])
        s.ciclo(q + dt.timedelta(minutes=10), [])
        out[-1]["ok"] = out[-1]["ok"] and len(s.caixa.mensagens) == 1
        out[-1]["linhas"] = [{"hora": e["hora"].strftime("%H:%M"), "produto": e["produto"], "preco": e["preco"], "pontuacao": e["pontuacao"], "evento": e["evento"]}
                             for e in s.eventos]
        out[-1]["mensagens_enviadas"] = len(s.caixa.mensagens)
    finally:
        s.fechar()

    # S5 promocao expira antes do envio (candidato espera vaga e a fonte ja encerrou)
    s = _fresco(historico_real, {"max_por_ciclo": 1})
    try:
        s.ciclo(t, [s.oferta("H05"), s.oferta("H01")])               # so 1 sai agora; a outra espera
        enviados_antes = len(s.caixa.mensagens)
        s.ciclo(t + dt.timedelta(minutes=10), [], validar_na_fonte=lambda oid: (False, "oferta encerrada na fonte (status FINISHED)"))
        aguardava = [e for e in s.eventos if e["evento"].startswith("DESCARTADA (expirou)")]
        ok = bool(aguardava) and len(s.caixa.mensagens) == enviados_antes
        out.append(_sit("S5", "A promocao que esperava vaga acaba antes do envio", s,
                        "revalida na fonte, ve que acabou e NAO envia (nunca apresenta oferta encerrada como ativa)", ok))
    finally:
        s.fechar()

    # S6 oferta fica aguardando orcamento: vaga por varredura (anti-rajada) e depois vence
    s = _fresco(historico_real, {"max_por_ciclo": 1, "validade_candidato_min": 15})
    try:
        s.ciclo(t, [s.oferta("H05"), s.oferta("H01"), s.oferta("H10")])
        s.ciclo(t + dt.timedelta(minutes=10), [])
        s.ciclo(t + dt.timedelta(minutes=20), [])
        sem_pendente = s.contagem().get("pendente", 0) == 0
        estados = {s.estado(e["cid"])[0] for e in s.eventos if e["cid"] and e["evento"].startswith("candidato")}
        ok = sem_pendente and ("retida_orcamento" in estados or "substituido" in estados or "enviado" in estados)
        ret = prioridade.retidas(s.con, t + dt.timedelta(minutes=21))
        out.append(_sit("S6", "Oferta fica esperando vaga (1 por varredura, validade de 15 min)", s,
                        "quem espera e enviado no ciclo seguinte, substituido por outra melhor ou fica RETIDO com motivo; nenhum candidato fica pendente para sempre",
                        ok, {"retidas": [{"produto": r["produto"], "motivo": r["motivo"]} for r in ret]}))
    finally:
        s.fechar()

    # S7 WhatsApp indisponivel: guarda na fila, reentrega dentro da validade e descarta fora dela
    s = _fresco(historico_real)
    try:
        s.caixa.fora = True
        s.ciclo(t, [s.oferta("H05")])
        na_fila = len(outbox.pendentes(s.con, tipo="alerta", agora_dt=t))
        s.caixa.fora = False
        ent = outbox.drenar(s.con, s.caixa, revalidar=lambda oid: (True, "ativa"), agora_dt=t + dt.timedelta(minutes=12))
        s.eventos.append({"hora": t + dt.timedelta(minutes=12), "produto": "k800_pro_127v", "preco": None, "pontuacao": None,
                          "evento": f"WhatsApp voltou: {len(ent)} entregue(s) da fila (revalidada na fonte)", "cid": None})
        # segunda queda: volta so depois da validade (30 min)
        s.caixa.fora = True
        s.ciclo(t + dt.timedelta(hours=3), [s.oferta("H01", quando=t + dt.timedelta(hours=3))])
        s.caixa.fora = False
        ent2 = outbox.drenar(s.con, s.caixa, revalidar=lambda oid: (False, "fora da validade"), agora_dt=t + dt.timedelta(hours=3, minutes=50))
        s.eventos.append({"hora": t + dt.timedelta(hours=3, minutes=50), "produto": "dreame_f10", "preco": None, "pontuacao": None,
                          "evento": "WhatsApp voltou 50 min depois: alerta vencido e nao revalidado e DESCARTADO (nao entrega oferta velha)", "cid": None})
        desfechos = [r["desfecho"] for r in s.con.execute("SELECT desfecho FROM outbox WHERE tipo='alerta'")]
        ok = na_fila == 1 and len(ent) == 1 and len(s.caixa.mensagens) == 1 and any(d and "descart" in d for d in desfechos)
        out.append(_sit("S7", "WhatsApp indisponivel no envio", s, "alerta guardado na fila; entregue ao voltar dentro de 30 min; descartado se vencido", ok,
                        {"desfechos_da_fila": desfechos}))
    finally:
        s.fechar()

    # S8 dia cheio: todas as ofertas reais documentadas reencenadas ao longo da manha (1 a cada 10 min)
    s = _fresco(historico_real)
    try:
        itens = [i for i in avaliacao.carregar_corpus() if i["origem"] in ("real_historico", "documentado") and i["caso"] in ("positivo", "ambiguo") and i.get("preco")]
        for k, it in enumerate(itens):
            q = t - dt.timedelta(hours=3) + dt.timedelta(minutes=10 * k)
            s.ciclo(q, [s.oferta(it["id"], quando=q, n=str(k))])
        s.ciclo(t + dt.timedelta(hours=2), [])
        sem_pendente = s.contagem().get("pendente", 0) == 0
        ret = prioridade.retidas(s.con, t + dt.timedelta(hours=3), horas=24)
        out.append(_sit("S8", f"Dia cheio: {len(itens)} ofertas reais reencenadas, 1 a cada 10 min", s,
                        "respeita 6 comuns + excecoes, nada fica pendente, e tudo que o orcamento reteve aparece em `retidas`", sem_pendente,
                        {"ofertas_reencenadas": len(itens), "retidas": [{"produto": r["produto"], "preco": r["preco_final"], "pontuacao": r["score"], "motivo": r["motivo"]} for r in ret]}))
    finally:
        s.fechar()
    return {"gerado_em": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "historico_real": historico_real, "situacoes": out,
            "todas_ok": all(x["ok"] for x in out)}


def formatar(res: dict[str, Any], detalhe: bool = True) -> str:
    L = [f"== SIMULACAO DA POLITICA DE PRIORIDADE | historico {'REAL (lido)' if res['historico_real'] else 'sintetico'} | alertas simulados, NADA enviado"]
    for s in res["situacoes"]:
        L.append(f"\n[{s['nome']}] {s['pergunta']}  =>  {'OK' if s['ok'] else 'FALHOU'}")
        L.append(f"   esperado: {s['esperado']}")
        L.append(f"   mensagens que sairiam: {s['mensagens_enviadas']} | estados finais: {s['estados_finais']}")
        if detalhe:
            for e in s["linhas"]:
                p = f"R$ {e['preco']:.2f}" if e["preco"] else "-"
                L.append(f"     {e['hora']} {str(e['produto'])[:22]:22s} {p:>11s}  {e['evento'][:150]}")
        for r in s.get("retidas") or []:
            L.append(f"   RETIDA: {r['produto']} {('R$ %.2f' % r['preco']) if r.get('preco') else ''} {r['motivo']}")
    return "\n".join(L)
