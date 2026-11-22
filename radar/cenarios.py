"""Homologacao da cadeia de alerta com cenarios SINTETICOS claramente identificados (ids `SINT-*`).

Roda o codigo de producao (varredura.processar_oferta, alertas, outbox, revalidacao) em um banco TEMPORARIO.
A ativacao dos alertas existe SO em memoria, dentro desta execucao: config/radar_regras.yaml nao e tocado e o banco real nao e aberto.
Por padrao nada e enviado ao WhatsApp. `enviar_teste_whatsapp=True` envia UMA mensagem rotulada como teste ao seu proprio chat.
"""

from __future__ import annotations

import copy
import datetime as dt
import os
import tempfile
from typing import Any

from . import alertas, catalogo, db, historico, outbox, ranking, varredura
from .fontes.base import FonteErroRede
from .modelos import Oferta

AGORA = dt.datetime(2026, 11, 21, 10, 0)  # horario de alerta (07:00-23:00); fixo para o resultado ser reprodutivel


def _semear(con, produto: str, precos: list[float]) -> None:
    for i, p in enumerate(precos):
        t = (AGORA - dt.timedelta(days=3) + dt.timedelta(hours=12 * i)).strftime("%Y-%m-%d %H:%M")
        con.execute("INSERT INTO observacoes (origem, produto, coletado_em, preco_entregue, onde, hash) VALUES (?,?,?,?,?,?)",
                    ("SINTETICO", produto, t, p, "serie sintetica", f"sint-{produto}-{i}"))
    con.commit()


def _oferta(i: str, titulo: str, preco: float, loja: str = "KaBuM!", texto: str = "", minutos: int = 20, **kw) -> Oferta:
    pub = (AGORA - dt.timedelta(minutes=minutos)).strftime("%Y-%m-%d %H:%M")
    return Oferta(fonte="promobit", canal="SINTETICO", id_externo=f"SINT-{i}", titulo=titulo, texto=texto, loja=loja,
                  preco_anunciado=preco, url=f"https://exemplo.invalido/sint-{i}", publicado_em=pub, **kw)


class _Caixa:
    """Canal de saida falso: guarda o que SERIA enviado."""

    def __init__(self) -> None:
        self.mensagens: list[str] = []
        self.falhar = False

    def __call__(self, texto: str) -> tuple[bool, str]:
        if self.falhar:
            return False, "canal indisponivel (simulado)"
        self.mensagens.append(texto)
        return True, "capturado (simulado)"


def _linha(cid: str, nome: str, esperado: str, obtido: str, ok: bool, extra: str = "") -> dict[str, Any]:
    return {"id": cid, "cenario": nome, "esperado": esperado, "obtido": obtido, "ok": bool(ok), "detalhe": extra}


def executar_cenarios(enviar_teste_whatsapp: bool = False) -> dict[str, Any]:
    anterior = os.environ.get("CENTRAL_COMPRAS_DADOS_PRIVADOS")
    abertas: list = []
    try:
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["CENTRAL_COMPRAS_DADOS_PRIVADOS"] = tmp
            try:
                return _rodar(enviar_teste_whatsapp, abertas)
            except Exception as exc:  # noqa: BLE001 - um cenario que quebra e um cenario REPROVADO, nao um crash silencioso
                return {"cenarios": [_linha("ERRO", "excecao durante os cenarios", "nenhuma", f"{type(exc).__name__}: {str(exc)[:160]}", False)],
                        "ok": False, "total": 1, "aprovados": 0, "alerta_exemplo": "", "envio_teste": None, "historico_semente": {}}
            finally:
                for c in abertas:  # no Windows a pasta temporaria so some com as conexoes fechadas
                    try:
                        c.close()
                    except Exception:  # noqa: BLE001
                        pass
    finally:
        if anterior is None:
            os.environ.pop("CENTRAL_COMPRAS_DADOS_PRIVADOS", None)
        else:
            os.environ["CENTRAL_COMPRAS_DADOS_PRIVADOS"] = anterior


