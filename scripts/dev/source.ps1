$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = (Resolve-Path (Join-Path $ScriptDir "../..")).Path
$EnvFile = Join-Path $RootDir ".env"
if (Test-Path $EnvFile) {
    Get-Content $EnvFile | ForEach-Object {
        if ($_ -match '^\s*#' -or $_ -match '^\s*$') {
            return
        }
        $parts = $_ -split '=', 2
        if ($parts.Count -eq 2) {
            [System.Environment]::SetEnvironmentVariable($parts[0], $parts[1])
        }
    }
}

$env:PGN_POSTGRES_DB = if ($env:PGN_POSTGRES_DB) { $env:PGN_POSTGRES_DB } elseif ($env:PGNSS_POSTGRES_DB) { $env:PGNSS_POSTGRES_DB } else { "pgn_simulator" }
$env:PGN_POSTGRES_USER = if ($env:PGN_POSTGRES_USER) { $env:PGN_POSTGRES_USER } elseif ($env:PGNSS_POSTGRES_USER) { $env:PGNSS_POSTGRES_USER } else { "postgres" }
$env:PGN_POSTGRES_PASSWORD = if ($env:PGN_POSTGRES_PASSWORD) { $env:PGN_POSTGRES_PASSWORD } elseif ($env:PGNSS_POSTGRES_PASSWORD) { $env:PGNSS_POSTGRES_PASSWORD } else { "postgres" }
$env:PGN_POSTGRES_PORT = if ($env:PGN_POSTGRES_PORT) { $env:PGN_POSTGRES_PORT } elseif ($env:PGNSS_POSTGRES_PORT) { $env:PGNSS_POSTGRES_PORT } else { "5432" }
$env:PGN_SERVER_PORT = if ($env:PGN_SERVER_PORT) { $env:PGN_SERVER_PORT } else { "8006" }
$env:PGN_DATABASE_URL = "postgresql://$($env:PGN_POSTGRES_USER):$($env:PGN_POSTGRES_PASSWORD)@127.0.0.1:$($env:PGN_POSTGRES_PORT)/$($env:PGN_POSTGRES_DB)"
