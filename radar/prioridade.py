"""Prioridade e orcamento de notificacoes (substitui o limite de 6 por ordem de chegada).

Fluxo: a varredura NAO envia mais na hora. Cada oferta que passa nos portoes (classe, status, duplicidade) vira um CANDIDATO com
PONTUACAO explicavel (0-100). No fim de cada ciclo o DESPACHANTE rankeia todos os candidatos pendentes e decide, respeitando:
  - orcamento diario comum e orcamento proprio dos CRITICOS (mais um pequeno orcamento de excecao por superioridade de pontuacao);
  - no maximo N alertas por ciclo (contra rajada) e um intervalo minimo por produto (contra repeticao);
  - substituicao: oferta muito superior desloca candidatos de menor valor AINDA NAO ENVIADOS;
  - revalidacao na fonte de candidato que esperou, e validade curta do candidato (nunca entrega oferta velha como ativa).
Com alertas desligados/nao homologados tudo isto roda do mesmo jeito, mas o resultado e 'selecionado_sombra' (nada e enviado).

Pontuacao (pesos em config/radar_regras.yaml > prioridade.pesos; soma 100):
  economia_pct 35   melhora % sobre o melhor preco atual conhecido (ou queda vs mediana do historico)
  economia_reais 10 melhora em R$ (escala `economia_reais_ref`)
  historico 15      novo menor preco do historico, ou queda vs mediana de 30 dias
  confianca 20      VALIDADO (cupom validado incluso) > PROVAVEL; hora incerta reduz
  exatidao 10       SKU confirmado e voltagem informada; nome alternativo/sem voltagem/sem SKU reduzem
  urgencia 10       so com HORA CONFIAVEL (muito recente) ou validade proxima; hora incerta = 0
  menos penalidade por alertas anteriores do mesmo produto nas ultimas 24 h
"""

from __future__ import annotations

import datetime as dt
import json
import sqlite3
import time
from typing import Any, Callable

from . import alertas, latencia, outbox, piloto
from .cupons import VALIDADO

PADRAO: dict[str, Any] = {
    "orcamento_diario": 6,
    "orcamento_critico_diario": 3,
    "orcamento_excecao_diario": 2,
    "score_minimo": 40,
    "score_excecao": 80,
    "limiar_ultimo_comum": 65,
    "max_por_ciclo": 2,
    "max_criticos_por_ciclo": 2,
    "intervalo_mesmo_produto_min": 90,
    "intervalo_critico_mesmo_produto_min": 30,
    "melhora_para_repetir_pct": 5,
    "substituicao_delta": 15,
    "validade_candidato_min": 30,
    "revalidar_apos_min": 5,
    "penalidade_repeticao": 8,
    "economia_pct_ref": 20,
    "economia_reais_ref": 300,
    "pesos": {"economia_pct": 35, "economia_reais": 10, "historico": 15, "confianca": 20, "exatidao": 10, "urgencia": 10},
}


def config(regras: dict[str, Any]) -> dict[str, Any]:
    p = {**PADRAO, **(regras.get("prioridade") or {})}
    p["pesos"] = {**PADRAO["pesos"], **((regras.get("prioridade") or {}).get("pesos") or {})}
    return p


def limiar_do_momento(p: dict[str, Any], usados_comum: int) -> float:
    """Pontuacao minima para gastar a proxima vaga COMUM. Sobe linearmente de `score_minimo` (1a vaga) ate `limiar_ultimo_comum` (ultima vaga).
    Evita que ofertas medianas da manha esgotem o orcamento antes das melhores do dia (achado da simulacao do dia cheio, fase 5)."""
    n = max(int(p["orcamento_diario"]), 1)
    ini = float(p["score_minimo"])
    fim = float(p.get("limiar_ultimo_comum", ini))
    return ini + (max(fim, ini) - ini) * min(usados_comum, n - 1) / max(n - 1, 1)


def _s(d: dt.datetime) -> str:
    return d.strftime("%Y-%m-%d %H:%M:%S")


# ------------------------------------------------------------------ pontuacao

