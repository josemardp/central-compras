"""Auto-recuperacao de relatorios perdidos (notebook suspenso, desligado ou sem rede no horario).

Motivo (21/11/2026): o notebook dormiu de 02:26 a 09:37 e o Windows nao recuperou o slot das 08:00 apesar de
StartWhenAvailable. A varredura roda a cada 10 min assim que o notebook acorda; ela chama `recuperar`, que
confere se o ultimo horario previsto de cada agendamento teve alguma execucao e, se nao teve e ainda esta dentro
da tolerancia, dispara a PROPRIA tarefa do Windows (mesmos limites, trava e log).
"""

from __future__ import annotations

import datetime as dt
import subprocess
from typing import Any, Callable

from . import db

FOLGA_ANTECIPADA_MIN = 2  # execucao que comecou um pouco antes do horario ainda conta


def ultimo_slot(horarios: list[str], agora: dt.datetime) -> dt.datetime | None:
    """Ultimo horario previsto que ja passou (hoje; se nenhum, o ultimo de ontem)."""
    if not horarios:
        return None
    hoje = []
    for h in horarios:
        hh, mm = (int(x) for x in str(h).split(":"))
        hoje.append(agora.replace(hour=hh, minute=mm, second=0, microsecond=0))
    passados = [t for t in hoje if t <= agora]
    if passados:
        return max(passados)
    return max(hoje) - dt.timedelta(days=1)


def atrasados(cfg: dict[str, Any], con, agora: dt.datetime | None = None) -> list[dict[str, Any]]:
    """Agendamentos por horario cujo ultimo slot ficou sem execucao e esta dentro de `recuperar_ate_horas`."""
    agora = agora or dt.datetime.now()
    saida: list[dict[str, Any]] = []
    for ag in cfg.get("agendamentos", []):
        tolerancia = float(ag.get("recuperar_ate_horas", 0) or 0)
        if not ag.get("horarios") or not ag.get("habilitada", True) or tolerancia <= 0:
            continue
        slot = ultimo_slot(ag["horarios"], agora)
        if slot is None or agora - slot > dt.timedelta(hours=tolerancia):
            continue
        desde = (slot - dt.timedelta(minutes=FOLGA_ANTECIPADA_MIN)).strftime("%Y-%m-%d %H:%M:%S")
        ja = con.execute("SELECT COUNT(*) FROM execucoes WHERE job = ? AND inicio >= ?", (ag["job"], desde)).fetchone()[0]
        if not ja:
            saida.append({"job": ag["job"], "tarefa": ag["tarefa"], "slot": slot, "atraso_min": int((agora - slot).total_seconds() // 60)})
    return saida


def _disparar_tarefa_windows(tarefa: str) -> tuple[bool, str]:
    p = subprocess.run(["schtasks", "/Run", "/TN", tarefa], capture_output=True, text=True, errors="replace", timeout=30)
    return p.returncode == 0, (p.stdout or p.stderr).strip()[:160]


def recuperar(
    cfg: dict[str, Any],
    agora: dt.datetime | None = None,
    disparar: Callable[[str], tuple[bool, str]] = _disparar_tarefa_windows,
) -> list[dict[str, Any]]:
    agora = agora or dt.datetime.now()
    con = db.abrir()
    try:
        feitos = []
        for a in atrasados(cfg, con, agora):
            ok, info = disparar(a["tarefa"])
            # Registra a tentativa para nao disparar de novo a cada 10 min enquanto a tarefa nao grava a execucao dela.
            con.execute(
                "INSERT INTO execucoes (job, passo, inicio, fim, status, codigo, resumo) VALUES (?,?,?,?,?,?,?)",
                (a["job"], "recuperacao", db.agora(), db.agora(), "recuperacao_ok" if ok else "recuperacao_falha", 0 if ok else 1,
                 f"slot {a['slot']:%d/%m %H:%M} atrasado {a['atraso_min']} min: {info}"),
            )
            con.commit()
            feitos.append({**a, "disparado": ok, "info": info})
        return feitos
    finally:
        con.close()
