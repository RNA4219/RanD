[CmdletBinding()]
param(
    [ValidateSet('auto', 'local', 'remote')]
    [string]$Mode = 'auto',

    [string]$InstallRoot = '.installed',

    [switch]$Force,

    [switch]$SkipOptional
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Resolve-Components.ps1')

function Invoke-CloneAndPin {
    param(
        [Parameter(Mandatory = $true)][string]$SourcePath,
        [Parameter(Mandatory = $true)][string]$TargetPath,
        [Parameter(Mandatory = $true)][string]$PinnedCommit
    )

    git clone $SourcePath $TargetPath
    git -C $TargetPath checkout $PinnedCommit
}

function Remove-TargetIfNeeded {
    param(
        [Parameter(Mandatory = $true)][string]$TargetPath,
        [Parameter(Mandatory = $true)][bool]$ShouldForce
    )

    if (-not (Test-Path -LiteralPath $TargetPath)) {
        return $true
    }

    if (-not $ShouldForce) {
        Write-Host "[skip] $TargetPath already exists. Use -Force to recreate it."
        return $false
    }

    Write-Host "[reset] removing and recreating $TargetPath"
    Remove-Item -LiteralPath $TargetPath -Recurse -Force
    return $true
}

$repoRoot = Get-InstallerRepoRoot
$installRootPath = Join-Path $repoRoot $InstallRoot
$reposRoot = Join-Path $installRootPath 'repos'
$stateRoot = Join-Path $installRootPath 'state'
$logsRoot = Join-Path $installRootPath 'logs'
$configRoot = Join-Path $installRootPath 'config'

foreach ($path in @($installRootPath, $reposRoot, $stateRoot, $logsRoot, $configRoot)) {
    if (-not (Test-Path -LiteralPath $path)) {
        New-Item -ItemType Directory -Path $path | Out-Null
    }
}

$components = Get-ResolvedComponents -RepoRoot $repoRoot -InstallRootPath $installRootPath -SkipOptional:$SkipOptional.IsPresent

foreach ($component in $components) {
    $targetPath = Join-Path $installRootPath $component.installSubdir
    $useLocal = $false

    switch ($Mode) {
        'local' { $useLocal = $component.localAvailable }
        'remote' { $useLocal = $false }
        default { $useLocal = $component.localAvailable }
    }

    $canProceed = Remove-TargetIfNeeded -TargetPath $targetPath -ShouldForce:$Force.IsPresent
    if (-not $canProceed) {
        continue
    }

    $targetParent = Split-Path -Parent $targetPath
    if (-not (Test-Path -LiteralPath $targetParent)) {
        New-Item -ItemType Directory -Path $targetParent | Out-Null
    }

    if ($useLocal) {
        Write-Host "[clone-local] $($component.name) <= $($component.resolvedLocalPath) @ $($component.pinnedCommit)"
        Invoke-CloneAndPin -SourcePath $component.resolvedLocalPath -TargetPath $targetPath -PinnedCommit $component.pinnedCommit
        continue
    }

    if ($Mode -eq 'local' -and -not $component.localAvailable) {
        Write-Warning "$($component.name) local path could not be resolved, so it is skipped in -Mode local."
        continue
    }

    if ([string]::IsNullOrWhiteSpace($component.remoteUrl)) {
        Write-Warning "$($component.name) cannot be installed because remoteUrl is not set."
        continue
    }

    if ($Mode -eq 'auto' -and $component.localResolution -ne 'remote-only' -and -not $component.localAvailable) {
        Write-Warning "$($component.name) local path was resolved via $($component.localResolution) but not found. Falling back to remote clone."
    }

    Write-Host "[clone-remote] $($component.name) <= $($component.remoteUrl) @ $($component.pinnedCommit)"
    Invoke-CloneAndPin -SourcePath $component.remoteUrl -TargetPath $targetPath -PinnedCommit $component.pinnedCommit
}

Write-Host ''
Write-Host "Done: $installRootPath"
Write-Host "Check status: .\\scripts\\status.ps1"
