"""Relatorio de efetividade: o que as fontes trouxeram, o que serviu para os 12 produtos e por que o resto foi descartado.

Diferencia AUSENCIA de ofertas (fonte respondeu, nada relevante) de FALHA do coletor (erro, sem resposta).
So conta o que foi medido: a telemetria (`coletas_ciclo`) comeca na primeira varredura depois da migracao 2.
"""

from __future__ import annotations

import datetime as dt
import json
import sqlite3
from typing import Any


def gerar(con: sqlite3.Connection, horas: float = 24.0, agora: dt.datetime | None = None) -> dict[str, Any]:
    agora = agora or dt.datetime.now()
    corte = (agora - dt.timedelta(hours=horas)).strftime("%Y-%m-%d %H:%M:%S")
    fontes: dict[str, dict[str, Any]] = {}
    descartes_total: dict[str, int] = {}
    primeiro = ultimo = None
    for r in con.execute("SELECT * FROM coletas_ciclo WHERE ciclo_em >= ? ORDER BY ciclo_em", (corte,)):
        f = fontes.setdefault(r["fonte"], {"ciclos": 0, "ok": 0, "vazia": 0, "erro": 0, "itens": 0, "casadas": 0,
                                           "cupons_extraidos": 0, "cupons_elegiveis": 0, "cupons_aplicados": 0, "ultimo_erro": None})
        f["ciclos"] += 1
        f[r["status"]] = f.get(r["status"], 0) + 1
        f["itens"] += r["itens"]
        f["casadas"] += r["casadas"]
        f["cupons_extraidos"] += r["cupons_extraidos"]
        f["cupons_aplicados"] += r["cupons_aplicados"]
        if r["erro"]:
            f["ultimo_erro"] = r["erro"][:120]
        d = json.loads(r["descartes_json"] or "{}")
        f["cupons_elegiveis"] += int(d.pop("elegiveis", 0))
        for k in ("lacuna_min", "perdido_min", "intervalo_efetivo_min"):
            d.pop(k, None)
        if d.pop("janela_intensiva", False):
            f["ciclos_em_janela_intensiva"] = f.get("ciclos_em_janela_intensiva", 0) + 1
        if d.pop("lacuna", False):
            f["ciclos_com_lacuna"] = f.get("ciclos_com_lacuna", 0) + 1
        if d.pop("transbordo", False):
            f["ciclos_com_transbordo"] = f.get("ciclos_com_transbordo", 0) + 1
        cob, buraco = d.pop("cobertura_min", None), d.pop("buraco", False)
        if cob is not None:
            f["cobertura_min"] = cob
        f["ciclos_com_buraco"] = f.get("ciclos_com_buraco", 0) + (1 if buraco else 0)
        for k, v in d.items():
            descartes_total[k] = descartes_total.get(k, 0) + int(v)
        primeiro = primeiro or r["ciclo_em"]
        ultimo = r["ciclo_em"]
    for f in fontes.values():
        if f["ciclos"] and f.get("sem_configuracao") == f["ciclos"]:
            f["diagnostico"] = "NAO CONFIGURADA (nenhum canal habilitado; nada foi lido)"
        elif f["ciclos"] and f["erro"] == f["ciclos"]:
            f["diagnostico"] = "FALHA DO COLETOR (todos os ciclos com erro)"
        elif f["erro"]:
            f["diagnostico"] = f"instavel ({f['erro']} de {f['ciclos']} ciclos com erro)"
        elif f["itens"] == 0:
            f["diagnostico"] = "sem publicacoes (a fonte respondeu vazia; nao e falha)"
        elif f["casadas"] == 0:
            f["diagnostico"] = "coletando normalmente; nenhuma publicacao era dos seus 12 produtos"
        else:
            f["diagnostico"] = "coletando e com ofertas dos seus produtos"
        if f.get("ciclos_com_lacuna") or f.get("ciclos_com_transbordo"):
            f["diagnostico"] += (f" | LACUNA DE COLETA em {f.get('ciclos_com_lacuna', 0)} ciclo(s) e transbordo em {f.get('ciclos_com_transbordo', 0)}: "
                                 "a fonte ficou sem ser lida por mais tempo do que a lista alcanca; ofertas desse intervalo podem ter sido perdidas")
        if f.get("ciclos_com_buraco"):
            f["diagnostico"] += (f" | ATENCAO: em {f['ciclos_com_buraco']} ciclo(s) a lista cobriu so ~{f.get('cobertura_min'):.0f} min, "
                                 "menos que o intervalo: pode ter perdido ofertas")
    por_produto = [dict(r) for r in con.execute(
        "SELECT produto, COUNT(*) AS ofertas, MIN(preco_final) AS menor_preco_final, "
        "SUM(CASE WHEN classe IN ('CRITICA','ALTA') THEN 1 ELSE 0 END) AS relevantes "
        "FROM ofertas WHERE produto IS NOT NULL AND ultima_vista_em >= ? GROUP BY produto ORDER BY ofertas DESC", (corte,))]
    por_classe = {r["classe"]: r["n"] for r in con.execute(
        "SELECT classe, COUNT(*) AS n FROM ofertas WHERE produto IS NOT NULL AND ultima_vista_em >= ? GROUP BY classe", (corte,))}
    alertas = {r["modo"]: r["n"] for r in con.execute("SELECT modo, COUNT(*) AS n FROM alertas WHERE enviado_em >= ? GROUP BY modo", (corte,))}
    fila = {(r["desfecho"] or "pendente"): r["n"] for r in con.execute(
        "SELECT desfecho, COUNT(*) AS n FROM outbox WHERE criado_em >= ? GROUP BY desfecho", (corte,))}
    cupons_loja = con.execute(
        "SELECT COUNT(*) FROM ofertas WHERE produto IS NULL AND cupom_codigo IS NOT NULL AND ultima_vista_em >= ?", (corte,)).fetchone()[0]
    return {
        "janela_horas": horas, "telemetria_desde": primeiro, "telemetria_ate": ultimo,
        "total_publicacoes": sum(f["itens"] for f in fontes.values()),
        "total_casadas": sum(f["casadas"] for f in fontes.values()),
        "fontes": fontes, "descartes": descartes_total, "por_produto": por_produto, "por_classe": por_classe,
        "alertas": alertas, "fila": fila, "cupons_de_loja_registrados": cupons_loja,
    }


