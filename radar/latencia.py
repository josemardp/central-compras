"""Latencia do radar: do momento da publicacao ate a mensagem no WhatsApp. Separa MEDIDO de ESTIMADO.

Etapas (e de onde sai o numero):
  1 publicacao -> coleta        MEDIDO so onde a fonte informa a hora (Gatry: ISO; Promobit/Pelando: "ha X min", resolucao ~1 min);
                                HardMOB nao informa hora: NAO MEDIDO. Inclui a espera ate o proximo ciclo.
  2 coleta -> classificacao     MEDIDO a cada oferta (tempo de CPU em `processar_oferta`), gravado em `latencia.jsonl`.
  3 classificacao -> alerta     MEDIDO (criacao do candidato e da mensagem) e o despacho no fim do ciclo.
  4 criacao -> entrega WhatsApp MEDIDO a partir do primeiro envio depois desta versao; antes disso so ESTIMATIVA (esperas fixas do codigo).
Tambem calcula, com os horarios REAIS dos ciclos, a chance de uma promocao de poucos minutos ser lida pelo menos uma vez.
"""

from __future__ import annotations

import datetime as dt
import json
import statistics
from typing import Any

from . import caminhos

ARQ = "latencia.jsonl"
MAX_BYTES = 1_000_000
LIMITE_FRESCA_MIN = 120.0   # acima disto a oferta ja era antiga quando o radar a viu (nao entra na latencia)
ESTIMATIVA_ENVIO_S = 4.0   # esperas fixas do envio (0,8 s + 3,0 s) mais digitacao: limite INFERIOR, nao medida


def registrar(evento: str, **campos: Any) -> None:
    """Anexa uma linha. Nunca levanta: medir nao pode derrubar a varredura nem o envio."""
    try:
        arq = caminhos.radar_dir() / ARQ
        arq.parent.mkdir(parents=True, exist_ok=True)
        if arq.exists() and arq.stat().st_size > MAX_BYTES:
            linhas = arq.read_text(encoding="utf-8").splitlines()[-2000:]
            arq.write_text("\n".join(linhas) + "\n", encoding="utf-8")
        with arq.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "evento": evento, **campos}, ensure_ascii=False) + "\n")
    except Exception:  # noqa: BLE001
        pass


def ler(horas: float = 24.0, agora: dt.datetime | None = None) -> list[dict[str, Any]]:
    agora = agora or dt.datetime.now()
    arq = caminhos.radar_dir() / ARQ
    if not arq.exists():
        return []
    corte = (agora - dt.timedelta(hours=horas)).strftime("%Y-%m-%d %H:%M:%S")
    out = []
    for linha in arq.read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(linha)
        except ValueError:
            continue
        if r.get("ts", "") >= corte:
            out.append(r)
    return out


def _pct(v: list[float], p: float) -> float | None:
    if not v:
        return None
    v = sorted(v)
    return round(v[min(len(v) - 1, int(round(p * (len(v) - 1))))], 2)


def resumo_estat(v: list[float]) -> dict[str, Any]:
    return {"n": len(v), "p50": _pct(v, 0.5), "p90": _pct(v, 0.9), "max": round(max(v), 2) if v else None}


def chance_de_leitura(instantes: list[dt.datetime], duracao_min: float) -> float | None:
    """Fracao dos instantes de inicio possiveis em que uma promocao de `duracao_min` minutos e lida pelo menos uma vez.
    Usa os horarios REAIS dos ciclos (com o atraso do agendador). Considera so o AGENDAMENTO: a oferta ainda precisa estar na lista da fonte."""
    if len(instantes) < 2:
        return None
    instantes = sorted(instantes)
    gaps = [(b - a).total_seconds() / 60.0 for a, b in zip(instantes, instantes[1:])]
    total = sum(gaps)
    return round(sum(min(g, duracao_min) for g in gaps) / total, 3) if total else None


