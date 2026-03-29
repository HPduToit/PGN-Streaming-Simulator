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

$resolvedPgnssDb = if ($env:PGNSS_MYSQL_DATABASE) { $env:PGNSS_MYSQL_DATABASE } elseif ($env:PGNSS_POSTGRES_DB) { $env:PGNSS_POSTGRES_DB } elseif ($env:PGN_POSTGRES_DB) { $env:PGN_POSTGRES_DB } else { "pgnss_db" }
$resolvedPgnssUser = if ($env:INSTALLER_USERID) { $env:INSTALLER_USERID } elseif ($env:PGNSS_MYSQL_USER) { $env:PGNSS_MYSQL_USER } elseif ($env:PGNSS_POSTGRES_USER) { $env:PGNSS_POSTGRES_USER } elseif ($env:PGN_POSTGRES_USER) { $env:PGN_POSTGRES_USER } else { "postgres" }
$resolvedPgnssPassword = if ($env:INSTALLER_PWD) { $env:INSTALLER_PWD } elseif ($env:PGNSS_MYSQL_PASSWORD) { $env:PGNSS_MYSQL_PASSWORD } elseif ($env:PGNSS_POSTGRES_PASSWORD) { $env:PGNSS_POSTGRES_PASSWORD } elseif ($env:PGN_POSTGRES_PASSWORD) { $env:PGN_POSTGRES_PASSWORD } else { "postgres" }
$resolvedPgnssHost = if ($env:PGNSS_MYSQL_HOST) { $env:PGNSS_MYSQL_HOST } elseif ($env:PGNSS_POSTGRES_HOST) { $env:PGNSS_POSTGRES_HOST } elseif ($env:PGN_POSTGRES_HOST) { $env:PGN_POSTGRES_HOST } else { "127.0.0.1" }
$resolvedPgnssPort = if ($env:PGNSS_MYSQL_TCP_PORT) { $env:PGNSS_MYSQL_TCP_PORT } elseif ($env:PGNSS_POSTGRES_PORT) { $env:PGNSS_POSTGRES_PORT } elseif ($env:PGN_POSTGRES_PORT) { $env:PGN_POSTGRES_PORT } else { "5432" }

$env:PGNSS_MYSQL_DATABASE = $resolvedPgnssDb
$env:PGNSS_MYSQL_HOST = $resolvedPgnssHost
$env:PGNSS_MYSQL_TCP_PORT = $resolvedPgnssPort
$env:INSTALLER_USERID = $resolvedPgnssUser
$env:INSTALLER_PWD = $resolvedPgnssPassword
$env:MYSQL_ROOT_USER = if ($env:MYSQL_ROOT_USER) { $env:MYSQL_ROOT_USER } else { $resolvedPgnssUser }
$env:MYSQL_ROOT_PASSWORD = if ($env:MYSQL_ROOT_PASSWORD) { $env:MYSQL_ROOT_PASSWORD } else { $resolvedPgnssPassword }

$env:PGNSS_POSTGRES_DB = $resolvedPgnssDb
$env:PGNSS_POSTGRES_USER = $resolvedPgnssUser
$env:PGNSS_POSTGRES_PASSWORD = $resolvedPgnssPassword
$env:PGNSS_POSTGRES_PORT = $resolvedPgnssPort
$env:PGN_POSTGRES_DB = $resolvedPgnssDb
$env:PGN_POSTGRES_USER = $resolvedPgnssUser
$env:PGN_POSTGRES_PASSWORD = $resolvedPgnssPassword
$env:PGN_POSTGRES_PORT = $resolvedPgnssPort
$env:PGN_SERVER_PORT = if ($env:PGN_SERVER_PORT) { $env:PGN_SERVER_PORT } else { "8006" }
$env:PGN_DATABASE_URL = "postgresql://$($env:INSTALLER_USERID):$($env:INSTALLER_PWD)@$($env:PGNSS_MYSQL_HOST):$($env:PGNSS_MYSQL_TCP_PORT)/$($env:PGNSS_MYSQL_DATABASE)"
