$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = (Resolve-Path (Join-Path $ScriptDir "../..")).Path
Set-Location $RootDir

. (Join-Path $ScriptDir "source.ps1")
$configPath = if ($args.Length -ge 2 -and $args[1]) { $args[1] } else { "config.yaml" }
poetry run pgn-tournament update $args[0] --config $configPath
