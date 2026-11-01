param(
    [Parameter(Mandatory=$true)][string]$Archive,
    [string]$TargetDatabase = "visionguard_restore_drill"
)
$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$archivePath = (Resolve-Path -LiteralPath $Archive).Path
$allowedRoot = [IO.Path]::GetFullPath((Join-Path $root "runtime\backups"))
if (-not $archivePath.StartsWith($allowedRoot, [StringComparison]::OrdinalIgnoreCase)) { throw "restore archive must be under runtime/backups" }
if ($TargetDatabase -notmatch '^[a-z][a-z0-9_]{0,62}$') { throw "invalid target database name" }
$envFile = Join-Path $root ".env.postgres"
$cfg = ConvertFrom-StringData (Get-Content -Raw -LiteralPath $envFile)
$container = docker compose --env-file $envFile -f (Join-Path $root "compose.postgres.yml") ps -q postgres
if (-not $container) { throw "PostgreSQL container is not running" }
$exists = docker exec $container psql -U $cfg.POSTGRES_USER -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$TargetDatabase'"
if ($exists -eq "1") { throw "target database already exists; choose a new isolated name" }
$tempName = "/tmp/$([IO.Path]::GetFileName($archivePath))"
$started = Get-Date
docker cp $archivePath "${container}:$tempName" | Out-Null
docker exec $container pg_restore -l $tempName | Out-Null
if ($LASTEXITCODE -ne 0) { throw "archive integrity listing failed" }
docker exec $container createdb -U $cfg.POSTGRES_USER $TargetDatabase
docker exec $container pg_restore -U $cfg.POSTGRES_USER -d $TargetDatabase --no-owner $tempName
if ($LASTEXITCODE -ne 0) { throw "pg_restore failed" }
docker exec $container psql -U $cfg.POSTGRES_USER -d $TargetDatabase -v ON_ERROR_STOP=1 -c "GRANT USAGE ON SCHEMA public, visionguard_context TO visionguard_app" -c "GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public TO visionguard_app"
docker exec $container rm -f $tempName
$result = [ordered]@{
    archive = $archivePath
    target_database = $TargetDatabase
    restored_at = (Get-Date).ToUniversalTime().ToString("o")
    elapsed_seconds = ((Get-Date) - $started).TotalSeconds
    status = "restored"
}
$result | ConvertTo-Json
