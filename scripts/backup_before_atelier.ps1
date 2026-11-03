$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$destination = Join-Path $root "backups/pre-atelier-$stamp"
New-Item -ItemType Directory -Path $destination -Force | Out-Null
$remote = "/tmp/motordesk-pre-atelier-$stamp.dump"
docker compose exec -T db pg_dump -U workshop -d workshop -Fc -f $remote
if ($LASTEXITCODE -ne 0) { throw 'No se pudo respaldar PostgreSQL. No aplicar migraciones.' }
docker compose cp "db:$remote" (Join-Path $destination 'workshop.dump')
if ($LASTEXITCODE -ne 0) { throw 'No se pudo copiar el respaldo.' }
docker compose exec -T db pg_restore --list $remote | Out-File (Join-Path $destination 'contents.txt') -Encoding utf8
if ($LASTEXITCODE -ne 0) { throw 'El respaldo no es legible.' }
Get-FileHash (Join-Path $destination 'workshop.dump') -Algorithm SHA256 | Format-List
Write-Output "Respaldo privado: $destination"
