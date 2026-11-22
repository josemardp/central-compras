# Atalho de compatibilidade. A logica dos relatorios (robos, ares, chuveiro) agora e do radar:
#   python -m radar executar relatorios
# Definicao dos passos, horarios e limites: config/radar_jobs.yaml
# O radar cuida de trava (sem execucao dupla), timeout por passo, log UTF-8 e fila de reenvio.
# Este arquivo existe so para quem ainda disparar o caminho antigo (tarefa de outra maquina, atalho manual).

$ErrorActionPreference = "Continue"
$raiz = Split-Path -Parent $PSScriptRoot
Set-Location $raiz
$env:PYTHONUTF8 = "1"
& python -m radar executar relatorios
exit $LASTEXITCODE
