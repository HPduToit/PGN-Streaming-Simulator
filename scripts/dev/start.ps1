$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = (Resolve-Path (Join-Path $ScriptDir "../..")).Path
Set-Location $RootDir

. (Join-Path $ScriptDir "source.ps1")
poetry run pgn-tournament create --config dirk.config.yaml --start
