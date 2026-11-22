"""Qualidade e estabilidade dos coletores: completude dos campos, frescor, valor MARGINAL (itens que so aquela fonte traz) e latencia.

Regra para aceitar uma fonte nova (medida, nao opiniao): so entra se (a) trouxer itens que as demais nao trazem
(`unicos_pct` relevante) E (b) tiver preco/URL/hora confiaveis (completude) E (c) for estavel (sem erro recorrente).
"""

from __future__ import annotations

import datetime as dt
import re
import statistics
import time
from typing import Any, Callable

from .catalogo import normalizar
from .modelos import Oferta

_STOP = {"para", "com", "sem", "por", "uma", "dos", "das", "que", "mais", "novo", "nova", "oferta", "promocao", "cupom", "frete", "gratis", "loja"}


def tokens(titulo: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]{3,}", normalizar(titulo)) if t not in _STOP}


def _jaccard(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def cobertura_min(ofertas: list[Oferta], agora: dt.datetime | None = None) -> float | None:
    """Ate onde (em minutos) a lista recente alcanca para tras. Tem que ser MAIOR que o intervalo entre ciclos, senao ha buraco."""
    agora = agora or dt.datetime.now()
    recentes = [o for o in ofertas if (o.canal or "").startswith("recentes") or o.canal in ("promocoes",)] or list(ofertas)
    idades = []
    for o in recentes:
        if (o.extras or {}).get("tipo") == "cupom_loja" or (o.canal or "").startswith("cupom_loja"):
            continue
        try:
            idades.append((agora - dt.datetime.strptime(o.publicado_em[:16], "%Y-%m-%d %H:%M")).total_seconds() / 60.0)
        except (TypeError, ValueError):
            pass
    return round(max(idades), 0) if idades else None


def completude(ofertas: list[Oferta], agora: dt.datetime | None = None) -> dict[str, Any]:
    agora = agora or dt.datetime.now()
    n = len(ofertas)
    if not n:
        return {"n": 0}

    def pct(f: Callable[[Oferta], bool]) -> float:
        return round(100.0 * sum(1 for o in ofertas if f(o)) / n, 1)

    idades: list[float] = []
    for o in ofertas:
        try:
            idades.append((agora - dt.datetime.strptime(o.publicado_em[:16], "%Y-%m-%d %H:%M")).total_seconds() / 60.0)
        except (TypeError, ValueError):
            pass
    ids = [o.id_externo for o in ofertas]
    return {
        "n": n, "preco_pct": pct(lambda o: o.preco_anunciado is not None), "url_pct": pct(lambda o: bool(o.url)),
        "hora_pct": pct(lambda o: bool(o.publicado_em)), "loja_pct": pct(lambda o: bool(o.loja)),
        "cupom_pct": pct(lambda o: bool(o.cupom_codigo)), "ids_duplicados": n - len(set(ids)),
        "idade_mediana_min": round(statistics.median(idades), 0) if idades else None,
        "frescas_6h_pct": round(100.0 * sum(1 for i in idades if i <= 360) / len(idades), 1) if idades else None,
    }


def sobreposicao(por_fonte: dict[str, list[Oferta]], limiar: float = 0.5) -> dict[str, dict[str, Any]]:
    """Para cada fonte: quantos dos seus itens tem um 'gemeo' (titulo parecido) em OUTRA fonte. Unicos = valor marginal."""
    tk = {f: [(o, tokens(o.titulo)) for o in os_] for f, os_ in por_fonte.items()}
    saida: dict[str, dict[str, Any]] = {}
    for f, itens in tk.items():
        unicos = 0
        for o, t in itens:
            gemeo = any(_jaccard(t, t2) >= limiar and len(t & t2) >= 3
                        for g, outros in tk.items() if g != f for _, t2 in outros)
            unicos += 0 if gemeo else 1
        saida[f] = {"itens": len(itens), "unicos": unicos, "unicos_pct": round(100.0 * unicos / len(itens), 1) if itens else None}
    return saida


def estabilidade(con, horas: float = 24.0, agora: dt.datetime | None = None) -> dict[str, dict[str, Any]]:
    """Das medidas reais em `coletas_ciclo` (nao de uma execucao so)."""
    agora = agora or dt.datetime.now()
    corte = (agora - dt.timedelta(hours=horas)).strftime("%Y-%m-%d %H:%M:%S")
    saida: dict[str, dict[str, Any]] = {}
    for r in con.execute("SELECT fonte, status, itens FROM coletas_ciclo WHERE ciclo_em >= ? ORDER BY ciclo_em", (corte,)):
        s = saida.setdefault(r["fonte"], {"ciclos": 0, "erros": 0, "vazias": 0, "sem_config": 0, "itens": []})
        s["ciclos"] += 1
        s["erros"] += r["status"] == "erro"
        s["vazias"] += r["status"] == "vazia"
        s["sem_config"] += r["status"] == "sem_configuracao"
        if r["status"] in ("ok", "vazia"):
            s["itens"].append(r["itens"])
    for s in saida.values():
        it = s.pop("itens")
        validos = s["ciclos"] - s["sem_config"]
        s["disponibilidade_pct"] = round(100.0 * (validos - s["erros"]) / validos, 1) if validos else None
        s["itens_media"] = round(statistics.mean(it), 1) if it else None
        s["itens_min_max"] = (min(it), max(it)) if it else None
        s["variacao_itens_pct"] = round(100.0 * statistics.pstdev(it) / statistics.mean(it), 1) if len(it) > 1 and statistics.mean(it) else None
    return saida


def lacunas_historicas(con, horas: float = 24.0, agora: dt.datetime | None = None, cfg_fontes: dict[str, Any] | None = None) -> dict[str, Any]:
    """Janelas em que uma fonte ficou SEM ser lida por mais tempo do que a lista dela alcanca para tras: o que foi postado ali pode ter
    se perdido. Usa os ciclos gravados (`coletas_ciclo`). Alcance = menor cobertura medida entre os dois ciclos vizinhos, ou a estimativa
    `cobertura_estimada_min` da configuracao (HardMOB nao informa hora). Sem alcance conhecido a janela e listada como INDETERMINADA."""
    import json

    agora = agora or dt.datetime.now()
    ini = (agora - dt.timedelta(hours=horas)).strftime("%Y-%m-%d %H:%M:%S")
    cfg_fontes = cfg_fontes or {}
    por_fonte: dict[str, list[Any]] = {}
    for r in con.execute("SELECT ciclo_em, fonte, status, descartes_json FROM coletas_ciclo WHERE ciclo_em >= ? AND status IN ('ok','vazio') ORDER BY ciclo_em", (ini,)):
        por_fonte.setdefault(r["fonte"], []).append(r)
    saida: dict[str, Any] = {}
    for fonte, linhas in por_fonte.items():
        if cfg_fontes.get(fonte, {}).get("lista_estatica"):
            continue  # cupons de loja: nao ha "oferta que saiu da lista sem ser vista"
        janelas = []
        for a, b in zip(linhas, linhas[1:]):
            try:
                gap = (dt.datetime.strptime(b["ciclo_em"], "%Y-%m-%d %H:%M:%S") - dt.datetime.strptime(a["ciclo_em"], "%Y-%m-%d %H:%M:%S")).total_seconds() / 60
            except ValueError:
                continue
            cobs = []
            for x in (a, b):
                try:
                    c = json.loads(x["descartes_json"] or "{}").get("cobertura_min")
                except ValueError:
                    c = None
                if c:
                    cobs.append(float(c))
            alcance = min(cobs) if cobs else (float(cfg_fontes.get(fonte, {}).get("cobertura_estimada_min") or 0) or None)
            if alcance is None:
                if gap > 30:
                    janelas.append({"de": a["ciclo_em"], "ate": b["ciclo_em"], "sem_ler_min": round(gap), "alcance_min": None, "perdido_min": None, "situacao": "indeterminada (cobertura desconhecida)"})
            elif gap > alcance:
                janelas.append({"de": a["ciclo_em"], "ate": b["ciclo_em"], "sem_ler_min": round(gap), "alcance_min": round(alcance), "perdido_min": round(gap - alcance), "situacao": "LACUNA"})
        gaps = [(dt.datetime.strptime(b["ciclo_em"], "%Y-%m-%d %H:%M:%S") - dt.datetime.strptime(a["ciclo_em"], "%Y-%m-%d %H:%M:%S")).total_seconds() / 60
                for a, b in zip(linhas, linhas[1:])]
        saida[fonte] = {"ciclos": len(linhas), "maior_intervalo_min": round(max(gaps)) if gaps else None, "lacunas": janelas,
                        "perdido_total_min": sum(j["perdido_min"] or 0 for j in janelas)}
    return saida


def medir_ao_vivo(coletores: dict[str, Callable[[dict], list[Oferta]]], cfgs: dict[str, dict]) -> dict[str, Any]:
    """Coleta UMA vez cada fonte, medindo latencia. Erro de uma fonte nao impede as outras."""
    por_fonte: dict[str, list[Oferta]] = {}
    lat: dict[str, float] = {}
    erros: dict[str, str] = {}
    for f, fn in coletores.items():
        t0 = time.time()
        try:
            por_fonte[f] = fn(cfgs.get(f, {}))
        except Exception as exc:  # noqa: BLE001
            erros[f] = str(exc)[:120]
            por_fonte[f] = []
        lat[f] = round(time.time() - t0, 1)
    def eh_cupom(o: Oferta) -> bool:
        return (o.extras or {}).get("tipo") == "cupom_loja" or (o.canal or "").startswith("cupom_loja")

    # Cupom de loja nao tem preco nem URL de produto: medir junto distorce a completude (erro de leitura da 1a versao desta metrica).
    produtos = {f: [o for o in os_ if not eh_cupom(o)] for f, os_ in por_fonte.items()}
    comp = {f: {**completude(produtos[f]), "cupons_de_loja": sum(1 for o in os_ if eh_cupom(o)), "total_itens": len(os_)}
            for f, os_ in por_fonte.items()}
    for f, ps in produtos.items():  # janela de cobertura: quanto tempo para tras a lista alcanca (precisa ser > intervalo do ciclo)
        idades = []
        recentes = [o for o in ps if (o.canal or "").startswith("recentes")]  # paginas de loja tem itens antigos e mascaram o buraco
        for o in (recentes or ps):
            try:
                idades.append((dt.datetime.now() - dt.datetime.strptime(o.publicado_em[:16], "%Y-%m-%d %H:%M")).total_seconds() / 60.0)
            except (TypeError, ValueError):
                pass
        comp[f]["cobertura_min"] = round(max(idades), 0) if idades else None
    return {"completude": comp, "sobreposicao": sobreposicao({f: ps for f, ps in produtos.items() if ps}), "latencia_s": lat, "erros": erros}
