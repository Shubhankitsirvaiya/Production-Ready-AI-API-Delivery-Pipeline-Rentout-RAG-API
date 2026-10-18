<#
.SYNOPSIS
Pins one environment to an immutable GHCR image tag.

.DESCRIPTION
Use this script for both rollout and rollback. A rollout promotes a newer tested
SHA; a rollback promotes the previously known-good SHA. Argo CD then reconciles
the Git change with Kubernetes.
#>

param(
    # Environment whose Kustomize image tag should change.
    [Parameter(Mandatory = $true)]
    [ValidateSet("dev", "test", "prod")]
    [string]$Environment,

    # Twelve-character commit tag produced by the Docker workflow.
    [Parameter(Mandatory = $true)]
    [ValidatePattern("^[0-9a-f]{12}$")]
    [string]$ImageTag,

    # Commit the manifest change after editing it.
    [switch]$Commit,

    # Push the commit to origin/main so Argo CD can observe it.
    [switch]$Push
)

$ErrorActionPreference = "Stop"

# Resolve the target overlay from the selected environment.
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$overlayPath = Join-Path $repoRoot "k8s\overlays\$Environment\kustomization.yaml"

if (-not (Test-Path $overlayPath)) {
    throw "Environment overlay not found: $overlayPath"
}

# Read the overlay and replace only the first newTag value.
$content = Get-Content -LiteralPath $overlayPath -Raw
$updated = [regex]::Replace($content, '(?m)^(\s*newTag:\s*)[0-9a-f]{12}\s*$', "`${1}$ImageTag", 1)

if ($updated -eq $content) {
    throw "No twelve-character newTag field was found in $overlayPath"
}

# Save UTF-8 without a byte-order mark so Linux CI and Kustomize read it consistently.
$utf8NoBom = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText($overlayPath, $updated, $utf8NoBom)

Write-Host "Pinned $Environment to ghcr.io/shubhankitsirvaiya/rentout-rag-chatbot:$ImageTag"

if ($Commit) {
    # Commit only the selected environment manifest.
    git -C $repoRoot add $overlayPath
    git -C $repoRoot commit -m "deploy($Environment): promote image $ImageTag"
}

if ($Push) {
    if (-not $Commit) {
        throw "-Push requires -Commit so there is a Git change for Argo CD to observe."
    }
    # Pushing desired state is the GitOps deployment trigger.
    git -C $repoRoot push origin main
}

