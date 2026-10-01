param([string]$Destination = (Join-Path $HOME 'tools\maestro-2.11.0'))
$ErrorActionPreference = 'Stop'
$expected = '5384593cb4e7a106489e75a821d157dd43f4e438df6bc308b72e82c685e1283a'
$target = [IO.Path]::GetFullPath($Destination)
if (Test-Path -LiteralPath $target) { throw 'Target exists; inspect it before any replacement.' }
$stage = Join-Path ([IO.Path]::GetTempPath()) ('ultron-maestro-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $stage | Out-Null
& gh release download cli-2.11.0 --repo mobile-dev-inc/Maestro --pattern maestro.zip --dir $stage
if ($LASTEXITCODE -ne 0) { throw 'Could not download the pinned release.' }
$archive = Join-Path $stage 'maestro.zip'
if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected) {
    throw 'Release digest mismatch; no installation performed.'
}
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [IO.Compression.ZipFile]::OpenRead($archive)
try {
    foreach ($entry in $zip.Entries) {
        $resolved = [IO.Path]::GetFullPath((Join-Path $target $entry.FullName))
        if (-not $resolved.StartsWith($target + '\', [StringComparison]::OrdinalIgnoreCase)) {
            throw 'Unsafe archive path.'
        }
    }
} finally { $zip.Dispose() }
Expand-Archive -LiteralPath $archive -DestinationPath $target
$env:MAESTRO_CLI_NO_ANALYTICS = '1'
$env:MAESTRO_CLI_ANALYSIS_NOTIFICATION_DISABLED = 'true'
& (Join-Path $target 'maestro\bin\maestro.bat') --version
if ($LASTEXITCODE -ne 0) { throw 'Installed CLI did not start. Inspect Java 17+ and the installation.' }
Write-Output ('Installed pinned CLI; no Android packages or settings changed. Archive retained: ' + $archive)
