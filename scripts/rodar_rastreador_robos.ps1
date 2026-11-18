$ErrorActionPreference = "Stop"
$privadoDir = Join-Path $env:USERPROFILE ".central-compras\dados-privados\rastreador-robos"
New-Item -ItemType Directory -Force $privadoDir | Out-Null
$logPath = Join-Path $privadoDir "execucao.log"

$stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content -Path $logPath -Value "=== Inicio $stamp ===" -Encoding UTF8

Set-Location "C:\projetos\central-compras"
& python "C:\projetos\central-compras\scripts\rastrear_robos_bf.py" --enviar-zap *>> $logPath
$code = $LASTEXITCODE

$stampFim = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content -Path $logPath -Value "=== Fim $stampFim (exit=$code) ===" -Encoding UTF8
exit $code
