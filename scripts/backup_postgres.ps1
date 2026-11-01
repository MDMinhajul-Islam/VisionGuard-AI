param(
    [string]$OutputDirectory = "runtime/backups",
    [string]$Database = ""
)
$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$envFile = Join-Path $root ".env.postgres"
if (-not (Test-Path -LiteralPath $envFile)) { throw ".env.postgres is required" }
$cfg = ConvertFrom-StringData (Get-Content -Raw -LiteralPath $envFile)
$databaseName = if ($Database) { $Database } else { $cfg.POSTGRES_DB }
$outputRoot = [IO.Path]::GetFullPath((Join-Path $root $OutputDirectory))
$allowedRoot = [IO.Path]::GetFullPath((Join-Path $root "runtime\backups"))
if (-not $outputRoot.StartsWith($allowedRoot, [StringComparison]::OrdinalIgnoreCase)) { throw "backup output must remain under runtime/backups" }
New-Item -ItemType Directory -Force -Path $outputRoot | Out-Null
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$name = "visionguard-$databaseName-$stamp.dump"
$container = docker compose --env-file $envFile -f (Join-Path $root "compose.postgres.yml") ps -q postgres
if (-not $container) { throw "PostgreSQL container is not running" }
$started = Get-Date
docker exec $container pg_dump -U $cfg.POSTGRES_USER -d $databaseName -Fc --no-password -f "/tmp/$name"
if ($LASTEXITCODE -ne 0) { throw "pg_dump failed" }
$destination = Join-Path $outputRoot $name
docker cp "${container}:/tmp/$name" $destination | Out-Null
docker exec $container pg_restore -l "/tmp/$name" | Out-Null
if ($LASTEXITCODE -ne 0) { throw "pg_restore archive listing failed" }
docker exec $container rm -f "/tmp/$name"
$manifest = [ordered]@{
    format = "PostgreSQL custom archive"
    database = $databaseName
    created_at = (Get-Date).ToUniversalTime().ToString("o")
    elapsed_seconds = ((Get-Date) - $started).TotalSeconds
    path = $destination
    size_bytes = (Get-Item -LiteralPath $destination).Length
    sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $destination).Hash.ToLowerInvariant()
    media_included = $false
}
$manifestPath = "$destination.manifest.json"
$manifest | ConvertTo-Json | Set-Content -Encoding utf8NoBOM -LiteralPath $manifestPath
$manifest | ConvertTo-Json
