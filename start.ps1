$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$pythonPath = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Create the Python environment first using README.md.'
}
$mysqlPath = Join-Path $PSScriptRoot '.local/mysql/bin/mysqld.exe'
if (Test-Path -LiteralPath $mysqlPath) {
    $connection = Get-NetTCPConnection -LocalPort 3307 -State Listen -ErrorAction SilentlyContinue
    if (-not $connection) {
        $serverBase = (Join-Path $PSScriptRoot '.local/mysql').Replace('\', '/')
        $serverData = (Join-Path $PSScriptRoot '.local/mysql-data').Replace('\', '/')
        $serverLog = (Join-Path $PSScriptRoot '.local/mysql.log').Replace('\', '/')
        Start-Process -FilePath $mysqlPath -ArgumentList '--no-defaults', "--basedir=$serverBase", "--datadir=$serverData", '--port=3307', '--bind-address=127.0.0.1', '--mysqlx=OFF', "--log-error=$serverLog" -WindowStyle Hidden
        Start-Sleep -Seconds 4
    }
}
Write-Host 'Open http://127.0.0.1:5000 in your browser. Press Ctrl+C to stop the app.'
& $pythonPath run.py