def _rodar(enviar_teste: bool, abertas: list) -> dict[str, Any]:
    con = db.abrir()
    abertas.append(con)
    cat = catalogo.carregar()
    real = ranking.carregar_regras(operacao=False)  # sintetico: independe da ativacao viva
    regras = copy.deepcopy(real)
    regras["alertas"].update(enviar=True, homologado_em="SINTETICO (so em memoria)")
    _semear(con, "k800_pro_127v", [1250.0, 1230.0, 1199.98, 1240.0, 1260.0])
    _semear(con, "elgin_12k", [1899.0, 1880.0, 1865.6, 1890.0, 1905.0])
    caixa = _Caixa()
    L: list[dict[str, Any]] = []

    def proc(o: Oferta, r=regras, fn=caixa, quando: dt.datetime = AGORA) -> dict[str, Any]:
        return varredura.processar_oferta(con, o, cat, r, fn, quando)

    # S01 cupom valido (evidencia recente de funcionamento -> PROVAVEL; nunca VALIDADO por inferencia)
    r = proc(_oferta("01", "[SINTETICO] Robô Aspirador KaBuM Smart K800 Pro 127V Preto", 1099.0, "KaBuM!",
                     "cupom CASATECH10 10% de desconto, funcionando, consegui aplicar"))
    msg01 = caixa.mensagens[-1] if caixa.mensagens else ""
    L.append(_linha("S01", "cupom valido + preco abaixo do minimo historico", "ALTA, alerta enviado, status PROVAVEL, preco 'estimado'",
                    f"{r.get('classe')}, {r.get('acao')}, {r.get('validacao')}, preco_final {r.get('preco_final')}",
                    r.get("produto") == "k800_pro_127v" and r.get("classe") == "ALTA" and str(r.get("acao")).startswith("real")
                    and "Status: PROVAVEL" in msg01 and "(estimado)" in msg01 and "Confirme preço" in msg01
                    and "SEM frete" in msg01 and "Preço final entregue" not in msg01))  # a fonte sintetica nao informa frete

    # S01b frete conhecido ("frete gratis" no texto) => ai sim "entregue"
    n = len(caixa.mensagens)
    r = proc(_oferta("01b", "[SINTETICO] Robô Aspirador KaBuM Smart K800 Pro 127V Preto", 1090.0, "Americanas",
                     "cupom CASATECH10 10% de desconto, funcionando, consegui aplicar. Frete grátis"))
    msg01b = caixa.mensagens[-1] if len(caixa.mensagens) > n else ""
    L.append(_linha("S01b", "frete conhecido (frete gratis no texto)", "rotulo 'Preço final entregue'",
                    f"{r.get('acao')}", "Preço final entregue" in msg01b and "SEM frete" not in msg01b))

    # S02 cupom expirado
    n = len(caixa.mensagens)
    r = proc(_oferta("02", "[SINTETICO] Robô Aspirador KaBuM Smart K800 Pro 127V Preto", 1099.0, "Loja Dois",
                     "cupom CASATECH10 expirou, não funciona mais"))
    L.append(_linha("S02", "cupom expirado", "BAIXA, nenhuma mensagem", f"{r.get('classe')}, {r.get('acao')}, msgs novas {len(caixa.mensagens) - n}",
                    r.get("classe") == "BAIXA" and len(caixa.mensagens) == n and r.get("validacao") == "EXPIRADO"))

    # S03 novo menor preco: PROVAVEL -> ALTA; depois o comprador valida no carrinho -> VALIDADO -> CRITICA (novo alerta)
    o3 = _oferta("03", "[SINTETICO] Robô Aspirador KaBuM Smart K800 Pro 127V Preto", 1050.0, "Amazon", "preco imbativel")
    r1 = proc(o3)
    oid = con.execute("SELECT id FROM ofertas WHERE id_externo='SINT-03'").fetchone()["id"]
    con.execute("INSERT OR REPLACE INTO validacoes_manuais (oferta_id, por, em, preco_validado) VALUES (?,?,?,?)",
                (oid, "SINTETICO: carrinho simulado", db.agora(), r1.get("preco_final")))
    con.commit()
    n = len(caixa.mensagens)
    r2 = proc(o3)
    msg03 = caixa.mensagens[-1] if len(caixa.mensagens) > n else ""
    L.append(_linha("S03", "novo menor preco; depois validado manualmente", "1a: ALTA; 2a: CRITICA e novo alerta com status VALIDADO sem 'estimado'",
                    f"1a {r1.get('classe')}/{r1.get('acao')}; 2a {r2.get('classe')}/{r2.get('acao')}",
                    r1.get("classe") == "ALTA" and r2.get("classe") == "CRITICA" and str(r2.get("acao")).startswith("real")
                    and "Status: VALIDADO" in msg03 and "(estimado)" not in msg03))

    # S04 voltagem errada
    n = len(caixa.mensagens)
    r = proc(_oferta("04", "[SINTETICO] Robô Aspirador Kabum! Smart K800 Pro 13000pa 220v, Preto - Ksar81020pt", 899.0, "Amazon"))
    L.append(_linha("S04", "produto de voltagem errada (K800 Pro 220V)", "nao reconhece, descarte 'quase casou: outra tensao', sem alerta",
                    f"produto {r.get('produto')}, descarte {r.get('descarte')}, msgs novas {len(caixa.mensagens) - n}",
                    r.get("produto") is None and r.get("descarte") == "quase_casou:outra_tensao" and len(caixa.mensagens) == n))

    # S05 duplicada (mesmo item/loja/cupom/preco, outro id, dentro de 24 h)
    n = len(caixa.mensagens)
    r = proc(_oferta("05", "[SINTETICO] Robô Aspirador KaBuM Smart K800 Pro 127V Preto", 1099.0, "KaBuM!",
                     "cupom CASATECH10 10% de desconto, funcionando, consegui aplicar"))
    L.append(_linha("S05", "oferta duplicada", "suprimida (equivalente a alerta das ultimas 24 h)", f"{r.get('acao')}, msgs novas {len(caixa.mensagens) - n}",
                    str(r.get("acao")).startswith("suprimir") and len(caixa.mensagens) == n))

    # S06a falha de internet no envio -> alerta vai para a fila com validade
    falha = _Caixa()
    falha.falhar = True
    r = proc(_oferta("06", "[SINTETICO] Robô Aspirador KaBuM Smart K800 Pro 127V Preto", 1000.0, "Magalu", "oferta"), fn=falha)
    pend = outbox.pendentes(con, tipo="alerta", agora_dt=AGORA)
    L.append(_linha("S06a", "falha de internet no envio do alerta", "registrado como 'falha' e guardado na fila de alertas (validade 30 min)",
                    f"{r.get('acao')}, fila {len(pend)}, expira {pend[0]['expira_em'] if pend else None}",
                    str(r.get("acao")).startswith("falha") and len(pend) == 1 and pend[0]["expira_em"] == "2026-11-21 10:30:00"))

    # S06b falha de internet na coleta
    def sem_rede(cfg):
        raise FonteErroRede("sem rede (simulado)")
    from unittest import mock  # alertas "ligados" so em memoria: com a config real (desligada) a varredura descartaria a fila de alertas (kill switch)

    with mock.patch.object(ranking, "carregar_regras", return_value=regras):
        codigo = varredura.executar(enviar=False, coletores={"fonte_x": sem_rede}, fontes_cfg={"fonte_x": {}}, agora=AGORA)
    st = con.execute("SELECT status FROM coletas_ciclo WHERE fonte='fonte_x'").fetchone()
    L.append(_linha("S06b", "falha de internet na coleta", "fonte marcada como erro (nao como 'sem ofertas') e saida 1",
                    f"status {st['status'] if st else None}, saida {codigo}", st is not None and st["status"] == "erro" and codigo == 1))

    # S07a oferta vencida na fila e ENCERRADA na fonte -> descartada, nunca entregue como ativa
    entregues = _Caixa()
    depois = AGORA + dt.timedelta(hours=2)
    res = outbox.drenar(con, entregues, revalidar=lambda oid: (False, "oferta encerrada na fonte (status FINISHED)"), agora_dt=depois)
    desf = con.execute("SELECT desfecho FROM outbox ORDER BY id").fetchall()
    L.append(_linha("S07a", "alerta vencido na fila e encerrado na fonte", "descartado (descartado_revalidacao), nada entregue",
                    f"{[d['desfecho'] for d in desf]}, entregues {len(entregues.mensagens)}",
                    len(entregues.mensagens) == 0 and [d["desfecho"] for d in desf] == ["descartado_revalidacao"] and bool(res)))

    # S07b vencido mas ainda ativo -> entregue rotulado como revalidado
    outbox.enfileirar(con, "ALERTA SINTETICO", "radar-alerta", "canal indisponivel", tipo="alerta", oferta_id=oid, ttl_min=30, agora_dt=AGORA)
    outbox.drenar(con, entregues, revalidar=lambda o: (True, "ativa na fonte"), agora_dt=depois)
    L.append(_linha("S07b", "alerta vencido na fila, ainda ativo na fonte", "entregue rotulado 'revalidado na fonte as HH:MM' com pedido de conferencia",
                    f"{entregues.mensagens[-1][:70] if entregues.mensagens else None}",
                    bool(entregues.mensagens) and "revalidado na fonte" in entregues.mensagens[-1] and "Confira antes de pagar" in entregues.mensagens[-1]))

    # S08 titulo sem voltagem
    n = len(caixa.mensagens)
    r = proc(_oferta("08", "[SINTETICO] Robô Aspirador KABUM! K800 Pro Laser 13000Pa", 950.0, "Shopee", "oferta"))
    L.append(_linha("S08", "titulo sem voltagem (K800 existe em 127V e 220V)", "reconhece com aviso e NAO gera alerta urgente (classe limitada a MEDIA)",
                    f"{r.get('classe')}, {r.get('acao')}", r.get("produto") == "k800_pro_127v" and r.get("classe") == "MEDIA" and len(caixa.mensagens) == n))

    # S09 nome alternativo sem SKU (Elgin Eco III) com preco excelente
    n = len(caixa.mensagens)
    r = proc(_oferta("09", "[SINTETICO] Ar-Condicionado Split HW Inverter Elgin Eco III Wi-Fi 12.000 BTUs Só Frio - 220V", 1500.0, "Amazon", "oferta"))
    L.append(_linha("S09", "nome alternativo sem codigo do fabricante, preco 20% abaixo do minimo", "reconhece fraco e NAO gera alerta urgente",
                    f"{r.get('classe')}, {r.get('acao')}", r.get("produto") == "elgin_12k" and r.get("classe") == "MEDIA" and len(caixa.mensagens) == n))

    # S10 oferta antiga
    n = len(caixa.mensagens)
    r = proc(_oferta("10", "[SINTETICO] Robô Aspirador KaBuM Smart K800 Pro 127V Preto", 900.0, "Casas Bahia", "oferta", minutos=600))
    L.append(_linha("S10", "oferta com 10 h (antiga)", "sem alerta (nao vira 'relampago')", f"{r.get('acao')}, descarte {r.get('descarte')}",
                    r.get("acao") == "sem_alerta" and r.get("descarte") == "oferta_antiga" and len(caixa.mensagens) == n))

    # S13 oferta no PRECO QUE JA MONITORAMOS (melhor preco atual = ultima coleta propria R$ 1.260): nao e novidade
    n = len(caixa.mensagens)
    r = proc(_oferta("13", "[SINTETICO] Robô Aspirador KaBuM Smart K800 Pro 127V Preto", 1258.0, "Americanas", "oferta"))
    L.append(_linha("S13", "oferta igual ao melhor preco atual ja monitorado (sem novidade)", "fora de ALTA/CRITICA, motivo 'sem novidade', nenhuma mensagem",
                    f"{r.get('classe')}, {r.get('acao')}, {str(r.get('motivo'))[:60]}",
                    r.get("classe") in ("MEDIA", "BAIXA") and "sem novidade" in str(r.get("motivo")) and len(caixa.mensagens) == n))

    # S11 configuracao REAL (alertas desligados): a mesma oferta forte so e registrada em sombra
    sombra = _Caixa()
    r = varredura.processar_oferta(con, _oferta("11", "[SINTETICO] Robô Aspirador KaBuM Smart K800 Pro 127V Preto", 1010.0, "Outra Loja", "oferta"),
                                   cat, real, sombra, AGORA)
    L.append(_linha("S11", "configuracao real (enviar=false, sem homologado_em)", "modo sombra: registra e NAO envia", f"{r.get('acao')}, msgs {len(sombra.mensagens)}",
                    str(r.get("acao")).startswith("sombra") and not sombra.mensagens))

    # S12 cupom de loja, que nao e produto, nao dispara alerta de produto
    n = len(caixa.mensagens)
    cl = Oferta(fonte="meliuz", canal="cupom_loja:amazon", id_externo="SINT-12", titulo="[SINTETICO] amazon: R$ 150 de desconto", loja="Amazon",
                texto="R$150 de desconto em compras acima de R$1.499. Aplique o cupom.", cupom_codigo="SINT150", extras={"tipo": "cupom_loja"})
    r = proc(cl)
    L.append(_linha("S12", "cupom de loja (sem produto)", "so registrado; alerta de produto nao dispara", f"{r.get('acao')}, msgs novas {len(caixa.mensagens) - n}",
                    r.get("acao") == "registrado" and len(caixa.mensagens) == n))

    L += _cenarios_prioridade(con, regras)

    teste = None
    if enviar_teste and msg01:
        teste = _enviar_teste(msg01)
    estat = historico.estatisticas(con, "k800_pro_127v", AGORA)
    con.close()
    return {"cenarios": L, "ok": all(x["ok"] for x in L), "total": len(L), "aprovados": sum(1 for x in L if x["ok"]),
            "alerta_exemplo": msg01, "envio_teste": teste, "historico_semente": estat["historico_total"]}


