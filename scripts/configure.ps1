param([switch]$SQLite)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$target = Join-Path $root '.env'
if (Test-Path $target) { throw '.env ya existe. No se reemplazan secretos ni configuración.' }
function New-Secret([int]$length) {
    $bytes = New-Object byte[] $length
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $rng.GetBytes($bytes)
    $rng.Dispose()
    return ([System.BitConverter]::ToString($bytes)).Replace('-', '').ToLower()
}
$secret = New-Secret 32
$password = New-Secret 10
$dbPassword = New-Secret 20
$content = Get-Content (Join-Path $root '.env.example') -Raw -Encoding UTF8
$content = $content.Replace('SECRET_KEY=', "SECRET_KEY=$secret").Replace('ADMIN_PASSWORD=', "ADMIN_PASSWORD=$password").Replace('POSTGRES_PASSWORD=', "POSTGRES_PASSWORD=$dbPassword")
if ($SQLite) {
    $content = $content.Replace('postgresql+psycopg://workshop:workshop@127.0.0.1:5432/workshop', 'sqlite:///./workshop.db')
} else {
    $content = $content.Replace('workshop:workshop@127.0.0.1', "workshop:${dbPassword}@127.0.0.1")
}
[System.IO.File]::WriteAllText($target, $content, (New-Object System.Text.UTF8Encoding $false))
Write-Output 'Configuración creada. Guarde el acceso inicial; debe cambiarse al iniciar sesión.'
Write-Output "Usuario: admin / Contraseña temporal: $password"
