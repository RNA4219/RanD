[CmdletBinding()]
param(
    [string]$Preset = "paper_arxiv_ai_recent",
    [int]$MaxItems = 0
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = (Join-Path $root "src")
$args = @("-m", "rand_research.cli", "run-once", "--preset", $Preset)
if ($MaxItems -gt 0) {
    $args += @("--max-items", "$MaxItems")
}
python @args
