"""Executor de jobs definidos em config/radar_jobs.yaml.

Cada job: trava de execucao unica, um subprocesso por passo com timeout,
log UTF-8 com rotacao e registro da execucao no banco (ultima execucao,
status, falhas consecutivas). Falha de um passo nao derruba os demais
quando o job declara `continuar_apos_falha`.
"""

from __future__ import annotations

import datetime as dt
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import yaml

from . import caminhos, db, maquina, outbox, trava

ARQ_JOBS = caminhos.CONFIG_DIR / "radar_jobs.yaml"
LOG_DIAS = 14
LOG_MAX_BYTES = 5 * 1024 * 1024


def carregar_config(caminho: Path | None = None) -> dict[str, Any]:
    cfg = yaml.safe_load((caminho or ARQ_JOBS).read_text(encoding="utf-8")) or {}
    cfg.setdefault("jobs", {})
    cfg.setdefault("agendamentos", [])
    return cfg


def _expandir(comando: list[str]) -> list[str]:
    return [sys.executable if c == "{python}" else c for c in comando]


def _rotacionar_logs() -> None:
    corte = time.time() - LOG_DIAS * 86400
    for f in caminhos.logs_dir().glob("*.log"):
        try:
            if f.stat().st_mtime < corte:
                f.unlink()
        except OSError:
            pass


def _log_do_dia(job: str) -> Path:
    base = caminhos.logs_dir() / f"{job}-{dt.datetime.now():%Y%m%d}.log"
    try:
        if base.exists() and base.stat().st_size > LOG_MAX_BYTES:
            base.replace(base.with_suffix(f".{dt.datetime.now():%H%M%S}.log"))
    except OSError:
        pass
    return base


def _matar_arvore(pid: int) -> None:
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, check=False)
    else:
        try:
            os.kill(pid, 9)
        except OSError:
            pass