def analisar(con, horas: float = 24.0, agora: dt.datetime | None = None, cfg_fontes: dict[str, Any] | None = None) -> dict[str, Any]:
    agora = agora or dt.datetime.now()
    cfg_fontes = cfg_fontes or {}
    ini = (agora - dt.timedelta(hours=horas)).strftime("%Y-%m-%d %H:%M:%S")
    out: dict[str, Any] = {"janela_h": horas}

    # 1. publicacao -> deteccao (MEDIDO, so onde a fonte informa a hora)
    pub: dict[str, Any] = {}
    for fonte in ("gatry", "promobit", "pelando", "hardmob"):
        frescas, antigas = [], 0
        for r in con.execute("SELECT publicado_em, detectado_em FROM ofertas WHERE fonte=? AND publicado_em IS NOT NULL AND detectado_em >= ?", (fonte, ini)):
            try:
                d = (dt.datetime.strptime(r["detectado_em"][:16], "%Y-%m-%d %H:%M") - dt.datetime.strptime(r["publicado_em"][:16], "%Y-%m-%d %H:%M")).total_seconds() / 60.0
            except ValueError:
                continue
            if 0 <= d <= LIMITE_FRESCA_MIN:
                frescas.append(d)
            elif d > LIMITE_FRESCA_MIN:
                antigas += 1   # oferta velha lida pela 1a vez (carga inicial ou atraso da propria fonte): NAO e latencia do radar
        pub[fonte] = {**resumo_estat(frescas), "medido": bool(frescas), "antigas_lidas_pela_1a_vez": antigas,
                      "nota": ("a fonte nao informa a hora da postagem: NAO MEDIDO" if fonte == "hardmob" else
                               f"so chegadas frescas (ate {LIMITE_FRESCA_MIN:.0f} min); inclui a espera ate o proximo ciclo; hora relativa 'ha X min' tem resolucao de ~1 min"
                               if frescas else f"sem chegada fresca com hora na janela ({antigas} oferta(s) antiga(s) lida(s) pela 1a vez)")}
    out["publicacao_ate_deteccao_min"] = pub

    # 2 e 3. tempos internos (MEDIDO)
    reg = ler(horas, agora)
    # cada registro "fonte" traz a MEDIANA do ciclo para aquela fonte (nao uma linha por oferta: seriam milhares); n abaixo = ciclos
    classif = [r["t_classif_ms_med"] for r in reg if r.get("evento") == "fonte" and r.get("t_classif_ms_med") is not None]
    cand = [r["t_candidato_ms_med"] for r in reg if r.get("evento") == "fonte" and r.get("t_candidato_ms_med") is not None]
    out["coleta_ate_classificacao_ms"] = {**resumo_estat(classif), "medido": bool(classif)}
    out["classificacao_ate_candidato_ms"] = {**resumo_estat(cand), "medido": bool(cand)}
    fetch = {}
    for fonte in {r["fonte"] for r in reg if r.get("evento") == "fonte"}:
        v = [r["t_coleta_s"] for r in reg if r.get("evento") == "fonte" and r["fonte"] == fonte and r.get("t_coleta_s") is not None]
        fetch[fonte] = resumo_estat(v)
    out["tempo_de_leitura_da_fonte_s"] = fetch
    out["despacho_s"] = resumo_estat([r["t_despacho_s"] for r in reg if r.get("evento") == "despacho" and r.get("t_despacho_s") is not None])
    out["ciclo_total_s"] = resumo_estat([r["t_ciclo_s"] for r in reg if r.get("evento") == "ciclo" and r.get("t_ciclo_s") is not None])

    # 4. entrega (MEDIDO desde esta versao; antes ESTIMATIVA)
    for chave, evento in (("entrega_alerta_s", "envio_alerta"), ("entrega_relatorio_s", "envio_relatorio")):
        v = [r["duracao_s"] for r in reg if r.get("evento") == evento and r.get("ok") and r.get("duracao_s") is not None]
        out[chave] = {**resumo_estat(v), "medido": bool(v), "estimativa_inferior_s": ESTIMATIVA_ENVIO_S}
    esp = [r["espera_s"] for r in reg if r.get("evento") == "envio_alerta" and r.get("espera_s") is not None]
    out["candidato_ate_envio_s"] = {**resumo_estat(esp), "medido": bool(esp)}
    ponta = [r["espera_s"] + r["duracao_s"] for r in reg if r.get("evento") == "envio_alerta" and r.get("ok") and r.get("espera_s") is not None and r.get("duracao_s") is not None]
    out["criacao_ate_confirmacao_s"] = {**resumo_estat(ponta), "medido": bool(ponta)}
    na_fila = [r["na_fila_s"] for r in reg if r.get("evento") == "envio_fila" and r.get("ok") and r.get("na_fila_s") is not None]
    out["tempo_na_fila_s"] = {**resumo_estat(na_fila), "medido": bool(na_fila)}
    out["envios_com_falha"] = sum(1 for r in reg if r.get("evento") in ("envio_alerta", "envio_relatorio", "envio_fila") and not r.get("ok"))
    out["teste_de_entrega"] = [r for r in reg if r.get("evento") == "teste_entrega"][-1:] or None

    # cobertura x intervalo e chance de ler promocao curta (MEDIDO: telemetria e horarios reais dos ciclos)
    fontes: dict[str, Any] = {}
    por_fonte: dict[str, list[Any]] = {}
    for r in con.execute("SELECT ciclo_em, fonte, status, descartes_json FROM coletas_ciclo WHERE ciclo_em >= ? AND status IN ('ok','vazio') ORDER BY ciclo_em", (ini,)):
        por_fonte.setdefault(r["fonte"], []).append(r)
    for fonte, linhas in por_fonte.items():
        if cfg_fontes.get(fonte, {}).get("lista_estatica"):
            continue
        cobs = []
        for r in linhas:
            try:
                c = json.loads(r["descartes_json"] or "{}").get("cobertura_min")
            except ValueError:
                c = None
            if c:
                cobs.append(float(c))
        inst = [dt.datetime.strptime(r["ciclo_em"], "%Y-%m-%d %H:%M:%S") for r in linhas]
        gaps = [(b - a).total_seconds() / 60.0 for a, b in zip(inst, inst[1:])]
        intervalo = float(cfg_fontes.get(fonte, {}).get("intervalo_min", 10))
        pior = min(cobs) if cobs else None
        if pior is None:
            avaliacao = "indeterminada (a fonte nao informa hora: cobertura nao medida)"
        elif pior < intervalo:
            avaliacao = "INSUFICIENTE (a lista as vezes cobre menos que o intervalo)"
        elif pior < 2 * intervalo:
            avaliacao = "margem CURTA (menos de 2x o intervalo no pior momento)"
        else:
            avaliacao = "suficiente"
        fontes[fonte] = {"ciclos": len(linhas), "intervalo_config_min": intervalo, "intervalo_real_mediano_min": round(statistics.median(gaps), 1) if gaps else None,
                         "maior_intervalo_min": round(max(gaps), 1) if gaps else None,
                         "cobertura_min": {"pior": pior, "p10": _pct(cobs, 0.1), "mediana": _pct(cobs, 0.5)} if cobs else None,
                         "avaliacao_cobertura": avaliacao,
                         "chance_de_ler_promocao_de": {f"{d} min": chance_de_leitura(inst, d) for d in (3, 5, 10, 15)}}
    out["fontes"] = fontes
    return out


