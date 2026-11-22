"""Ciclo de um relatorio periodico (robos, ares, chuveiro): coletar, comparar, persistir, enviar.

Regras que antes nao existiam (falhas reais de 20/11/2026):
- a comparacao usa a ULTIMA COLETA BOA, nao a ultima coleta;
- coleta degradada (rede lenta) e repetida uma vez e, se continuar ruim,
  nao sobrescreve estado.json e o relatorio sai com aviso de coleta parcial;
- mensagem que nao saiu vai para a fila (outbox) e e reenviada no ciclo seguinte.
"""

from __future__ import annotations

import json
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any, Callable

from . import db, historico, maquina, outbox


def _aviso(msg: str) -> None:
    print(f"[radar] {msg}", file=sys.stderr, flush=True)


def _abrir_banco() -> sqlite3.Connection | None:
    try:
        return db.abrir()
    except Exception as exc:  # noqa: BLE001 - o relatorio nao pode depender do banco
        _aviso(f"banco indisponivel ({exc}); seguindo sem fila e sem estatisticas")
        return None


def _modelos_com_preco(coleta: dict[str, Any]) -> int:
    return sum(1 for m in (coleta.get("modelos") or {}).values() if (m or {}).get("melhor_preco") is not None)


def executar_ciclo(
    *,
    rotulo: str,
    origem: str,
    coletar: Callable[[], dict[str, Any]],
    montar_mensagem: Callable[..., str],
    estado_path: Path,
    hist_path: Path,
    enviar_zap: bool,
    enviar_fn: Callable[[str], tuple[bool, str]],
    primeira_vez: bool = False,
    persistir: bool = True,
    pausa_retentativa_s: float = 45.0,
) -> int:
    if enviar_zap and persistir:
        pode, motivo = maquina.pode_rodar()
        if not pode:
            _aviso(f"{rotulo}: {motivo}")  # execucao direta do script noutra maquina: nao coleta, nao envia, nao grava
            return 0
    registros = historico.carregar_jsonl(hist_path, origem)
    anterior = historico.ultimo_estado_bom(registros)
    if anterior is None and estado_path.exists():
        try:
            anterior = json.loads(estado_path.read_text(encoding="utf-8"))
        except Exception:
            anterior = None

    atual = coletar()
    degradada, motivo = historico.esta_degradada(atual, anterior)
    if degradada and pausa_retentativa_s >= 0:
        _aviso(f"{rotulo}: coleta degradada ({motivo}); nova tentativa em {pausa_retentativa_s:.0f}s")
        time.sleep(pausa_retentativa_s)
        segunda = coletar()
        if _modelos_com_preco(segunda) >= _modelos_com_preco(atual):
            atual = segunda
        degradada, motivo = historico.esta_degradada(atual, anterior)

    mensagem = montar_mensagem(atual, anterior, primeira_vez=primeira_vez)
    if degradada:
        ref = (anterior or {}).get("coletado_em", "n/d")
        mensagem = (
            f"⚠️ *Coleta parcial:* {motivo}. Itens 'indisponivel' abaixo podem ser falha de leitura, "
            f"nao falta de estoque. Comparacoes usam a ultima coleta boa ({ref}).\n\n{mensagem}"
        )
    # Ofertas que o limite de alertas segurou (so com alertas REAIS ativos; em sombra o bloco e vazio). Nunca derruba o relatorio.
    try:
        con_b = _abrir_banco()
        if con_b is not None:
            try:
                from . import prioridade, ranking
                mensagem += prioridade.bloco_retidas(con_b, ranking.carregar_regras(), origem)
            finally:
                con_b.close()
    except Exception as exc:  # noqa: BLE001
        _aviso(f"bloco de ofertas retidas indisponivel ({exc})")
    print(mensagem)

    con = _abrir_banco()
    if persistir:
        atual_gravar = dict(atual)
        if degradada:
            atual_gravar["degradada"] = True
        hist_path.parent.mkdir(parents=True, exist_ok=True)
        with hist_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(atual_gravar, ensure_ascii=False) + "\n")
        if degradada:
            _aviso(f"{rotulo}: estado.json preservado (coleta degradada nao vira referencia)")
        else:
            estado_path.write_text(json.dumps(atual, ensure_ascii=False, indent=2), encoding="utf-8")
        if con is not None:
            try:
                historico.registrar_observacao(con, origem, atual, degradada)
            except Exception as exc:  # noqa: BLE001
                _aviso(f"nao consegui registrar no banco: {exc}")

    if not enviar_zap:
        if con is not None:
            con.close()
        return 0

    _t = time.perf_counter()
    ok, info = enviar_fn(mensagem)
    try:
        from . import latencia
        latencia.registrar("envio_relatorio", origem=origem, ok=bool(ok), duracao_s=round(time.perf_counter() - _t, 2), chars=len(mensagem))
    except Exception:  # noqa: BLE001 - medir nunca derruba o relatorio
        pass
    print(f"[ZAP] ok={ok} | {info}")
    if not ok and con is not None:
        outbox.enfileirar(con, mensagem, origem, info)
        _aviso(f"{rotulo}: mensagem na fila para reenvio ({info})")
    if ok and con is not None:
        for _id, ok_r, info_r in outbox.drenar(con, enviar_fn):
            print(f"[ZAP-REENVIO] id={_id} ok={ok_r} | {info_r}")
    if con is not None:
        con.close()
    return 0 if ok else 1
