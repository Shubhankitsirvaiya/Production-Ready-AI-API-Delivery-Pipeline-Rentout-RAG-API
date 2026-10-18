<#
.SYNOPSIS
Shows rollout, Pod, HPA, and recent-event status for one environment.
#>

param(
    [ValidateSet("dev", "test", "prod")]
    [string]$Environment = "dev"
)

$ErrorActionPreference = "Stop"
$namespace = "rentout-$Environment"

# Wait for the current Deployment revision to finish or fail.
kubectl --namespace $namespace rollout status deployment/rentout-api --timeout=5m

# Show current and historical rollout revisions.
kubectl --namespace $namespace rollout history deployment/rentout-api

# Show Pod readiness, restarts, IP addresses, and node placement.
kubectl --namespace $namespace get pods -o wide

# Show live CPU and memory when Metrics Server is ready.
kubectl --namespace $namespace top pods

# Show current and desired HPA replicas and observed utilization.
kubectl --namespace $namespace get horizontalpodautoscaler

# Show recent namespace events in chronological order for troubleshooting.
kubectl --namespace $namespace get events --sort-by='.lastTimestamp'
