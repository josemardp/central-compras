"""Trava de execucao unica por job (impede o mesmo monitor rodar duas vezes).

Arquivo criado de forma atomica (O_EXCL) com PID e horario. Trava de processo
morto ou mais velha que `validade_s` e considerada orfa e tomada.
"""

from __future__ import annotations

import contextlib
import json
import os
import time
from pathlib import Path

from . import caminhos


class TravaOcupada(RuntimeError):
    pass


def _pid_vivo(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        h = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not h:
            return False
        codigo = ctypes.c_ulong()
        ok = ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(codigo))
        ctypes.windll.kernel32.CloseHandle(h)
        return bool(ok) and codigo.value == 259  # STILL_ACTIVE
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _ler(caminho: Path) -> dict:
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except Exception:
        return {}


@contextlib.contextmanager
def aguardar(nome: str, espera_max_s: float = 300.0, validade_s: int = 900, pasta: Path | None = None):
    """Como `trava`, mas espera ate `espera_max_s` a vez (usado para serializar envios ao WhatsApp)."""
    limite = time.time() + espera_max_s
    while True:
        cm = trava(nome, validade_s=validade_s, pasta=pasta)
        try:
            caminho = cm.__enter__()
            break
        except TravaOcupada:
            if time.time() >= limite:
                raise
            time.sleep(2.0)
    try:
        yield caminho
    finally:
        cm.__exit__(None, None, None)


@contextlib.contextmanager
def trava(nome: str, validade_s: int = 3 * 3600, pasta: Path | None = None):
    """Context manager: levanta TravaOcupada se outro processo vivo ja segura `nome`."""
    caminho = (pasta or caminhos.travas_dir()) / f"{nome}.lock"
    corpo = json.dumps({"pid": os.getpid(), "desde": time.time()})
    for _ in range(2):
        try:
            fd = os.open(str(caminho), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            info = _ler(caminho)
            velho = time.time() - float(info.get("desde") or 0) > validade_s
            if info.get("pid") and _pid_vivo(int(info["pid"])) and not velho:
                raise TravaOcupada(f"{nome} ja esta em execucao (pid {info['pid']})")
            with contextlib.suppress(OSError):
                caminho.unlink()  # orfa: toma
            continue
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(corpo)
        break
    else:
        raise TravaOcupada(f"nao foi possivel obter a trava {nome}")
    try:
        yield caminho
    finally:
        with contextlib.suppress(OSError):
            caminho.unlink()