def _cenarios_prioridade(con, regras_ligadas: dict[str, Any]) -> list[dict[str, Any]]:
    """Priorizacao, orcamento, CRITICO acima do limite, expiracao e reconexao. Banco temporario; canal falso."""
    from . import prioridade

    L: list[dict[str, Any]] = []
    r = copy.deepcopy(regras_ligadas)
    r["prioridade"] = {**r.get("prioridade", {}), "max_por_ciclo": 2, "orcamento_diario": 3, "orcamento_critico_diario": 2, "max_criticos_por_ciclo": 1, "limiar_ultimo_comum": 40}
    t0 = AGORA + dt.timedelta(hours=1)  # 11:00, depois dos cenarios anteriores

    def cand(prod, score, classe="ALTA", preco=1000.0, quando=t0):
        return prioridade.registrar_candidato(
            con, oferta_id=None, produto=prod, loja=f"L-{prod}-{score}", vendedor=None, classe=classe, score=score,
            componentes={"economia_reais": 100.0, "economia_pct": 10.0}, preco_final=preco, status_cupom="PROVAVEL", cupom=None, fonte="SINTETICO",
            hora_incerta=False, mensagem=f"[SINTETICO] {prod} R$ {preco:.0f} (pontuacao {score})", url=None, regras=r, agora=quando)

    def est(i):
        return con.execute("SELECT estado FROM candidatos_alerta WHERE id=?", (i,)).fetchone()[0]

    # P01 a melhor oferta ganha de quem chegou primeiro; so 2 por ciclo (anti-rajada)
    caixa = _Caixa()
    a, b, c_, d = cand("dreame_f10", 50), cand("tapo_rv20_max", 92), cand("xiaomi_s40c", 60), cand("elgin_12k", 78)
    prioridade.despachar(con, r, caixa, t0)
    ordem = [m.split("]")[1].split(" R$")[0].strip() for m in caixa.mensagens]
    L.append(_linha("P01", "ofertas chegam fracas primeiro; o despacho ordena por pontuacao", "enviam as 2 melhores (92 e 78) em ordem; as muito inferiores ficam retidas ou substituidas (nunca em silencio)",
                    f"enviadas {ordem}; estados {[est(x) for x in (a, b, c_, d)]}",
                    ordem == ["tapo_rv20_max", "elgin_12k"] and all(est(x) in ("substituido", "retida_orcamento") for x in (a, c_)) and est(b) == est(d) == "enviado"))

    # P02 duas ofertas do MESMO produto: so a melhor
    t1 = t0 + dt.timedelta(minutes=10)
    x1, x2 = cand("midea_lite_12k", 55, quando=t1), cand("midea_lite_12k", 83, quando=t1)
    n = len(caixa.mensagens)
    prioridade.despachar(con, r, caixa, t1)
    L.append(_linha("P02", "duas ofertas do mesmo produto no mesmo ciclo", "so a de maior pontuacao e enviada; a outra fica substituida",
                    f"{est(x1)} / {est(x2)}; msgs novas {len(caixa.mensagens) - n}", est(x2) == "enviado" and est(x1) == "substituido" and len(caixa.mensagens) == n + 1))

    # P03 orcamento comum esgotado (3): o 4o comum nao passa, mas um CRITICO passa (orcamento proprio) e nao se repete
    t2 = t0 + dt.timedelta(minutes=20)
    comum = cand("agratto_12k", 70, quando=t2)
    crit1 = cand("philco_18k", 95, "CRITICA", 1500.0, quando=t2)
    n = len(caixa.mensagens)
    prioridade.despachar(con, r, caixa, t2)
    t3 = t0 + dt.timedelta(minutes=30)
    crit_rep = cand("philco_18k", 96, "CRITICA", 1490.0, quando=t3)   # 20 min depois, 0,7% melhor: repeticao
    prioridade.despachar(con, r, caixa, t3)
    L.append(_linha("P03", "orcamento comum esgotado; alerta CRITICO ultrapassa o limite comum mas nao se repete",
                    "comum 'retida_orcamento'; CRITICO enviado; repeticao do CRITICO suprimida",
                    f"comum {est(comum)}; critico {est(crit1)}; repeticao {est(crit_rep)}",
                    est(comum) == "retida_orcamento" and est(crit1) == "enviado" and est(crit_rep) == "suprimido_repeticao" and len(caixa.mensagens) == n + 1))

    # P04 candidato que nao foi enviado vence (nao entrega oferta velha)
    velho = cand("elgin_18k", 85, quando=t0 - dt.timedelta(minutes=50))
    n = len(caixa.mensagens)
    prioridade.despachar(con, r, caixa, t0 + dt.timedelta(minutes=40))
    L.append(_linha("P04", "candidato com mais de 30 min sem ser enviado", "expirado, nada entregue", f"{est(velho)}, msgs novas {len(caixa.mensagens) - n}",
                    est(velho) == "expirado" and len(caixa.mensagens) == n))

    # P05 internet cai no envio e VOLTA: o alerta vai para a fila e e entregue na reconexao, dentro da validade
    t5 = t0 + dt.timedelta(hours=2)
    r2 = copy.deepcopy(r)
    r2["prioridade"].update(orcamento_diario=9, orcamento_critico_diario=9)
    fora = _Caixa()
    fora.falhar = True
    pid = cand("dreame_f10", 88, preco=1102.0, quando=t5)
    prioridade.despachar(con, r2, fora, t5)
    na_fila = len(outbox.pendentes(con, tipo="alerta", agora_dt=t5))
    voltou = _Caixa()
    outbox.drenar(con, voltou, revalidar=lambda oid: (True, "ativa"), agora_dt=t5 + dt.timedelta(minutes=12))
    L.append(_linha("P05", "internet indisponivel no envio e reconexao", "falha registrada, alerta guardado e entregue ao reconectar (dentro de 30 min)",
                    f"{est(pid)}; na fila {na_fila}; entregues apos reconectar {len(voltou.mensagens)}",
                    est(pid) == "falha_envio" and na_fila == 1 and len(voltou.mensagens) == 1))

    # P06 sombra: com a configuracao REAL (alertas desligados) o ranking roda e NADA e enviado
    real = ranking.carregar_regras(operacao=False)
    t6 = t0 + dt.timedelta(hours=3)
    s1 = prioridade.registrar_candidato(con, oferta_id=None, produto="tapo_rv20_max", loja="Z", vendedor=None, classe="ALTA", score=85,
                                        componentes={}, preco_final=700.0, status_cupom="PROVAVEL", cupom=None, fonte="SINTETICO", hora_incerta=False,
                                        mensagem="[SINTETICO]", url=None, regras=real, agora=t6)
    mudo = _Caixa()
    prioridade.despachar(con, real, mudo, t6)
    L.append(_linha("P06", "configuracao real (alertas desligados): despacho em sombra", "selecionado_sombra e NENHUMA mensagem", f"{est(s1)}, msgs {len(mudo.mensagens)}",
                    est(s1) == "selecionado_sombra" and not mudo.mensagens))
    return L


