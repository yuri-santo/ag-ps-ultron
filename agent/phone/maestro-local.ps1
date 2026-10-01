param([ValidateSet('version', 'help')][string]$Operation = 'version')
$ErrorActionPreference = 'Stop'
$cli = Join-Path $HOME 'tools\maestro-2.11.0\maestro\bin\maestro.bat'
if (-not (Test-Path -LiteralPath $cli -PathType Leaf)) { throw 'Pinned Maestro CLI not installed.' }
$env:MAESTRO_CLI_NO_ANALYTICS = '1'
$env:MAESTRO_CLI_ANALYSIS_NOTIFICATION_DISABLED = 'true'
if ($Operation -eq 'version') { & $cli --version } else { & $cli --help }
exit $LASTEXITCODE
