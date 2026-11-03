param([string]$Flutter = 'flutter', [switch]$SkipWebBuild)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
Push-Location $projectRoot
try {
    if (-not $SkipWebBuild) {
        & $Flutter build web --release --no-web-resources-cdn
        if ($LASTEXITCODE -ne 0) { throw 'No se pudo compilar Flutter' }
    }
    if (-not (Test-Path build/web/index.html)) { throw 'Falta build/web/index.html' }
    & $pythonPath -m PyInstaller --noconfirm --name MotorDesk --onedir --console --paths backend --distpath dist --workpath build/portable --specpath build --collect-submodules app --collect-all pwdlib --collect-all argon2 --collect-all pgvector --collect-data email_validator --hidden-import uvicorn.logging --hidden-import uvicorn.loops.auto --hidden-import uvicorn.protocols.http.auto --hidden-import uvicorn.protocols.websockets.auto --hidden-import uvicorn.lifespan.on --add-data "${projectRoot}/backend/app/resources:app/resources" --add-data "${projectRoot}/build/web:web" --exclude-module pytest --exclude-module onnxruntime --exclude-module tokenizers backend/local_entry.py
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo empaquetar MotorDesk' }
    Copy-Item -LiteralPath docs/instalacion_local.md -Destination dist/MotorDesk/LEEME.md
    Copy-Item -LiteralPath docs/portabilidad_resultados.md -Destination dist/MotorDesk/portabilidad_resultados.md
    Copy-Item -LiteralPath integrations.example.json -Destination dist/MotorDesk/integrations.example.json
    @('@echo off', '"%~dp0MotorDesk.exe" backup', 'pause') | Set-Content -Encoding ascii dist/MotorDesk/Respaldar.cmd
    @('@echo off', 'echo Se restaurara en una carpeta NUEVA para no sobrescribir datos.', 'set /p "target=Carpeta nueva para los datos: "', '"%~dp0MotorDesk.exe" restore --data-dir "%target%"', 'pause') | Set-Content -Encoding ascii dist/MotorDesk/Restaurar.cmd
    & $pythonPath scripts/package_licenses.py
    if ($LASTEXITCODE -ne 0) { throw 'No se pudieron recopilar las licencias' }
    & $pythonPath scripts/package_source.py
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo empaquetar el código fuente' }
    & $pythonPath scripts/package_windows_zip.py
    if ($LASTEXITCODE -ne 0) { throw "No se pudo crear el ZIP Windows" }
} finally { Pop-Location }