def demonstrar_ofertas_reais() -> dict[str, Any]:
    """Reencena OFERTAS REAIS (corpus: historico do Promobit e documentos do STATUS.md) pela cadeia de producao.

    O banco e TEMPORARIO, mas semeado com o historico REAL de precos desta maquina (lido, nunca alterado). Os alertas ficam ligados so em
    memoria e nada e enviado. Mostra, para cada oferta real, o que o radar reconheceu e o que decidiria. A hora de publicacao e posta
    como '30 min atras' (as ofertas reais tem dias; o objetivo e exercitar a decisao, nao a idade)."""
    from . import avaliacao, caminhos

    reais = {nome: caminhos.tracker_dir(nome) / "historico.jsonl" for nome in ("rastreador-robos", "rastreador-ares", "rastreador-chuveiro")}
    itens = [i for i in avaliacao.carregar_corpus()
             if i["origem"] in ("real_historico", "documentado") and i["caso"] in ("positivo", "ambiguo") and i.get("preco")]
    anterior = os.environ.get("CENTRAL_COMPRAS_DADOS_PRIVADOS")
    abertas: list = []
    try:
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["CENTRAL_COMPRAS_DADOS_PRIVADOS"] = tmp
            try:
                con = db.abrir()
                abertas.append(con)
                for nome, arq in reais.items():
                    historico.importar_para_db(con, nome, arq)
                cat = catalogo.carregar()
                regras = copy.deepcopy(ranking.carregar_regras(operacao=False))
                regras["alertas"].update(enviar=True, homologado_em="DEMONSTRACAO (so em memoria)")
                agora = dt.datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
                caixa = _Caixa()
                linhas = []
                for it in itens:
                    pub = (agora - dt.timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M")
                    of = Oferta(fonte="promobit", canal="REAL-REENCENADA", id_externo=f"REAL-{it['id']}", titulo=it["texto"], loja=it.get("loja"),
                                preco_anunciado=float(it["preco"]), publicado_em=pub, url=None)
                    r = varredura.processar_oferta(con, of, cat, regras, caixa, agora)
                    st = historico.estatisticas(con, r["produto"], agora) if r.get("produto") else {}
                    linhas.append({"id": it["id"], "origem": it["origem"], "texto": it["texto"][:70], "loja": it.get("loja"), "preco": it["preco"],
                                   "esperado": it.get("esperado"), "produto": r.get("produto"), "classe": r.get("classe"), "validacao": r.get("validacao"),
                                   "acao": r.get("acao"), "motivo": r.get("motivo"), "preco_final": r.get("preco_final"),
                                   "minimo_historico": (st.get("historico_total") or {}).get("menor"), "obs_historico": st.get("observacoes_validas")})
                return {"ofertas": linhas, "mensagens_que_sairiam": len(caixa.mensagens), "primeira_mensagem": caixa.mensagens[0] if caixa.mensagens else None}
            finally:
                for c in abertas:
                    try:
                        c.close()
                    except Exception:  # noqa: BLE001
                        pass
    finally:
        if anterior is None:
            os.environ.pop("CENTRAL_COMPRAS_DADOS_PRIVADOS", None)
        else:
            os.environ["CENTRAL_COMPRAS_DADOS_PRIVADOS"] = anterior


def mensagem_de_teste(corpo_alerta: str) -> str:
    cab = ("🧪 *TESTE DO RADAR DE COMPRAS (mensagem sintética, não é oferta real)*\n"
           "Produto, preço e loja abaixo são inventados para testar o formato. Não compre nada com base nesta mensagem.\n"
           "Os alertas reais continuam DESLIGADOS.\n\n")
    return cab + corpo_alerta.replace("https://exemplo.invalido/sint-01", "(sem link: teste)")


def _enviar_teste(corpo: str) -> dict[str, Any]:
    from . import canais

    ok, info = canais.enviar_whatsapp(mensagem_de_teste(corpo))
    return {"ok": ok, "info": info}