def formatar(a: dict[str, Any]) -> str:
    def lin(nome: str, d: dict[str, Any], un: str, extra: str = "") -> str:
        if not d or not d.get("n"):
            return f"  {nome:42s} sem medida na janela{extra}"
        return f"  {nome:42s} n={d['n']:<4d} mediana {d['p50']} {un} | p90 {d['p90']} {un} | max {d['max']} {un}{extra}"

    L = [f"== LATENCIA | ultimas {a['janela_h']:.0f} h | [MEDIDO] = tempo real gravado; [ESTIMADO] = calculo/limite, nao medido"]
    L.append("\n1) Publicacao -> deteccao (inclui a espera do proximo ciclo)")
    for f, d in a["publicacao_ate_deteccao_min"].items():
        L.append(lin(f"[{'MEDIDO' if d['medido'] else 'NAO MEDIDO'}] {f}", d, "min", f"  ({d['nota']})" if not d.get("n") else f"  (+{d['antigas_lidas_pela_1a_vez']} antigas fora da conta)"))
    L.append("\n2) Coleta -> classificacao e 3) classificacao -> alerta (tempo de processamento)")
    L.append(lin("[MEDIDO] classificar 1 oferta (mediana por ciclo)", a["coleta_ate_classificacao_ms"], "ms"))
    L.append(lin("[MEDIDO] criar candidato e mensagem (mediana)", a["classificacao_ate_candidato_ms"], "ms"))
    L.append(lin("[MEDIDO] despacho (fim do ciclo)", a["despacho_s"], "s"))
    L.append(lin("[MEDIDO] ciclo completo", a["ciclo_total_s"], "s"))
    for f, d in a["tempo_de_leitura_da_fonte_s"].items():
        L.append(lin(f"[MEDIDO] ler a fonte {f}", d, "s"))
    L.append("\n4) Criacao -> entrega no WhatsApp")
    for chave, nome in (("entrega_alerta_s", "alerta"), ("entrega_relatorio_s", "relatorio")):
        d = a[chave]
        if d["medido"]:
            L.append(lin(f"[MEDIDO] envio de {nome}", d, "s"))
        else:
            L.append(f"  [ESTIMADO] envio de {nome}: pelo menos {d['estimativa_inferior_s']:.0f} s (esperas fixas do codigo); ainda sem medida real")
    L.append(lin("[MEDIDO] candidato -> inicio do envio", a["candidato_ate_envio_s"], "s"))
    L.append(lin("[MEDIDO] criacao -> confirmacao (ponta a ponta)", a["criacao_ate_confirmacao_s"], "s"))
    L.append(lin("[MEDIDO] tempo na fila ate a reentrega", a["tempo_na_fila_s"], "s"))
    t = a.get("teste_de_entrega")
    if t:
        t = t[0]
        L.append(f"  [MEDIDO] teste controlado de {t['ts']}: ok={t.get('ok')} | criacao->inicio {t.get('espera_s')} s | envio {t.get('duracao_s')} s | "
                 f"ponta a ponta {t.get('ponta_a_ponta_s')} s | confirmado no chat: {t.get('confirmado_no_chat')}")
    L.append("\n5) Cobertura da lista x intervalo e chance de ler promocao curta (horarios reais dos ciclos)")
    for f, d in a["fontes"].items():
        c = d["cobertura_min"]
        L.append(f"  {f:18s} ciclo {d['intervalo_config_min']:.0f} min (real: mediana {d['intervalo_real_mediano_min']}, maior {d['maior_intervalo_min']}) | "
                 f"cobertura {('pior %.0f, p10 %.0f, mediana %.0f min' % (c['pior'], c['p10'], c['mediana'])) if c else 'n/d'} => {d['avaliacao_cobertura']}")
        L.append("                     chance de ler uma promocao que dura: " + ", ".join(f"{k} = {v:.0%}" for k, v in d["chance_de_ler_promocao_de"].items() if v is not None))
    return "\n".join(L)