def formatar(rel: dict[str, Any]) -> str:
    L = [f"== EFETIVIDADE | ultimas {rel['janela_horas']:.0f} h | telemetria {rel['telemetria_desde']} ate {rel['telemetria_ate']}"]
    if not rel["fontes"]:
        return L[0] + "\nSem telemetria no periodo (rode a varredura ou aguarde o proximo ciclo)."
    L.append(f"Publicacoes coletadas: {rel['total_publicacoes']} | casadas com seus 12 produtos: {rel['total_casadas']}")
    L.append("\n-- Por fonte (ausencia de oferta x falha do coletor)")
    for nome, f in rel["fontes"].items():
        L.append(f"  {nome}: {f['ciclos']} ciclos (ok {f['ok']}, vazia {f['vazia']}, erro {f['erro']}, sem config. {f.get('sem_configuracao', 0)}) | itens {f['itens']} | casadas {f['casadas']} "
                 f"| cupons extraidos {f['cupons_extraidos']}, elegiveis {f['cupons_elegiveis']}, aplicados ao preco {f['cupons_aplicados']}")
        L.append(f"      => {f['diagnostico']}" + (f" | ultimo erro: {f['ultimo_erro']}" if f["ultimo_erro"] else ""))
    L.append("\n-- Motivos de descarte (publicacoes que nao viraram oportunidade)")
    for k, v in sorted(rel["descartes"].items(), key=lambda kv: -kv[1]):
        L.append(f"  {v:5d}  {k}")
    L.append("\n-- Ofertas dos seus produtos")
    if rel["por_produto"]:
        for p in rel["por_produto"]:
            L.append(f"  {p['produto']}: {p['ofertas']} oferta(s), {p['relevantes']} relevante(s), menor preco final visto {p['menor_preco_final']}")
    else:
        L.append("  nenhuma oferta de comunidade casou com os 12 produtos no periodo")
    L.append(f"\nClasses: {rel['por_classe'] or '-'} | alertas: {rel['alertas'] or '-'} | fila: {rel['fila'] or '-'} | cupons de loja registrados: {rel['cupons_de_loja_registrados']}")
    return "\n".join(L)
