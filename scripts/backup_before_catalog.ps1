$ErrorActionPreference = 'Stop'
# Respaldo verificado antes de recrear `db` con pgvector y aplicar 0004.
# A diferencia de backup_before_atelier.ps1, éste comprueba que el dump es
# realmente restaurable ANTES de permitir cualquier migracion.
$root = Split-Path $PSScriptRoot -Parent
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$destination = Join-Path $root "backups/pre-pgvector-$stamp"
New-Item -ItemType Directory -Path $destination -Force | Out-Null

$remote = "/tmp/motordesk-$stamp.dump"
docker compose exec -T db pg_dump -U workshop -d workshop -Fc -f $remote
if ($LASTEXITCODE -ne 0) { throw 'pg_dump fallo. No continuar.' }
docker compose cp "db:$remote" (Join-Path $destination 'workshop.dump')
if ($LASTEXITCODE -ne 0) { throw 'No se pudo copiar el respaldo.' }

# pg_restore --list lee la cabecera del archivo: si pasa, el dump es coherente.
docker compose exec -T db pg_restore --list $remote | Out-File (Join-Path $destination 'contents.txt') -Encoding utf8
if ($LASTEXITCODE -ne 0) { throw 'El respaldo no es legible. No continuar.' }

$tables = (Select-String -Path (Join-Path $destination 'contents.txt') -Pattern 'TABLE DATA').Count
$schema = docker compose exec -T db psql -U workshop -d workshop -t -c "select version_num from alembic_version"
if ($tables -lt 20) { throw "El respaldo solo contiene $tables tablas; se esperaban 25. No continuar." }
if ($schema.Trim() -ne '0003') { throw "La base esta en $schema, no en 0003. Revisar antes de continuar." }

$hash = (Get-FileHash (Join-Path $destination 'workshop.dump') -Algorithm SHA256).Hash
Set-Content (Join-Path $destination 'SHA256SUMS.txt') "$hash  workshop.dump" -Encoding ascii

Write-Output "Respaldo verificado: $destination"
Write-Output "  tablas en el dump : $tables"
Write-Output "  alembic_version   : $($schema.Trim())"
Write-Output "  sha256            : $hash"