def pontuar(
    *, preco_final: float, preco_ref: float | None, stats: dict[str, Any] | None, validacao: str, avisos: list[str],
    idade_horas: float | None, hora_incerta: bool, repeticoes_24h: int, regras: dict[str, Any], validade_horas: float | None = None,
) -> tuple[float, dict[str, Any]]:
    """(score 0-100, componentes). Tudo explicavel: cada componente mostra o valor bruto e os pontos."""
    p = config(regras)
    w = p["pesos"]
    stats = stats or {}
    total, mes = stats.get("historico_total") or {}, stats.get("ultimos_30_dias") or {}
    mediana = mes.get("mediana") or total.get("mediana")
    base = preco_ref if preco_ref else mediana
    economia = (base - preco_final) if base else None
    pct = (economia / base * 100.0) if base and economia is not None else None
    comp: dict[str, Any] = {"economia_reais": round(economia, 2) if economia is not None else None,
                            "economia_pct": round(pct, 1) if pct is not None else None,
                            "base_de_comparacao": "melhor preco atual" if preco_ref else ("mediana do historico" if mediana else "sem base")}

    f_pct = max(0.0, min((pct or 0.0) / float(p["economia_pct_ref"]), 1.0))
    f_rs = max(0.0, min((economia or 0.0) / float(p["economia_reais_ref"]), 1.0))
    minimo = total.get("menor")
    queda_med = ((mediana - preco_final) / mediana * 100.0) if mediana else 0.0
    f_hist = 1.0 if (minimo is not None and preco_final <= minimo) else max(0.0, min(queda_med / 30.0, 1.0))
    f_conf = {VALIDADO: 1.0}.get(validacao, 0.5)
    if hora_incerta:
        f_conf *= 0.7
    f_exat = 1.0
    for aviso, teto in (("sku_nao_confirmado", 0.5), ("tensao_nao_informada", 0.3), ("nome_alternativo", 0.2)):
        if aviso in avisos:
            f_exat = min(f_exat, teto)
    if hora_incerta or idade_horas is None:
        f_urg = 0.0  # sem hora confiavel NAO ha urgencia presumida
    else:
        f_urg = 1.0 if idade_horas <= 0.5 else 0.6 if idade_horas <= 2 else 0.3 if idade_horas <= 6 else 0.0
    if validade_horas is not None and 0 <= validade_horas <= 2:
        f_urg = 1.0  # a promocao acaba logo
    pontos = {"economia_pct": f_pct * w["economia_pct"], "economia_reais": f_rs * w["economia_reais"], "historico": f_hist * w["historico"],
              "confianca": f_conf * w["confianca"], "exatidao": f_exat * w["exatidao"], "urgencia": f_urg * w["urgencia"]}
    penal = min(repeticoes_24h, 2) * float(p["penalidade_repeticao"])
    score = max(0.0, min(100.0, sum(pontos.values()) - penal))
    # `pontos` separado: economia_pct/economia_reais acima sao os VALORES (R$ e %), aqui sao os PONTOS de cada componente
    comp["pontos"] = {k: round(v, 1) for k, v in pontos.items()}
    comp["penalidade_repeticao"] = penal
    return round(score, 1), comp


def texto_prioridade(score: float, comp: dict[str, Any]) -> str:
    partes = []
    if comp.get("economia_pct") is not None:
        partes.append(f"economia {comp['economia_pct']:.0f}% (R$ {comp['economia_reais']:.0f}) sobre {comp['base_de_comparacao']}")
    return f"{score:.0f}/100" + (" | " + "; ".join(partes) if partes else "")


# ------------------------------------------------------------------ candidatos

def repeticoes_24h(con: sqlite3.Connection, produto: str, agora: dt.datetime) -> int:
    return con.execute("SELECT COUNT(*) FROM alertas WHERE produto=? AND modo IN ('real','sombra') AND enviado_em >= ?",
                       (produto, _s(agora - dt.timedelta(hours=24)))).fetchone()[0]


