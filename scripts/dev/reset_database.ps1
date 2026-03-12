$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = (Resolve-Path (Join-Path $ScriptDir "../..")).Path
Set-Location $RootDir

. (Join-Path $ScriptDir "source.ps1")

Write-Host "Resetting PGN simulator database and wiping generated output"
New-Item -ItemType Directory -Force -Path (Join-Path $RootDir "pgn_output") | Out-Null
Get-ChildItem -Force (Join-Path $RootDir "pgn_output") | Remove-Item -Recurse -Force

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
