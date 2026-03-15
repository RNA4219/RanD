function Get-InstallerRepoRoot {
    return Split-Path -Parent $PSScriptRoot
}

function Import-InstallerEnv {
    param(
        [Parameter(Mandatory = $true)][string]$RepoRoot
    )

    $envPath = Join-Path $RepoRoot '.env'
    if (-not (Test-Path -LiteralPath $envPath)) {
        return
    }

    foreach ($line in Get-Content -LiteralPath $envPath) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith('#') -or -not $trimmed.Contains('=')) {
            continue
        }
        $pair = $trimmed.Split('=', 2)
        $key = $pair[0].Trim()
        $value = $pair[1].Trim().Trim("'").Trim('"')
        if (-not $key) {
            continue
        }
        [System.Environment]::SetEnvironmentVariable($key, $value, 'Process')
    }
}

function Get-LocalPathOverrides {
    param(
        [Parameter(Mandatory = $true)][string]$RepoRoot,
        [Parameter(Mandatory = $true)][string]$InstallRootPath
    )

    $overrides = @{}
    $candidates = @(
        (Join-Path $RepoRoot 'config\localPathOverrides.json'),
        (Join-Path $InstallRootPath 'config\localPathOverrides.json')
    )

    foreach ($path in $candidates) {
        if (-not (Test-Path -LiteralPath $path)) {
            continue
        }
        $payload = Get-Content -Raw -LiteralPath $path | ConvertFrom-Json -AsHashtable
        if ($payload.ContainsKey('components')) {
            foreach ($entry in $payload.components.GetEnumerator()) {
                $overrides[$entry.Key] = $entry.Value
            }
            continue
        }
        foreach ($entry in $payload.GetEnumerator()) {
            $overrides[$entry.Key] = $entry.Value
        }
    }

    return $overrides
}

function Resolve-ComponentPath {
    param(
        [Parameter(Mandatory = $true)]$Component,
        [Parameter(Mandatory = $true)][hashtable]$Overrides
    )

    $resolvedPath = $null
    $resolutionSource = 'remote-only'

    if ($Overrides.ContainsKey($Component.name) -and $Overrides[$Component.name]) {
        $resolvedPath = $Overrides[$Component.name]
        $resolutionSource = 'override-json'
    }
    elseif ($Component.envVar -and [System.Environment]::GetEnvironmentVariable([string]$Component.envVar, 'Process')) {
        $resolvedPath = [System.Environment]::GetEnvironmentVariable([string]$Component.envVar, 'Process')
        $resolutionSource = 'repo-env'
    }
    elseif ($Component.pathKey -and $Component.relativePath) {
        $root = [System.Environment]::GetEnvironmentVariable([string]$Component.pathKey, 'Process')
        if ($root) {
            $resolvedPath = Join-Path $root $Component.relativePath
            $resolutionSource = $Component.pathKey
        }
    }

    $localAvailable = $false
    if ($resolvedPath -and (Test-Path -LiteralPath $resolvedPath)) {
        $localAvailable = $true
    }

    return [pscustomobject]@{
        name = $Component.name
        layer = $Component.layer
        required = $Component.required
        pathKey = $Component.pathKey
        relativePath = $Component.relativePath
        envVar = $Component.envVar
        remoteUrl = $Component.remoteUrl
        installSubdir = $Component.installSubdir
        pinnedCommit = $Component.pinnedCommit
        resolvedLocalPath = $resolvedPath
        localResolution = $resolutionSource
        localAvailable = $localAvailable
    }
}

function Get-ResolvedComponents {
    param(
        [Parameter(Mandatory = $true)][string]$RepoRoot,
        [Parameter(Mandatory = $true)][string]$InstallRootPath,
        [switch]$SkipOptional
    )

    Import-InstallerEnv -RepoRoot $RepoRoot
    $manifestPath = Join-Path $RepoRoot 'manifests\components.json'
    $manifest = Get-Content -Raw $manifestPath | ConvertFrom-Json
    if ($SkipOptional) {
        $manifest = $manifest | Where-Object { $_.required }
    }

    $overrides = Get-LocalPathOverrides -RepoRoot $RepoRoot -InstallRootPath $InstallRootPath
    return @($manifest | ForEach-Object { Resolve-ComponentPath -Component $_ -Overrides $overrides })
}
