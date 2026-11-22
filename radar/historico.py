"""Historico de precos: leitura do JSONL original, deteccao de coleta degradada e estatisticas.

O historico.jsonl dos rastreadores continua sendo a fonte original (append-only).
Aqui ele e lido, comparado e copiado de forma idempotente para a tabela
`observacoes`. Preco None significa "sem leitura/indisponivel", nunca zero.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import sqlite3
from pathlib import Path
from typing import Any

from . import correcoes

LIMITE_TIMEOUTS = 4  # timeouts de navegacao na mesma rodada que denunciam rede ruim
LIMITE_FALTANTES = 0.5  # fracao dos modelos que tinham preco e agora nao tem


def carregar_jsonl(caminho: Path, origem: str | None = None) -> list[dict[str, Any]]:
    """Le o historico.jsonl. Com `origem`, aplica as correcoes versionadas (o arquivo nunca e alterado)."""
    if not caminho.exists():
        return []
    registros: list[dict[str, Any]] = []
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha:
            continue
        try:
            reg = json.loads(linha)
        except Exception:
            continue
        if isinstance(reg, dict):
            registros.append(reg)
    return correcoes.aplicar(registros, origem) if origem else registros


def _varrer(obj: Any):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k, v
            yield from _varrer(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _varrer(v)


def contar_timeouts(coleta: dict[str, Any]) -> int:
    """Quantas leituras da rodada estouraram o tempo (sintoma de rede lenta, nao de produto)."""
    return sum(
        1 for k, v in _varrer(coleta) if k == "erro" and isinstance(v, str) and "timeout" in v.lower()
    )


def _com_preco(coleta: dict[str, Any] | None) -> set[str]:
    return {
        k for k, m in ((coleta or {}).get("modelos") or {}).items() if (m or {}).get("melhor_preco") is not None
    }


def esta_degradada(atual: dict[str, Any], referencia: dict[str, Any] | None) -> tuple[bool, str]:
    """Decide se a rodada parece falha de leitura (e nao mudanca real de mercado)."""
    timeouts = contar_timeouts(atual)
    tinham = _com_preco(referencia)
    perdidos = {k for k in tinham if k not in _com_preco(atual)}
    rede_ruim = timeouts >= LIMITE_TIMEOUTS
    rede_suspeita = timeouts >= 2 and bool(perdidos)
    perda_forte = len(tinham) >= 2 and len(perdidos) >= math.ceil(LIMITE_FALTANTES * len(tinham))
    razoes: list[str] = []
    if timeouts:
        razoes.append(f"{timeouts} leituras estouraram o tempo")
    if perdidos:
        razoes.append(f"{len(perdidos)} de {len(tinham)} modelos que tinham preco ficaram sem leitura")
    # Perda isolada de preco, sem sinal de rede, pode ser falta de estoque real: nao e degradacao.
    return (rede_ruim or rede_suspeita or perda_forte), "; ".join(razoes)


def ultimo_estado_bom(registros: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Ultimo registro do historico que nao foi degradacao em relacao ao anterior bom."""
    bom: dict[str, Any] | None = None
    for reg in registros:
        if reg.get("degradada"):
            continue
        degradada, _ = esta_degradada(reg, bom) if bom else (False, "")
        if not degradada:
            bom = reg
    return bom


def _hash_obs(origem: str, produto: str, coletado_em: str, preco: float | None, onde: str | None) -> str:
    base = f"{origem}|{produto}|{coletado_em}|{preco}|{onde}"
    return hashlib.sha1(base.encode("utf-8")).hexdigest()


def importar_para_db(con: sqlite3.Connection, origem: str, caminho_jsonl: Path) -> dict[str, int]:
    """Copia o historico.jsonl para `observacoes` (idempotente). Retorna contadores."""
    # O banco guarda o valor BRUTO; correcoes entram como campos de auditoria (sincronizar_correcoes), nunca por sobrescrita.
    registros = carregar_jsonl(caminho_jsonl)
    novas = vistas = degradadas = 0
    bom: dict[str, Any] | None = None
    for reg in registros:
        degr_flag = bool(reg.get("degradada"))
        if not degr_flag and bom is not None:
            degr_flag, _ = esta_degradada(reg, bom)
        if not degr_flag:
            bom = reg
        degradadas += 1 if degr_flag else 0
        coletado = str(reg.get("coletado_em") or "")
        for chave, mod in (reg.get("modelos") or {}).items():
            preco = mod.get("melhor_preco")
            preco = float(preco) if isinstance(preco, (int, float)) else None
            onde = mod.get("melhor_onde")
            h = _hash_obs(origem, chave, coletado, preco, onde)
            cur = con.execute(
                "INSERT OR IGNORE INTO observacoes "
                "(origem, produto, coletado_em, preco_entregue, onde, parcelamento, validacao, degradada, hash) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (origem, chave, coletado, preco, onde, mod.get("melhor_parcelamento"), "COLETA_PROPRIA", int(degr_flag), h),
            )
            if cur.rowcount:
                novas += 1
            else:
                vistas += 1
    con.commit()
    corrigidas = sincronizar_correcoes(con)
    return {"registros": len(registros), "observacoes_novas": novas, "ja_existiam": vistas, "rodadas_degradadas": degradadas,
            "correcoes_aplicadas": corrigidas}


