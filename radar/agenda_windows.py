"""Ponte entre config/radar_jobs.yaml e o Agendador de Tarefas do Windows.

O YAML manda; o Windows so dispara. `status` compara o desejado com o real,
`aplicar` cria/atualiza as tarefas (com backup do XML anterior) e `remover`
desfaz. Nada aqui altera tarefas de outros projetos.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from . import caminhos


def _ps(script: str, timeout: int = 90) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
    )


def _q(texto: str) -> str:
    return "'" + str(texto).replace("'", "''") + "'"


def raiz_estavel() -> str:
    """Caminho do repositorio usado nas tarefas (junction C:\\projetos preferido: e o padrao das maquinas)."""
    c = Path(r"C:\projetos\central-compras")
    return str(c if c.exists() else caminhos.RAIZ)


def estado_tarefas(nomes: list[str]) -> dict[str, dict[str, Any]]:
    lista = ",".join(_q(n) for n in nomes)
    script = f"""
$r = @()
foreach ($n in @({lista})) {{
  $t = Get-ScheduledTask -TaskName $n -ErrorAction SilentlyContinue
  if (-not $t) {{ $r += [pscustomobject]@{{nome=$n; existe=$false}}; continue }}
  $i = Get-ScheduledTaskInfo -TaskName $n
  $a = ($t.Actions | ForEach-Object {{ ($_.Execute + ' ' + $_.Arguments).Trim() }}) -join ' | '
  $r += [pscustomobject]@{{
    nome=$n; existe=$true; estado=[string]$t.State; limite=[string]$t.Settings.ExecutionTimeLimit;
    ultima=[string]$i.LastRunTime; resultado=$i.LastTaskResult; proxima=[string]$i.NextRunTime;
    perdida_inicia=[bool]$t.Settings.StartWhenAvailable; acao=$a; gatilhos=@($t.Triggers).Count }}
}}
$r | ConvertTo-Json -Compress -Depth 4
"""
    p = _ps(script)
    if p.returncode != 0 or not p.stdout.strip():
        return {n: {"existe": None, "erro": (p.stderr or "sem saida")[:200]} for n in nomes}
    dados = json.loads(p.stdout)
    if isinstance(dados, dict):
        dados = [dados]
    return {d["nome"]: d for d in dados}


def _script_aplicar(ag: dict[str, Any], python: str, raiz: str, backup_xml: Path) -> str:
    nome = ag["tarefa"]
    job = ag["job"]
    limite = int(ag.get("limite_execucao_min", 30))
    habilitada = bool(ag.get("habilitada", True))
    if ag.get("horarios"):
        gatilhos = "\n".join(f"$gat += New-ScheduledTaskTrigger -Daily -At {_q(h)}" for h in ag["horarios"])
    else:
        passo = int(ag["a_cada_min"])
        desloc = int(ag.get("deslocamento_min", 0))
        inicio, fim = ag.get("inicio"), ag.get("fim")
        if inicio and fim:  # janela com data: dispara so dentro dela; EndBoundary + DeleteExpiredTaskAfter = a tarefa expira e some sozinha
            import datetime as _dt
            d_ini, d_fim = _dt.datetime.strptime(str(inicio), "%Y-%m-%d %H:%M"), _dt.datetime.strptime(str(fim), "%Y-%m-%d %H:%M")
            minutos = max(int((d_fim - d_ini).total_seconds() // 60), 1)   # em MINUTOS: o ultimo disparo cai na grade (30/11 23:55), nao na hora cheia
            gatilhos = (
                f"$gat += New-ScheduledTaskTrigger -Once -At {_q(str(inicio))} "
                f"-RepetitionInterval (New-TimeSpan -Minutes {passo}) -RepetitionDuration (New-TimeSpan -Minutes {minutos})\n"
                f"$gat[0].EndBoundary = {_q(d_fim.strftime('%Y-%m-%dT%H:%M:%S'))}"
            )
        else:
            gatilhos = (
                f"$gat += New-ScheduledTaskTrigger -Once -At {_q(f'00:{desloc:02d}')} "
                f"-RepetitionInterval (New-TimeSpan -Minutes {passo}) -RepetitionDuration (New-TimeSpan -Days 3650)"
            )
    argumentos = f'--headless "{python}" -m radar executar {job}'
    return f"""
$ErrorActionPreference = 'Stop'
$nome = {_q(nome)}
$existente = Get-ScheduledTask -TaskName $nome -ErrorAction SilentlyContinue
if ($existente) {{ Export-ScheduledTask -TaskName $nome | Out-File -FilePath {_q(str(backup_xml))} -Encoding utf8 }}
$gat = @()
{gatilhos}
$acao = New-ScheduledTaskAction -Execute 'conhost.exe' -Argument {_q(argumentos)} -WorkingDirectory {_q(raiz)}
$cfg = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes {limite}) -MultipleInstances IgnoreNew `
  -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries {"-StartWhenAvailable" if ag.get("iniciar_se_perdida", True) else ""} {"-DeleteExpiredTaskAfter (New-TimeSpan -Hours 24)" if ag.get("fim") else ""}
$cfg.Enabled = {"$true" if habilitada else "$false"}
$prin = New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $nome -Action $acao -Trigger $gat -Settings $cfg -Principal $prin -Force | Out-Null
(Get-ScheduledTask -TaskName $nome).State
"""


def aplicar(cfg: dict[str, Any], *, so_mostrar: bool = False) -> list[dict[str, Any]]:
    resultados: list[dict[str, Any]] = []
    for ag in cfg.get("agendamentos", []):
        base = f"tarefa-{ag['tarefa'].replace(' ', '_')}"
        original = caminhos.backups_dir() / f"{base}.original.xml"
        # O primeiro backup (estado antes do cutover) nunca e sobrescrito.
        backup_xml = original if not original.exists() else caminhos.backups_dir() / f"{base}-{__import__('time').strftime('%Y%m%d-%H%M%S')}.xml"
        script = _script_aplicar(ag, sys.executable, raiz_estavel(), backup_xml)
        if so_mostrar:
            resultados.append({"tarefa": ag["tarefa"], "script": script})
            continue
        p = _ps(script)
        resultados.append(
            {"tarefa": ag["tarefa"], "ok": p.returncode == 0, "saida": (p.stdout or "").strip()[:200],
             "erro": (p.stderr or "").strip()[:300], "backup": str(backup_xml) if backup_xml.exists() else None}
        )
    return resultados


def restaurar_backup(nome_tarefa: str) -> dict[str, Any]:
    """Reimporta o XML salvo antes da ultima aplicacao (reversao do cutover)."""
    xml = caminhos.backups_dir() / f"tarefa-{nome_tarefa.replace(' ', '_')}.original.xml"
    if not xml.exists():
        return {"ok": False, "erro": f"sem backup em {xml}"}
    script = f"Register-ScheduledTask -TaskName {_q(nome_tarefa)} -Xml (Get-Content -Raw -Encoding utf8 {_q(str(xml))}) -Force | Out-Null"
    p = _ps(script)
    return {"ok": p.returncode == 0, "erro": (p.stderr or "").strip()[:300]}


def remover(nome_tarefa: str) -> dict[str, Any]:
    p = _ps(f"Unregister-ScheduledTask -TaskName {_q(nome_tarefa)} -Confirm:$false")
    return {"ok": p.returncode == 0, "erro": (p.stderr or "").strip()[:300]}