def registrar_candidato(
    con: sqlite3.Connection, *, oferta_id: int | None, produto: str, loja: str | None, vendedor: str | None, classe: str, score: float,
    componentes: dict[str, Any], preco_final: float, status_cupom: str, cupom: str | None, fonte: str, hora_incerta: bool,
    mensagem: str, url: str | None, regras: dict[str, Any], agora: dt.datetime,
) -> int:
    p = config(regras)
    cur = con.execute(
        "INSERT INTO candidatos_alerta (oferta_id, produto, familia, classe, score, componentes_json, preco_final, economia, economia_pct, "
        "status_cupom, cupom, fonte, hora_incerta, mensagem, url, estado, criado_em, expira_em) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'pendente',?,?)",
        (oferta_id, produto, alertas.chave_familia(produto, loja, vendedor), classe, score, json.dumps(componentes, ensure_ascii=False),
         preco_final, componentes.get("economia_reais"), componentes.get("economia_pct"), status_cupom, cupom, fonte, int(hora_incerta),
         mensagem, url, _s(agora), _s(agora + dt.timedelta(minutes=float(p["validade_candidato_min"])))))
    con.commit()
    return int(cur.lastrowid)


def _marcar(con: sqlite3.Connection, cid: int, estado: str, motivo: str, agora: dt.datetime) -> None:
    con.execute("UPDATE candidatos_alerta SET estado=?, motivo=?, decidido_em=? WHERE id=?", (estado, motivo, _s(agora), cid))
    con.commit()


def _usados_hoje(con: sqlite3.Connection, agora: dt.datetime) -> dict[str, int]:
    ini = agora.strftime("%Y-%m-%d") + " 00:00:00"
    rows = con.execute("SELECT classe, motivo FROM candidatos_alerta WHERE estado IN ('enviado','selecionado_sombra') AND decidido_em >= ?", (ini,)).fetchall()
    out = {"comum": 0, "critico": 0, "excecao": 0}
    for r in rows:
        m = str(r["motivo"] or "")
        out["excecao" if m.startswith("orcamento:excecao") else "critico" if m.startswith("orcamento:critico") else "comum"] += 1
    return out


def _ultimo_alerta(con: sqlite3.Connection, produto: str) -> sqlite3.Row | None:
    return con.execute("SELECT preco, enviado_em FROM alertas WHERE produto=? AND modo IN ('real','sombra') ORDER BY id DESC LIMIT 1", (produto,)).fetchone()


def _repete(ult: sqlite3.Row | None, preco: float, agora: dt.datetime, intervalo_min: float, melhora_pct: float) -> bool:
    """True se for REPETICAO: mesmo produto dentro do intervalo e sem melhora relevante sobre o ultimo alerta."""
    if ult is None:
        return False
    try:
        idade_min = (agora - dt.datetime.strptime(ult["enviado_em"], "%Y-%m-%d %H:%M:%S")).total_seconds() / 60.0
    except ValueError:
        return False
    if idade_min >= intervalo_min:
        return False
    return not (ult["preco"] and preco <= float(ult["preco"]) * (1 - melhora_pct / 100.0))


# ------------------------------------------------------------------ despachante

