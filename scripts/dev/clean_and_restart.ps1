$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = (Resolve-Path (Join-Path $ScriptDir "../..")).Path
Set-Location $RootDir

. (Join-Path $ScriptDir "source.ps1")

$confirmation = Read-Host "Are you sure you want to run this script? This will remove Docker volumes for PostgreSQL, wipe generated output, and restart the local PGN server prerequisites. Type 'yes' to continue"
if ($confirmation -ne "yes") {
    Write-Host "Operation cancelled by user."
    exit 1
}

New-Item -ItemType Directory -Force -Path (Join-Path $RootDir "pgn_output") | Out-Null
Get-ChildItem -Force (Join-Path $RootDir "pgn_output") | Remove-Item -Recurse -Force

docker compose down -v --remove-orphans
if ($LASTEXITCODE -ne 0) {
    throw "Failed to stop PostgreSQL container"
}

docker compose up -d pgn_db
if ($LASTEXITCODE -ne 0) {
    throw "Failed to start PostgreSQL container"
}

do {
    Write-Host "Waiting for PostgreSQL to become healthy..."
    Start-Sleep -Seconds 5
    $healthStatus = docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}unknown{{end}}' pgn_db 2>$null
} while ($healthStatus -ne "healthy")

poetry run pgn-tournament reset-db --yes --wipe-output
if ($LASTEXITCODE -ne 0) {
    throw "Failed to reset PGN simulator database"
}

Write-Host "PostgreSQL is ready in container: pgn_db"
Write-Host "Start the local server with:"
Write-Host "  .\scripts\dev\start_server.ps1"
Write-Host "Create/start tournaments locally with:"
Write-Host "  .\scripts\dev\start.ps1"
Write-Host "  .\scripts\dev\start_tournament.ps1 <uuid>"
