# Atalho no Windows para o homelab que roda no WSL Debian.
#   .\Homelab.ps1 up all
#   .\Homelab.ps1 ps ia
#   .\Homelab.ps1 check
param(
    [Parameter(Mandatory = $true, Position = 0)][ValidateSet('up', 'down', 'ps', 'logs', 'pull', 'config', 'check')]
    [string]$Acao,
    [Parameter(Position = 1)][string]$Stack = 'all',
    [string]$Distro = 'Debian',
    [string]$Raiz = '/opt/agent-stacks/homelab'
)
$ErrorActionPreference = 'Stop'
if ($Stack -notmatch '^[a-z]+$') { throw "Stack inválido: $Stack" }
wsl.exe -d $Distro -u root -- bash "$Raiz/scripts/homelab.sh" $Acao $Stack
exit $LASTEXITCODE
