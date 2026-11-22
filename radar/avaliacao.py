"""Avaliacao do reconhecimento de produtos sobre a amostra rotulada (tests/corpus/radar_ofertas_rotuladas.yaml).

Metricas (positivos e negativos; ambiguos ficam fora e sao reportados a parte):
  TP  esperado=P e reconheceu P
  FN  esperado=P e nao reconheceu (ou reconheceu outro produto)
  FP  reconheceu algo onde o esperado era nenhum, OU reconheceu produto diferente do esperado
  TN  esperado nenhum e nao reconheceu
  precisao = TP/(TP+FP) | recuperacao = TP/(TP+FN) | taxa de falso positivo = FP/(FP+TN)
Nao infere eficacia pela ausencia de ofertas: so conta o que tem rotulo.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

from . import caminhos, catalogo

ARQ_CORPUS = caminhos.RAIZ / "tests" / "corpus" / "radar_ofertas_rotuladas.yaml"


def carregar_corpus(caminho: Path | None = None) -> list[dict[str, Any]]:
    return (yaml.safe_load((caminho or ARQ_CORPUS).read_text(encoding="utf-8")) or {}).get("itens") or []


CONJUNTOS = ("treino", "regressao", "independente")
# treino      itens que EU vi ao construir/ajustar o catalogo (nao servem para medir desempenho: so provam que nao regrediu)
# regressao   itens escritos para travar uma regra ou um defeito ja corrigido (garantia contra voltar o erro; otimista por construcao)
# independente itens REAIS rotulados por leitura do titulo, ANTES de rodar o reconhecimento sobre eles; unico conjunto que mede mercado.
#             Um item que gerou correcao guarda `primeira_passada: {obtido: ...}`: a medida "antes da correcao" e a que vale como desempenho;
#             depois da correcao ele passa a ser regressao tambem.
ORIGENS_INDEPENDENTES = ("real_cotacao_independente", "real_ao_vivo", "real_gatry_historico")  # compatibilidade


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float] | None:
    """Intervalo de confianca de 95% (Wilson) para uma proporcao k/n. Mostra o quanto uma amostra pequena PODE esconder."""
    if n <= 0:
        return None
    p = k / n
    den = 1 + z * z / n
    centro = (p + z * z / (2 * n)) / den
    meia = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / den
    return round(max(0.0, centro - meia), 3), round(min(1.0, centro + meia), 3)


def _taxas(tp: int, fp: int, fn: int, tn: int) -> dict[str, Any]:
    def d(a: int, b: int) -> float | None:
        return round(a / b, 4) if b else None
    return {"TP": tp, "FP": fp, "FN": fn, "TN": tn, "precisao": d(tp, tp + fp), "recuperacao": d(tp, tp + fn),
            "taxa_falso_positivo": d(fp, fp + tn), "recuperacao_ic95": wilson(tp, tp + fn),
            "falso_positivo_ic95": wilson(fp, fp + tn)}


def _contar(k: dict[str, int], esperado: str | None, got: str | None) -> None:
    if esperado and got == esperado:
        k["tp"] += 1
    elif esperado and got is None:
        k["fn"] += 1
    elif esperado and got != esperado:
        k["fp"] += 1  # reconheceu o produto ERRADO: erra a oferta e acusa um produto que nao e
        k["fn"] += 1
    elif not esperado and got is not None:
        k["fp"] += 1
    else:
        k["tn"] += 1


def avaliar(itens: list[dict[str, Any]] | None = None, cat: dict[str, Any] | None = None) -> dict[str, Any]:
    itens = itens if itens is not None else carregar_corpus()
    cat = cat or catalogo.carregar()
    cont = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0, "tn": 0})
    erros: list[dict[str, Any]] = []
    ambiguos: list[dict[str, Any]] = []
    for it in itens:
        c = catalogo.identificar(it["texto"], cat)
        got = c.produto_id if c else None
        avisos = list(c.avisos) if c else []
        caso = it["caso"]
        if caso == "ambiguo":
            ok = got == it.get("esperado") and (not it.get("aviso") or it["aviso"] in avisos)
            ambiguos.append({"id": it["id"], "ok": ok, "esperado": it.get("esperado"), "aviso_esperado": it.get("aviso"),
                             "obtido": got, "avisos": avisos, "texto": it["texto"][:90]})
            continue
        esperado = it.get("esperado") if caso == "positivo" else None
        conjunto = it.get("conjunto") or ("independente" if it["origem"] in ORIGENS_INDEPENDENTES else "treino")
        grupos = ["total", it["origem"], f"conjunto:{conjunto}"]
        if it["origem"] in ORIGENS_INDEPENDENTES:
            grupos.append("independentes_nao_vistos_na_calibracao")
        for chave in grupos:
            _contar(cont[chave], esperado, got)
        if conjunto == "independente":  # medida ANTES da correcao: o que o reconhecimento fez na primeira vez que viu o item
            got1 = it["primeira_passada"].get("obtido") if it.get("primeira_passada") else got
            _contar(cont["conjunto:independente (primeira passada, antes das correcoes)"], esperado, got1)
        if (esperado or None) != got:
            erros.append({"id": it["id"], "origem": it["origem"], "tipo": "FN" if esperado and not got else "FP",
                          "esperado": esperado, "obtido": got, "texto": it["texto"][:100], "calibracao": bool(it.get("calibracao"))})
    return {
        "itens": len(itens),
        "por_origem": {o: _taxas(**{k: v for k, v in c.items()}) for o, c in cont.items()},
        "ambiguos": ambiguos,
        "ambiguos_ok": sum(1 for a in ambiguos if a["ok"]),
        "erros": erros,
    }


def formatar(rel: dict[str, Any]) -> str:
    L = [f"== AVALIACAO DO RECONHECIMENTO | {rel['itens']} itens rotulados"]
    L.append("  (so 'conjunto:independente' mede mercado; treino e regressao provam apenas que nao regrediu)")
    for origem, t in rel["por_origem"].items():
        L.append(f"  {origem[:62]:62s} TP {t['TP']:3d} FP {t['FP']:3d} FN {t['FN']:3d} TN {t['TN']:3d} | precisao {t['precisao']} "
                 f"| recuperacao {t['recuperacao']} IC95 {t['recuperacao_ic95']} | falso positivo {t['taxa_falso_positivo']} IC95 {t['falso_positivo_ic95']}")
    L.append(f"  ambiguos com o comportamento esperado: {rel['ambiguos_ok']} de {len(rel['ambiguos'])}")
    for a in rel["ambiguos"]:
        if not a["ok"]:
            L.append(f"    AMBIGUO FORA DO ESPERADO {a['id']}: esperado {a['esperado']}+{a['aviso_esperado']}, obtido {a['obtido']}+{a['avisos']} | {a['texto']}")
    for e in rel["erros"]:
        L.append(f"  ERRO {e['tipo']} {e['id']} ({e['origem']}): esperado {e['esperado']}, obtido {e['obtido']} | {e['texto']}")
    return "\n".join(L)