def despachar(
    con: sqlite3.Connection, regras: dict[str, Any], enviar_fn: Callable[[str], tuple[bool, str]] | None, agora: dt.datetime | None = None,
    *, revalidar: Callable[[int], tuple[bool, str]] | None = None,
) -> list[dict[str, Any]]:
    """Rankeia os candidatos pendentes e decide. Retorna a lista de decisoes (para log, relatorio e testes)."""
    agora = agora or dt.datetime.now()
    p = config(regras)
    cfg = regras.get("alertas", {})
    real = bool(enviar_fn is not None and cfg.get("enviar") and cfg.get("homologado_em"))
    pil = piloto.config(regras) if (real and piloto.modo(regras) == "PILOTO") else None
    if pil is not None:  # MODO PILOTO: limites bem menores e revalidacao sempre; as barreiras por candidato entram no laco abaixo
        p = {**p, **piloto.limites_prioridade(pil), "revalidar_apos_min": 0 if pil.get("revalidar_sempre", True) else p["revalidar_apos_min"]}
    decisoes: list[dict[str, Any]] = []

    def reg(c: sqlite3.Row, estado: str, motivo: str) -> None:
        _marcar(con, c["id"], estado, motivo, agora)
        decisoes.append({"id": c["id"], "produto": c["produto"], "classe": c["classe"], "score": c["score"], "estado": estado, "motivo": motivo,
                         "preco_final": c["preco_final"]})

    # Quem venceu ESPERANDO vaga (limite por varredura) nao some em silencio: vira `retida_orcamento`, que aparece no painel e no bloco de retidas.
    con.execute("UPDATE candidatos_alerta SET "
                "estado=CASE WHEN motivo LIKE 'aguardando vaga%' THEN 'retida_orcamento' ELSE 'expirado' END, "
                "motivo=CASE WHEN motivo LIKE 'aguardando vaga%' THEN 'venceu aguardando vaga (limite por varredura); oferta NAO entregue' "
                "WHEN motivo LIKE 'aguardando horario%' THEN 'venceu fora do horario de alertas; oferta NAO entregue' "
                "ELSE 'validade do candidato vencida (oferta pode ter acabado)' END, decidido_em=? "
                "WHERE estado='pendente' AND expira_em < ?", (_s(agora), _s(agora)))
    con.commit()
    pend = con.execute("SELECT * FROM candidatos_alerta WHERE estado='pendente' ORDER BY score DESC, id").fetchall()
    if not pend:
        return decisoes

    hi, hf = (cfg.get("horario") or {}).get("inicio", "07:00"), (cfg.get("horario") or {}).get("fim", "23:00")
    if not (hi <= agora.strftime("%H:%M") <= hf):
        for c in pend:
            con.execute("UPDATE candidatos_alerta SET motivo='aguardando horario de alertas' WHERE id=?", (c["id"],))
        con.commit()
        decisoes.append({"estado": "adiado", "motivo": f"fora do horario de alertas ({hi}-{hf}): candidatos aguardam ate vencer"})
        return decisoes

    # 1 candidato por produto por despacho: a melhor oferta; as demais do mesmo produto ficam substituidas
    melhores: dict[str, sqlite3.Row] = {}
    for c in pend:
        if c["produto"] in melhores:
            reg(c, "substituido", f"melhor oferta do mesmo produto neste despacho (pontuacao {melhores[c['produto']]['score']:.0f} contra {c['score']:.0f})")
        else:
            melhores[c["produto"]] = c

    usados = _usados_hoje(con, agora)
    n_ciclo = n_crit_ciclo = 0
    selecionados: list[sqlite3.Row] = []
    restantes: list[sqlite3.Row] = []
    for c in melhores.values():
        # candidato que esperou: confirma na fonte antes de entregar (nunca apresenta oferta encerrada como ativa)
        try:
            idade_min = (agora - dt.datetime.strptime(c["criado_em"], "%Y-%m-%d %H:%M:%S")).total_seconds() / 60.0
        except ValueError:
            idade_min = 0.0
        if revalidar is not None and c["oferta_id"] is not None and idade_min >= float(p["revalidar_apos_min"]):
            try:
                ativa, mot = revalidar(int(c["oferta_id"]))
            except Exception as exc:  # noqa: BLE001 - na duvida nao entrega
                ativa, mot = False, f"revalidacao falhou: {str(exc)[:60]}"
            if not ativa:
                reg(c, "expirado", f"revalidacao antes de entregar: {mot}")
                continue
        if pil is not None:
            passa, porque = piloto.avaliar_candidato(c, pil)
            if not passa:
                reg(c, "nao_selecionado", f"fora do piloto: {porque}")
                continue
        ult = _ultimo_alerta(con, c["produto"])
        critica = c["classe"] == "CRITICA"
        if critica:
            if usados["critico"] >= int(p["orcamento_critico_diario"]):
                reg(c, "retida_orcamento", f"orcamento CRITICO do dia esgotado ({p['orcamento_critico_diario']}): oferta NAO entregue")
                continue
            if n_crit_ciclo >= int(p["max_criticos_por_ciclo"]):
                restantes.append(c)  # fica para o proximo ciclo (anti-rajada)
                continue
            if _repete(ult, c["preco_final"], agora, float(p["intervalo_critico_mesmo_produto_min"]), float(p["melhora_para_repetir_pct"])):
                reg(c, "suprimido_repeticao", f"CRITICO repetido: ja houve alerta deste produto ha menos de {p['intervalo_critico_mesmo_produto_min']} min sem melhora de {p['melhora_para_repetir_pct']}%")
                continue
            orc = "critico"
        else:
            if c["score"] < float(p["score_minimo"]):
                reg(c, "nao_selecionado", f"pontuacao {c['score']:.0f} abaixo do minimo {p['score_minimo']}")
                continue
            if _repete(ult, c["preco_final"], agora, float(p["intervalo_mesmo_produto_min"]), float(p["melhora_para_repetir_pct"])):
                reg(c, "suprimido_repeticao", f"repeticao: alerta deste produto ha menos de {p['intervalo_mesmo_produto_min']} min sem melhora de {p['melhora_para_repetir_pct']}%")
                continue
            limiar = limiar_do_momento(p, usados["comum"])
            if usados["comum"] < int(p["orcamento_diario"]) and c["score"] < limiar and c["score"] < float(p["score_excecao"]):
                # a vaga N do dia exige mais que a vaga 1: oferta mediana cedo nao gasta o orcamento que a melhor da tarde vai precisar
                reg(c, "retida_orcamento", f"pontuacao {c['score']:.0f} abaixo do limiar do momento ({limiar:.0f}; {usados['comum']} de {p['orcamento_diario']} "
                    "vagas comuns ja usadas hoje): reserva vaga para oferta melhor; oferta NAO entregue")
                continue
            if n_ciclo >= int(p["max_por_ciclo"]):
                restantes.append(c)
                continue
            if usados["comum"] < int(p["orcamento_diario"]):
                orc = "comum"
            elif c["score"] >= float(p["score_excecao"]) and usados["excecao"] < int(p["orcamento_excecao_diario"]):
                orc = "excecao"
            else:
                excecao_acabou = c["score"] >= float(p["score_excecao"])
                reg(c, "retida_orcamento", f"orcamento diario esgotado ({p['orcamento_diario']})"
                    + (f" e orcamento de excecao esgotado ({p['orcamento_excecao_diario']})" if excecao_acabou
                       else f" e pontuacao {c['score']:.0f} abaixo da excecao {p['score_excecao']}") + ": oferta NAO entregue")
                continue
        usados[orc] += 1
        n_crit_ciclo += 1 if critica else 0
        n_ciclo += 0 if critica else 1
        selecionados.append(c)
        _entregar(con, c, orc, real, enviar_fn, regras, agora, reg)

    for c in restantes:  # marca quem esta esperando vaga: se vencer, vira `retida_orcamento` (visivel), nao `expirado` (silencioso)
        con.execute("UPDATE candidatos_alerta SET motivo='aguardando vaga no proximo ciclo' WHERE id=? AND estado='pendente'", (c["id"],))
    con.commit()

    # substituicao: quem ficou esperando e e MUITO inferior ao melhor selecionado perde a vez de vez
    if selecionados and restantes:
        topo = max(s["score"] for s in selecionados)
        for c in restantes:
            if c["score"] + float(p["substituicao_delta"]) <= topo:
                reg(c, "substituido", f"substituido por oferta superior neste despacho (pontuacao {topo:.0f} contra {c['score']:.0f})")
    return decisoes


