$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSCommandPath
$py = Join-Path $root '.venv\Scripts\python.exe'
$logDir = Join-Path $root 'logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$outLog = Join-Path $logDir 'backend_bg.log'
$errLog = Join-Path $logDir 'backend_bg.err.log'

function Get-ListeningPid($port) {
  $line = netstat -ano | Select-String ":$port" | Select-String 'LISTENING' | Select-Object -First 1
  if (-not $line) { return $null }
  $parts = ($line -split '\s+')
  return [int]$parts[-1]
}

$listenPid = Get-ListeningPid 8000
if ($listenPid) {
  try { Stop-Process -Id $listenPid -Force } catch {}
  Start-Sleep -Milliseconds 300
}

Start-Process -WindowStyle Hidden -WorkingDirectory $root -FilePath $py -ArgumentList @(
  '-m','uvicorn','app.main:app',
  '--host','127.0.0.1',
  '--port','8000',
  '--proxy-headers',
  '--forwarded-allow-ips','127.0.0.1,::1'
) -RedirectStandardOutput $outLog -RedirectStandardError $errLog

Start-Sleep -Seconds 1
$newPid = Get-ListeningPid 8000
if (-not $newPid) {
  throw "Backend failed to start. Check $errLog"
}

Write-Output "Backend running on 127.0.0.1:8000 (pid $newPid)"