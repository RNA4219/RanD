[CmdletBinding()]
param(
    [string]$InstallRoot = '.installed',
    [switch]$SkipOptional
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Resolve-Components.ps1')

$repoRoot = Get-InstallerRepoRoot
$installRootPath = Join-Path $repoRoot $InstallRoot
$components = Get-ResolvedComponents -RepoRoot $repoRoot -InstallRootPath $installRootPath -SkipOptional:$SkipOptional.IsPresent

$rows = foreach ($component in $components) {
    $targetPath = Join-Path $installRootPath $component.installSubdir
    [pscustomobject]@{
        Name = $component.name
        Layer = $component.layer
        Required = $component.required
        LocalAvailable = $component.localAvailable
        LocalResolution = $component.localResolution
        ResolvedLocalPath = $component.resolvedLocalPath
        Installed = Test-Path -LiteralPath $targetPath
        PinnedCommit = $component.pinnedCommit
        RemoteUrl = $component.remoteUrl
        TargetPath = $targetPath
    }
}

$rows | Sort-Object Layer, Name | Format-Table -AutoSize