def sincronizar_correcoes(con: sqlite3.Connection, lista: list[dict[str, Any]] | None = None) -> int:
    """Marca no banco as observacoes cobertas por config/radar_correcoes.yaml (idempotente).

    `melhor_preco: null` invalida a leitura; com valor, grava `preco_corrigido`. O valor bruto permanece
    em `preco_entregue` para auditoria. As estatisticas usam o corrigido e ignoram as invalidas.
    """
    n = 0
    for c in (lista if lista is not None else correcoes.carregar()):
        novo = c.get("melhor_preco")
        cur = con.execute(
            "UPDATE observacoes SET invalida = ?, preco_corrigido = ?, correcao_motivo = ? "
            "WHERE origem = ? AND produto = ? AND coletado_em = ?",
            (1 if novo is None else 0, novo, str(c.get("motivo", ""))[:400], c.get("origem"), c.get("produto"), str(c.get("coletado_em"))),
        )
        n += cur.rowcount
    con.commit()
    return n


def reconstruir_observacoes(con: sqlite3.Connection, origem: str, caminho_jsonl: Path) -> dict[str, int]:
    """Apaga e recria as observacoes de uma origem a partir do JSONL bruto (que e a fonte de verdade)."""
    con.execute("DELETE FROM observacoes WHERE origem = ?", (origem,))
    con.commit()
    return importar_para_db(con, origem, caminho_jsonl)


def registrar_observacao(
    con: sqlite3.Connection,
    origem: str,
    coleta: dict[str, Any],
    degradada: bool,
) -> int:
    """Grava as observacoes de uma coleta recem-feita (sem reler o arquivo)."""
    novas = 0
    coletado = str(coleta.get("coletado_em") or "")
    for chave, mod in (coleta.get("modelos") or {}).items():
        preco = mod.get("melhor_preco")
        preco = float(preco) if isinstance(preco, (int, float)) else None
        onde = mod.get("melhor_onde")
        cur = con.execute(
            "INSERT OR IGNORE INTO observacoes "
            "(origem, produto, coletado_em, preco_entregue, onde, parcelamento, validacao, degradada, hash) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (origem, chave, coletado, preco, onde, mod.get("melhor_parcelamento"), "COLETA_PROPRIA", int(degradada),
             _hash_obs(origem, chave, coletado, preco, onde)),
        )
        novas += cur.rowcount
    con.commit()
    return novas


def preco_referencia(con: sqlite3.Connection, produto: str, agora: dt.datetime | None = None, max_horas: float = 36.0) -> float | None:
    """Melhor preco ATUAL ja conhecido do produto (ultima coleta propria valida do rastreador, com correcoes), ou None se velho/inexistente.

    E o que os relatorios de 08/14/20h ja mostram: oferta igual ou pior que isto nao e novidade e nao merece alerta urgente."""
    agora = agora or dt.datetime.now()
    r = con.execute(
        "SELECT coletado_em, COALESCE(preco_corrigido, preco_entregue) AS p FROM observacoes WHERE produto = ? "
        "AND COALESCE(preco_corrigido, preco_entregue) IS NOT NULL AND degradada = 0 AND invalida = 0 AND validacao = 'COLETA_PROPRIA' "
        "ORDER BY coletado_em DESC LIMIT 1", (produto,)).fetchone()
    if not r:
        return None
    try:
        idade_h = (agora - dt.datetime.strptime(r["coletado_em"], "%Y-%m-%d %H:%M")).total_seconds() / 3600
    except ValueError:
        return None
    return float(r["p"]) if 0 <= idade_h <= max_horas else None


def estatisticas(con: sqlite3.Connection, produto: str, agora: dt.datetime | None = None) -> dict[str, Any]:
    """Menor/maior preco validado (coleta propria, nao degradada) por janela. None = dados insuficientes."""
    agora = agora or dt.datetime.now()
    linhas = con.execute(
        "SELECT coletado_em, COALESCE(preco_corrigido, preco_entregue) AS preco FROM observacoes "
        "WHERE produto = ? AND COALESCE(preco_corrigido, preco_entregue) IS NOT NULL AND degradada = 0 AND invalida = 0 "
        "AND validacao = 'COLETA_PROPRIA' ORDER BY coletado_em",
        (produto,),
    ).fetchall()
    pontos: list[tuple[dt.datetime, float]] = []
    for r in linhas:
        try:
            pontos.append((dt.datetime.strptime(r["coletado_em"], "%Y-%m-%d %H:%M"), float(r["preco"])))
        except ValueError:
            continue

    def janela(dias: int | None) -> dict[str, Any]:
        corte = None if dias is None else agora - dt.timedelta(days=dias)
        vals = [p for t, p in pontos if corte is None or t >= corte]
        if not vals:
            return {"n": 0, "menor": None, "maior": None, "mediana": None}
        ordenados = sorted(vals)
        meio = len(ordenados) // 2
        mediana = ordenados[meio] if len(ordenados) % 2 else (ordenados[meio - 1] + ordenados[meio]) / 2
        return {"n": len(vals), "menor": min(vals), "maior": max(vals), "mediana": round(mediana, 2)}

    primeira = pontos[0][0] if pontos else None
    return {
        "produto": produto,
        "observacoes_validas": len(pontos),
        "desde": primeira.strftime("%Y-%m-%d %H:%M") if primeira else None,
        "historico_total": janela(None),
        "ultimos_7_dias": janela(7),
        "ultimos_30_dias": janela(30),
        "ultimos_90_dias": janela(90),
        "cobertura_dias": (agora - primeira).days if primeira else 0,
    }
