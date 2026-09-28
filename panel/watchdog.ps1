# Restore the panel process only; never reset the user's network.
$logFile = Join-Path $PSScriptRoot 'watchdog.log'
try {
    $response = Invoke-WebRequest -Uri 'http://127.0.0.1:8090/health' -UseBasicParsing -TimeoutSec 5
    if ($response.StatusCode -eq 200) { exit }
} catch { }
$server = Join-Path $PSScriptRoot 'server.py'
$existing = Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'" | Where-Object { $_.CommandLine -like "*$server*" }
if ($existing) {
    "$(Get-Date -Format o) Painel sem resposta; processo e rede preservados." | Add-Content $logFile
    exit
}
$python = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python314\pythonw.exe'
if (Test-Path -LiteralPath $python) {
    Start-Process -FilePath $python -ArgumentList @($server) -WorkingDirectory $PSScriptRoot -WindowStyle Hidden
    "$(Get-Date -Format o) Painel reiniciado; rede preservada." | Add-Content $logFile
}
