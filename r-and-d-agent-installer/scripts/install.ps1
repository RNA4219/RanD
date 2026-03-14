[CmdletBinding()]
param(
    [ValidateSet('auto', 'local', 'remote')]
    [string]$Mode = 'auto',

    [string]$InstallRoot = '.installed',

    [switch]$Force,

    [switch]$SkipOptional
)

$ErrorActionPreference = 'Stop'

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

$repoRoot = Split-Path -Parent $PSScriptRoot
$manifestPath = Join-Path $repoRoot 'manifests\\components.json'
$manifest = Get-Content -Raw $manifestPath | ConvertFrom-Json

if ($SkipOptional) {
    $manifest = $manifest | Where-Object { $_.required }
}

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

foreach ($component in $manifest) {
    $targetPath = Join-Path $installRootPath $component.installSubdir
    $localExists = $false

    if ($component.localPath -and (Test-Path -LiteralPath $component.localPath)) {
        $localExists = $true
    }

    $useLocal = $false
    switch ($Mode) {
        'local' { $useLocal = $localExists }
        'remote' { $useLocal = $false }
        default { $useLocal = $localExists }
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
        Write-Host "[clone-local] $($component.name) <= $($component.localPath) @ $($component.pinnedCommit)"
        Invoke-CloneAndPin -SourcePath $component.localPath -TargetPath $targetPath -PinnedCommit $component.pinnedCommit
        continue
    }

    if ($Mode -eq 'local' -and -not $localExists) {
        Write-Warning "$($component.name) localPath was not found, so it is skipped in -Mode local."
        continue
    }

    if ([string]::IsNullOrWhiteSpace($component.remoteUrl)) {
        Write-Warning "$($component.name) cannot be installed because remoteUrl is not set."
        continue
    }

    Write-Host "[clone-remote] $($component.name) <= $($component.remoteUrl) @ $($component.pinnedCommit)"
    Invoke-CloneAndPin -SourcePath $component.remoteUrl -TargetPath $targetPath -PinnedCommit $component.pinnedCommit
}

Write-Host ''
Write-Host "Done: $installRootPath"
Write-Host "Check status: .\\scripts\\status.ps1"
