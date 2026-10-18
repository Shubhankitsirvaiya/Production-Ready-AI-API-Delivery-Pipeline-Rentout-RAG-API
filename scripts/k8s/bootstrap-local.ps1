<#
.SYNOPSIS
Creates the complete local Project 12 platform on Minikube.

.DESCRIPTION
The script starts Minikube with Docker Desktop, enables Metrics Server, installs
Headlamp and Argo CD, creates runtime Secrets from separate environment files,
and then registers all three GitOps applications with Argo CD.

Real credentials never get written to a tracked YAML file.
#>

# Stop immediately when any external command or PowerShell statement fails.
$ErrorActionPreference = "Stop"

# Resolve the repository root by moving two levels above scripts/k8s.
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path

# Docker Desktop is installed here on this machine, but its CLI is not in PATH.
$dockerBin = "C:\Users\Shubhankit\AppData\Local\Programs\DockerDesktop\resources\bin"

# Add Docker Desktop CLI tools only when the docker command is currently unavailable.
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    $dockerExe = Join-Path $dockerBin "docker.exe"
    if (-not (Test-Path $dockerExe)) {
        throw "Docker CLI was not found. Start Docker Desktop and update `$dockerBin in this script if its install path changed."
    }
    # This PATH update affects only the current script process and its child commands.
    $env:Path = "$dockerBin;$env:Path"
}

# Verify every command needed by the bootstrap flow before changing the cluster.
foreach ($commandName in @("docker", "minikube", "kubectl", "helm")) {
    if (-not (Get-Command $commandName -ErrorAction SilentlyContinue)) {
        throw "Required command '$commandName' is not installed or is not available in PATH."
    }
}

# Docker must be running because Minikube uses the Docker driver on this machine.
docker info | Out-Null

# Read Minikube status without stopping the script when the cluster is not running yet.
$minikubeStatus = minikube status --format='{{.Host}}' 2>$null

# Start the existing cluster profile only when its host is not already Running.
if ($minikubeStatus -ne "Running") {
    minikube start --driver=docker
}

# Metrics Server provides live CPU/memory values for Headlamp, kubectl top, and HPA.
minikube addons enable metrics-server

# Read simple KEY=VALUE entries from .env without printing any values.
function Read-DotEnv {
    param(
        # Full path to the local .env file.
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    # Store parsed keys in a case-sensitive dictionary.
    $values = @{}

    # Ignore blank lines, comments, and malformed lines.
    foreach ($line in Get-Content -LiteralPath $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#") -or -not $trimmed.Contains("=")) {
            continue
        }

        # Split only at the first equals sign so keys may contain complex values.
        $name, $value = $trimmed.Split("=", 2)
        $values[$name.Trim()] = $value.Trim().Trim('"').Trim("'")
    }

    return $values
}

# .env is a backward-compatible shared fallback for local development.
$sharedEnvPath = Join-Path $repoRoot ".env"

# Every environment can override credentials independently. The real files are
# ignored by Git; only their documented *.example templates are committed.
$environmentDefinitions = @(
    @{ Name = "dev"; Namespace = "rentout-dev"; EnvPath = (Join-Path $repoRoot ".env.dev") },
    @{ Name = "test"; Namespace = "rentout-test"; EnvPath = (Join-Path $repoRoot ".env.test") },
    @{ Name = "prod"; Namespace = "rentout-prod"; EnvPath = (Join-Path $repoRoot ".env.prod") }
)

# Create all environment namespaces before creating Secrets inside them.
foreach ($environment in $environmentDefinitions) {
    # Prefer the environment-specific file, then fall back to the shared .env.
    $selectedEnvPath = $environment.EnvPath
    if (-not (Test-Path $selectedEnvPath)) {
        if (-not (Test-Path $sharedEnvPath)) {
            throw "Missing $selectedEnvPath and fallback $sharedEnvPath. Create the environment file from its example."
        }
        Write-Warning "$selectedEnvPath is missing; using shared .env for $($environment.Name)."
        $selectedEnvPath = $sharedEnvPath
    }

    # Parse this environment's secrets without printing their values.
    $secretValues = Read-DotEnv -Path $selectedEnvPath

    # OpenAI is mandatory because the init container generates embeddings.
    if (-not $secretValues["OPENAI_API_KEY"] -or $secretValues["OPENAI_API_KEY"] -like "your_*" ) {
        throw "OPENAI_API_KEY is missing or contains an example value in $selectedEnvPath."
    }

    # LangSmith is optional and remains disabled by default in the ConfigMap.
    if (-not $secretValues["LANGSMITH_API_KEY"]) {
        Write-Warning "LANGSMITH_API_KEY is not set for $($environment.Name); trace export is unavailable."
    }

    # Use the namespace associated with the current environment definition.
    $namespace = $environment.Namespace

    # --dry-run emits YAML and kubectl apply makes the command idempotent.
    kubectl create namespace $namespace --dry-run=client -o yaml | kubectl apply -f -

    # Create or update application credentials without writing a Secret file to disk.
    kubectl -n $namespace create secret generic rentout-api-secrets `
        --from-literal="OPENAI_API_KEY=$($secretValues['OPENAI_API_KEY'])" `
        --from-literal="LANGSMITH_API_KEY=$($secretValues['LANGSMITH_API_KEY'])" `
        --from-literal="LANGSMITH_WORKSPACE_ID=$($secretValues['LANGSMITH_WORKSPACE_ID'])" `
        --dry-run=client -o yaml | kubectl apply -f -

    # Private GHCR packages require a token with read:packages permission.
    if ($secretValues["GHCR_USERNAME"] -and $secretValues["GHCR_TOKEN"]) {
        kubectl -n $namespace create secret docker-registry ghcr-pull-secret `
            --docker-server="ghcr.io" `
            --docker-username="$($secretValues['GHCR_USERNAME'])" `
            --docker-password="$($secretValues['GHCR_TOKEN'])" `
            --dry-run=client -o yaml | kubectl apply -f -
    }
    else {
        Write-Warning "GHCR credentials are absent for $namespace. This works only when the GHCR package is public."
    }
}

# Install the Headlamp Kubernetes UI into its own namespace.
helm upgrade --install headlamp headlamp/headlamp `
    --namespace headlamp `
    --create-namespace `
    --values (Join-Path $repoRoot "k8s\platform\headlamp-values.yaml") `
    --wait `
    --timeout 5m

# Create the Argo CD namespace idempotently.
kubectl create namespace argocd --dry-run=client -o yaml | kubectl apply -f -

# Install the official non-HA Argo CD bundle, suitable for this local demo cluster.
kubectl apply --server-side --force-conflicts `
    --namespace argocd `
    --filename "https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml"

# Wait until the Argo CD API server is available before adding Applications.
kubectl rollout status deployment/argocd-server --namespace argocd --timeout=5m

# Register the AppProject and dev/test/prod Applications with Argo CD.
kubectl apply --kustomize (Join-Path $repoRoot "argocd")

# Display a concise final state without revealing any secret values.
kubectl get nodes
kubectl get applications --namespace argocd

Write-Host "Bootstrap complete. Run scripts/k8s/open-dashboards.ps1 to open local access tunnels."