def _rodar_passo(comando: list[str], timeout_s: int, log: Path) -> tuple[str, int | None]:
    """Roda um passo gravando a saida no log. Retorna (status, codigo)."""
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    with log.open("a", encoding="utf-8", errors="replace") as f:
        proc = subprocess.Popen(
            comando, cwd=str(caminhos.RAIZ), env=env, stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL
        )
        try:
            codigo = proc.wait(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            _matar_arvore(proc.pid)
            proc.wait(timeout=30)
            f.write(f"\n[radar] TIMEOUT apos {timeout_s}s; processo encerrado\n")
            return "timeout", None
    return ("ok" if codigo == 0 else "falha"), codigo


def _registrar_inicio(con, job: str, passo: str | None) -> int:
    cur = con.execute(
        "INSERT INTO execucoes (job, passo, inicio, status) VALUES (?,?,?,'rodando')", (job, passo, db.agora())
    )
    con.commit()
    return int(cur.lastrowid)


def _registrar_fim(con, exec_id: int, status: str, codigo: int | None, resumo: str = "") -> None:
    con.execute(
        "UPDATE execucoes SET fim=?, status=?, codigo=?, resumo=? WHERE id=?",
        (db.agora(), status, codigo, resumo[:400], exec_id),
    )
    con.commit()


def _atualizar_estado_job(con, job: str, sucesso: bool) -> int:
    row = con.execute("SELECT falhas_consecutivas FROM jobs_estado WHERE job=?", (job,)).fetchone()
    falhas = 0 if sucesso else (int(row["falhas_consecutivas"]) + 1 if row else 1)
    agora = db.agora()
    con.execute(
        "INSERT INTO jobs_estado (job, ultima_execucao, ultimo_status, ultimo_sucesso, falhas_consecutivas) "
        "VALUES (?,?,?,?,?) ON CONFLICT(job) DO UPDATE SET ultima_execucao=excluded.ultima_execucao, "
        "ultimo_status=excluded.ultimo_status, falhas_consecutivas=excluded.falhas_consecutivas, "
        "ultimo_sucesso=COALESCE(excluded.ultimo_sucesso, jobs_estado.ultimo_sucesso)",
        (job, agora, "ok" if sucesso else "falha", agora if sucesso else None, falhas),
    )
    con.commit()
    return falhas


def executar_job(job_id: str, *, config: dict[str, Any] | None = None, pasta_trava: Path | None = None) -> int:
    cfg = config or carregar_config()
    job = (cfg.get("jobs") or {}).get(job_id)
    if not job:
        print(f"[radar] job desconhecido: {job_id}", file=sys.stderr)
        return 2

    if job.get("respeita_maquina_oficial", True) and config is None:  # `config` injetado = teste/uso programatico
        pode, motivo = maquina.pode_rodar()
        if not pode:
            print(f"[radar] job {job_id} ignorado: {motivo}")
            return 0
    _rotacionar_logs()
    log = _log_do_dia(job_id)
    con = db.abrir()
    try:
        try:
            with trava.trava(job.get("trava") or job_id, pasta=pasta_trava):
                return _executar_passos(con, job_id, job, log)
        except trava.TravaOcupada as exc:
            exec_id = _registrar_inicio(con, job_id, None)
            _registrar_fim(con, exec_id, "ignorada", None, str(exc))
            with log.open("a", encoding="utf-8") as f:
                f.write(f"[radar {db.agora()}] {exc}; execucao ignorada\n")
            print(f"[radar] {exc}; execucao ignorada")
            return 0
    finally:
        con.close()


def _executar_passos(con, job_id: str, job: dict[str, Any], log: Path) -> int:
    seguir = bool(job.get("continuar_apos_falha"))
    resultados: list[tuple[str, str, int | None]] = []
    # Com a trava em maos nenhuma outra instancia roda: qualquer 'rodando' deste job e resto de uma execucao morta
    # (reinicio do Windows, kill, queda de energia). Fecha o registro em vez de deixa-lo mentindo.
    orfas = con.execute(
        "UPDATE execucoes SET status='interrompida', fim=?, resumo='processo anterior morreu antes de terminar' "
        "WHERE job=? AND status='rodando'", (db.agora(), job_id)).rowcount
    con.commit()
    if orfas:
        print(f"[radar] {orfas} execucao(oes) anterior(es) de {job_id} estavam 'rodando' e foram marcadas como interrompidas")
    with log.open("a", encoding="utf-8") as f:
        f.write(f"\n=== [{db.agora()}] job {job_id} inicio ===\n")
    for passo in job.get("passos") or []:
        pid_ = str(passo.get("id"))
        exec_id = _registrar_inicio(con, job_id, pid_)
        with log.open("a", encoding="utf-8") as f:
            f.write(f"--- passo {pid_} ---\n")
        status, codigo = _rodar_passo(_expandir(passo["comando"]), int(float(passo.get("timeout_min", 10)) * 60), log)
        _registrar_fim(con, exec_id, status, codigo)
        resultados.append((pid_, status, codigo))
        if status != "ok" and not seguir:
            break
    sucesso = all(s == "ok" for _, s, _ in resultados) and bool(resultados)
    falhas = _atualizar_estado_job(con, job_id, sucesso)
    resumo = " ".join(f"{p}={s}" for p, s, _ in resultados)
    with log.open("a", encoding="utf-8") as f:
        f.write(f"=== [{db.agora()}] job {job_id} fim ({resumo}) ===\n")
    print(f"[radar] job {job_id}: {resumo}")
    if falhas in (2, 6, 12):
        try:
            outbox.enfileirar(
                con,
                f"⚠️ *Radar de compras:* o job *{job_id}* falhou {falhas} vezes seguidas ({resumo}). "
                f"Log: {log.name}",
                "radar-saude",
                "alerta de saude do proprio radar",
                ttl_min=120,  # aviso de saude velho (rede ja voltou) e ruido: vence em 2 h
            )
        except Exception:  # noqa: BLE001
            pass
    return 0 if sucesso else 1


def proxima_execucao(ag: dict[str, Any], agora: dt.datetime | None = None) -> dt.datetime | None:
    """Proximo disparo previsto de um agendamento (horarios fixos ou intervalo)."""
    agora = agora or dt.datetime.now()
    if ag.get("horarios"):
        candidatos = []
        for h in ag["horarios"]:
            hh, mm = (int(x) for x in str(h).split(":"))
            t = agora.replace(hour=hh, minute=mm, second=0, microsecond=0)
            candidatos.append(t if t > agora else t + dt.timedelta(days=1))
        return min(candidatos)
    if ag.get("a_cada_min"):
        passo = int(ag["a_cada_min"])
        minutos = (agora.hour * 60 + agora.minute) // passo * passo + passo
        return agora.replace(hour=0, minute=0, second=0, microsecond=0) + dt.timedelta(minutes=minutos)
    return None