def _entregar(con, c, orc, real, enviar_fn, regras, agora, reg) -> None:
    motivo = f"orcamento:{orc}"
    if not real:
        reg(c, "selecionado_sombra", motivo + " (sombra: nada enviado)")
        alertas.registrar(con, oferta_id=c["oferta_id"], produto=c["produto"], loja=None, vendedor=None, cupom=c["cupom"], preco=c["preco_final"],
                          url=c["url"], classe=c["classe"], status=c["status_cupom"] or "", modo="sombra", detalhe=f"{motivo} | prioridade {c['score']:.0f}", agora=agora)
        return
    inicio = dt.datetime.now()
    _t = time.perf_counter()
    try:
        espera = (inicio - dt.datetime.strptime(c["criado_em"], "%Y-%m-%d %H:%M:%S")).total_seconds()
    except ValueError:
        espera = None
    ok, info = enviar_fn(c["mensagem"])
    duracao = round(time.perf_counter() - _t, 2)
    # Estagios do alerta (MEDIDOS): criacao do candidato -> inicio do envio -> confirmacao devolvida pelo canal (para o WhatsApp, a mensagem
    # lida de volta na conversa) -> se falhou, entrada na fila. `espera_s` so vale quando o relogio nao e simulado (menos de 1 h).
    latencia.registrar("envio_alerta", cid=c["id"], ok=bool(ok), duracao_s=duracao, chars=len(c["mensagem"]),
                       espera_s=round(espera, 1) if espera is not None and 0 <= espera < 3600 else None,
                       criado_em=c["criado_em"], inicio_envio=inicio.strftime("%H:%M:%S"), confirmado_em=dt.datetime.now().strftime("%H:%M:%S") if ok else None)
    if ok:
        reg(c, "enviado", motivo)
        modo = "real"
    else:
        reg(c, "falha_envio", f"{motivo} | {info}")
        outbox.enfileirar(con, c["mensagem"], "radar-alerta", info, tipo="alerta", oferta_id=c["oferta_id"], agora_dt=agora,
                          ttl_min=float(regras.get("alertas", {}).get("ttl_alerta_min", outbox.TTL_ALERTA_MIN)))
        latencia.registrar("alerta_na_fila", cid=c["id"], enfileirado_em=dt.datetime.now().strftime("%H:%M:%S"), motivo=str(info)[:120])
        modo = "falha"
    alertas.registrar(con, oferta_id=c["oferta_id"], produto=c["produto"], loja=None, vendedor=None, cupom=c["cupom"], preco=c["preco_final"],
                      url=c["url"], classe=c["classe"], status=c["status_cupom"] or "", modo=modo, detalhe=f"{motivo} | {info if not ok else 'enviado'}", agora=agora)


