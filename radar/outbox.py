"""Fila de saida do WhatsApp com validade.

- Relatorio: reenviado ate `ttl_relatorio_horas` (padrao 24 h), sempre rotulado com a hora original.
- Alerta urgente: validade curta (`ttl_alerta_min`, padrao 30 min). Depois disso so sai se a oferta for
  REVALIDADA na fonte (continua ativa e sem preco pior); senao e descartada com desfecho registrado.
  Alerta nunca e entregue como "ativo" sem essa checagem.
Nada e marcado enviado sem confirmacao do canal; nada e reenviado duas vezes.
"""

from __future__ import annotations

import datetime as dt
import time
import sqlite3
from typing import Any, Callable

from .db import agora

MAX_TENTATIVAS = 6
TTL_RELATORIO_H = 24.0
TTL_ALERTA_MIN = 30.0


def _fmt(d: dt.datetime) -> str:
    return d.strftime("%Y-%m-%d %H:%M:%S")


def enfileirar(
    con: sqlite3.Connection, texto: str, origem: str, erro: str, *, tipo: str = "relatorio",
    ttl_min: float | None = None, oferta_id: int | None = None, agora_dt: dt.datetime | None = None,
) -> int:
    agora_dt = agora_dt or dt.datetime.now()
    if ttl_min is None:
        ttl_min = TTL_ALERTA_MIN if tipo == "alerta" else TTL_RELATORIO_H * 60
    cur = con.execute(
        "INSERT INTO outbox (criado_em, origem, texto, tentativas, ultimo_erro, tipo, expira_em, oferta_id) VALUES (?,?,?,1,?,?,?,?)",
        (_fmt(agora_dt), origem, texto, erro[:300], tipo, _fmt(agora_dt + dt.timedelta(minutes=ttl_min)), oferta_id),
    )
    con.commit()
    return int(cur.lastrowid)


def encerrar_vencidas(con: sqlite3.Connection, agora_dt: dt.datetime | None = None) -> int:
    """Relatorio vencido e descartado. Alerta vencido NAO e descartado aqui: depende da revalidacao."""
    agora_dt = agora_dt or dt.datetime.now()
    cur = con.execute(
        "UPDATE outbox SET desfecho='expirado_ttl' WHERE enviado_em IS NULL AND desfecho IS NULL AND tipo='relatorio' AND expira_em < ?",
        (_fmt(agora_dt),),
    )
    # tentativas esgotadas
    cur2 = con.execute(
        "UPDATE outbox SET desfecho='tentativas_esgotadas' WHERE enviado_em IS NULL AND desfecho IS NULL AND tentativas >= ?",
        (MAX_TENTATIVAS,),
    )
    con.commit()
    return cur.rowcount + cur2.rowcount


def pendentes(con: sqlite3.Connection, limite: int = 3, tipo: str | None = None, agora_dt: dt.datetime | None = None) -> list[sqlite3.Row]:
    encerrar_vencidas(con, agora_dt)
    sql = "SELECT * FROM outbox WHERE enviado_em IS NULL AND desfecho IS NULL"
    params: list[Any] = []
    if tipo:
        sql += " AND tipo = ?"
        params.append(tipo)
    sql += " ORDER BY id LIMIT ?"
    params.append(limite)
    return con.execute(sql, params).fetchall()


def descartar_alertas(con: sqlite3.Connection, motivo: str = "alertas desligados") -> int:
    """Descarta (com desfecho registrado) os ALERTAS ainda na fila. Relatorios nao sao tocados. Usado quando os alertas estao desligados
    ou sao desligados: alerta que esperava envio nao pode sair depois do kill switch."""
    cur = con.execute("UPDATE outbox SET desfecho='descartado_alertas_desligados', ultimo_erro=? WHERE tipo='alerta' AND enviado_em IS NULL AND desfecho IS NULL",
                      (motivo[:300],))
    con.commit()
    return cur.rowcount


def contar_pendentes(con: sqlite3.Connection) -> int:
    return len(pendentes(con, limite=1000))


def drenar(
    con: sqlite3.Connection,
    enviar_fn: Callable[[str], tuple[bool, str]],
    limite: int = 3,
    *,
    revalidar: Callable[[int], tuple[bool, str]] | None = None,
    agora_dt: dt.datetime | None = None,
) -> list[tuple[int, bool, str]]:
    """Tenta entregar a fila, do mais antigo ao mais novo. `revalidar(oferta_id) -> (ativa, motivo)` e exigido
    para alerta vencido; sem ele (ou com resposta negativa/erro) o alerta vencido e descartado."""
    agora_dt = agora_dt or dt.datetime.now()
    resultados: list[tuple[int, bool, str]] = []
    for row in pendentes(con, limite, agora_dt=agora_dt):
        texto = row["texto"]
        hora = str(row["criado_em"])[11:16]
        if row["tipo"] == "alerta":
            vencido = str(row["expira_em"] or "") < _fmt(agora_dt)
            if vencido:
                if revalidar is None or row["oferta_id"] is None:
                    ativa, motivo = False, "alerta vencido e sem como revalidar"
                else:
                    try:
                        ativa, motivo = revalidar(int(row["oferta_id"]))
                    except Exception as exc:  # noqa: BLE001 - na duvida, nao entrega promocao velha
                        ativa, motivo = False, f"revalidacao falhou: {str(exc)[:80]}"
                if not ativa:
                    con.execute("UPDATE outbox SET desfecho=?, ultimo_erro=? WHERE id=?",
                                ("descartado_revalidacao", motivo[:300], row["id"]))
                    con.commit()
                    resultados.append((int(row["id"]), False, f"descartado: {motivo}"))
                    continue
                texto = (f"🔄 *Alerta atrasado, revalidado na fonte as {agora_dt:%H:%M}* "
                         f"(detectado as {hora}). Confira antes de pagar.\n\n{texto}")
        else:
            texto = f"📬 *Reenvio* (a mensagem das {hora} nao tinha saido na hora)\n\n{texto}"
        _t = time.perf_counter()
        ok, info = enviar_fn(texto)
        try:  # medir nunca derruba a entrega
            from . import latencia
            na_fila = (dt.datetime.now() - dt.datetime.strptime(str(row["criado_em"])[:19], "%Y-%m-%d %H:%M:%S")).total_seconds()
            latencia.registrar("envio_fila", outbox_id=int(row["id"]), tipo=row["tipo"], ok=bool(ok), duracao_s=round(time.perf_counter() - _t, 2),
                               na_fila_s=round(na_fila, 1) if 0 <= na_fila < 7 * 86400 else None)
        except Exception:  # noqa: BLE001
            pass
        if ok:
            con.execute("UPDATE outbox SET enviado_em = ?, ultimo_erro = NULL, desfecho='enviado' WHERE id = ?", (agora(), row["id"]))
        else:
            con.execute("UPDATE outbox SET tentativas = tentativas + 1, ultimo_erro = ? WHERE id = ?", (info[:300], row["id"]))
        con.commit()
        resultados.append((int(row["id"]), ok, info))
        if not ok:
            break  # canal instavel: nao insiste com as demais agora
    return resultados
