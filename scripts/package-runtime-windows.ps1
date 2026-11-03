param([string]$OutputDirectory = 'dist/MotorDesk-Runtime')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
Push-Location $projectRoot
try {
    $basePath = & $pythonPath -c 'import sys; print(sys.base_prefix)'
    $signature = Get-AuthenticodeSignature (Join-Path $basePath 'python.exe')
    if ($signature.Status -ne 'Valid') { throw 'El intérprete base no tiene una firma válida. No se genera la distribución.' }
    & $pythonPath scripts/package_signed_runtime.py --output $OutputDirectory
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo empaquetar el runtime' }
    $copiedSignature = Get-AuthenticodeSignature (Join-Path $OutputDirectory 'runtime/python.exe')
    if ($copiedSignature.Status -ne 'Valid') { throw 'La firma del intérprete copiado no es válida' }
    Write-Output 'Firma del intérprete copiado: válida. Falta ejecutar las pruebas del paquete.'
} finally { Pop-Location }
