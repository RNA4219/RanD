[CmdletBinding()]
param(
    [string]$InstallRoot = '.installed'
)

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$manifestPath = Join-Path $repoRoot 'manifests\\components.json'
$manifest = Get-Content -Raw $manifestPath | ConvertFrom-Json
$installRootPath = Join-Path $repoRoot $InstallRoot

$rows = foreach ($component in $manifest) {
    $targetPath = Join-Path $installRootPath $component.installSubdir
    $localAvailable = $false

    if ($component.localPath -and (Test-Path -LiteralPath $component.localPath)) {
        $localAvailable = $true
    }

    [pscustomobject]@{
        Name = $component.name
        Layer = $component.layer
        Required = $component.required
        LocalAvailable = $localAvailable
        Installed = Test-Path -LiteralPath $targetPath
        PinnedCommit = $component.pinnedCommit
        LocalPath = $component.localPath
        RemoteUrl = $component.remoteUrl
        TargetPath = $targetPath
    }
}

$rows | Sort-Object Layer, Name | Format-Table -AutoSize
