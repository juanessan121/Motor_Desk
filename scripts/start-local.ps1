param([ValidateSet('serve','backup','restore','check')][string]$Command = 'serve', [string]$DataDir = '', [string]$File = '', [int]$Port = 8000)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Falta Python del proyecto. Instale Python 3.14; ejecute python -m venv .venv y .venv\Scripts\python -m pip install -r backend/requirements.lock. Para usuarios finales utilice MotorDesk.exe.'
}
$launchArgs = @('-m', 'app.local', $Command, '--port', $Port)
if ($DataDir) { $launchArgs += @('--data-dir', $DataDir) }
if ($File) { $launchArgs += @('--file', $File) }
Push-Location (Join-Path $projectRoot 'backend')
try { & $pythonPath @launchArgs; if ($LASTEXITCODE -ne 0) { throw "MotorDesk terminó con código $LASTEXITCODE" } }
finally { Pop-Location }