def retidas(con: sqlite3.Connection, agora: dt.datetime | None = None, horas: float = 24.0) -> list[sqlite3.Row]:
    """Oportunidades que o ORCAMENTO/limite por varredura deixou sem alerta (melhores primeiro). Substituidas por oferta melhor, repeticoes
    suprimidas e pontuacao abaixo do minimo sao decisoes de qualidade e ficam fora; aqui entra so o que se perdeu por falta de vaga."""
    agora = agora or dt.datetime.now()
    return con.execute("SELECT * FROM candidatos_alerta WHERE estado='retida_orcamento' AND criado_em >= ? ORDER BY score DESC, id",
                       (_s(agora - dt.timedelta(hours=horas)),)).fetchall()


def bloco_retidas(con: sqlite3.Connection, regras: dict[str, Any], origem: str | None = None, agora: dt.datetime | None = None,
                  horas: float = 8.0, limite: int = 3) -> str:
    """Texto para anexar ao relatorio das 08/14/20h: o que o orcamento reteve. VAZIO em modo sombra (nao existiam alertas ativos, entao
    nao ha o que 'ter perdido') e vazio quando nada foi retido. `origem` (rastreador-robos|ares|chuveiro) filtra pela familia do produto."""
    cfg = regras.get("alertas", {})
    if not (cfg.get("enviar") and cfg.get("homologado_em")):
        return ""
    prefixos = {"rastreador-robos": ("dreame", "k800", "tapo", "xiaomi"), "rastreador-ares": ("elgin", "agratto", "midea", "philco"),
                "rastreador-chuveiro": ("loren",)}.get(origem or "")
    linhas = [r for r in retidas(con, agora, horas) if not prefixos or str(r["produto"]).startswith(prefixos)][:limite]
    if not linhas:
        return ""
    corpo = "\n".join(f"- {r['produto']}: R$ {r['preco_final']:.2f} ({r['criado_em'][11:16]}, pontuacao {r['score']:.0f}) retida: {r['motivo']}" for r in linhas)
    return f"\n\n*Ofertas que o limite de alertas segurou (conferir se ainda valem):*\n{corpo}"


def painel(con: sqlite3.Connection, agora: dt.datetime | None = None, horas: float = 24.0) -> list[sqlite3.Row]:
    agora = agora or dt.datetime.now()
    return con.execute("SELECT * FROM candidatos_alerta WHERE criado_em >= ? ORDER BY criado_em DESC, score DESC",
                       (_s(agora - dt.timedelta(hours=horas)),)).fetchall()
