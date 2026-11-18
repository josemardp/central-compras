$ErrorActionPreference = "Continue"
$privadoDir = Join-Path $env:USERPROFILE ".central-compras\dados-privados\rastreador-robos"
New-Item -ItemType Directory -Force $privadoDir | Out-Null
$logPath = Join-Path $privadoDir "execucao.log"

$stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content -Path $logPath -Value "=== Inicio $stamp ===" -Encoding UTF8

Set-Location "C:\projetos\central-compras"
& python "C:\projetos\central-compras\scripts\rastrear_robos_bf.py" --enviar-zap *>> $logPath
$codeRobos = $LASTEXITCODE

& python "C:\projetos\central-compras\scripts\rastrear_ares_bf.py" --enviar-zap *>> $logPath
$codeAres = $LASTEXITCODE

$code = if ($codeRobos -ne 0 -or $codeAres -ne 0) { 1 } else { 0 }
$stampFim = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content -Path $logPath -Value "=== Fim $stampFim (robos=$codeRobos ares=$codeAres exit=$code) ===" -Encoding UTF8
exit $code
