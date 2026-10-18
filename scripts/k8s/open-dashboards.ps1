<#
.SYNOPSIS
Starts local port-forward processes for the API, Argo CD, and Headlamp.
#>

param(
    # Select which RentOut environment should be available on localhost:8000.
    [ValidateSet("dev", "test", "prod")]
    [string]$Environment = "dev"
)

$ErrorActionPreference = "Stop"

# Convert the short environment name into its Kubernetes namespace.
$rentoutNamespace = "rentout-$Environment"

# Each command is started in a hidden PowerShell window and continues running.
$forwardCommands = @(
    # FastAPI and Swagger UI: http://localhost:8000/docs
    "kubectl --namespace $rentoutNamespace port-forward service/rentout-api 8000:80",
    # Argo CD UI: https://localhost:8080
    "kubectl --namespace argocd port-forward service/argocd-server 8080:443",
    # Headlamp UI: http://localhost:4466
    "kubectl --namespace headlamp port-forward service/headlamp 4466:80"
)

foreach ($forwardCommand in $forwardCommands) {
    # A hidden process keeps each tunnel alive without opening extra terminal windows.
    Start-Process powershell `
        -WindowStyle Hidden `
        -ArgumentList "-NoProfile", "-Command", $forwardCommand
}

# Decode Argo CD's generated initial admin password for the local login.
$encodedArgoPassword = kubectl --namespace argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}'
$argoPassword = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($encodedArgoPassword))

# Generate a short-lived token for signing into Headlamp.
$headlampToken = kubectl --namespace headlamp create token headlamp

Write-Host "FastAPI:  http://localhost:8000/docs"
Write-Host "Argo CD:  https://localhost:8080  username=admin  password=$argoPassword"
Write-Host "Headlamp: http://localhost:4466"
Write-Host "Headlamp token: $headlampToken"
Write-Host "LangSmith: https://smith.langchain.com"

