[CmdletBinding()]
param(
    [int]$Port = 8000,
    [switch]$ReplaceExistingRegBridge
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$repoRoot = Split-Path -Parent $PSScriptRoot
$artifactDir = Join-Path $repoRoot 'artifacts\browser-e2e'

function Get-DemoListeners {
    return @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
}

function Get-ProcessInventory {
    return @(Get-CimInstance Win32_Process)
}

function Get-RegBridgeRootPid([int]$ListenerPid, [object[]]$Inventory) {
    $current = $Inventory | Where-Object ProcessId -eq $ListenerPid | Select-Object -First 1
    for ($depth = 0; $current -and $depth -lt 4; $depth++) {
        if ($current.CommandLine -match '(?i)-m\s+uvicorn\s+app\.main:app') {
            return [int]$current.ProcessId
        }
        if ($current.CommandLine -notmatch '(?i)spawn_main|multiprocessing') {
            break
        }
        $current = $Inventory | Where-Object ProcessId -eq $current.ParentProcessId | Select-Object -First 1
    }
    return $null
}

function Stop-ConfirmedTree([int]$RootPid, [object[]]$Inventory) {
    $descendants = [System.Collections.Generic.List[int]]::new()
    $pending = [System.Collections.Generic.Queue[int]]::new()
    $pending.Enqueue($RootPid)
    while ($pending.Count) {
        $parent = $pending.Dequeue()
        foreach ($child in $Inventory | Where-Object ParentProcessId -eq $parent) {
            $descendants.Add([int]$child.ProcessId)
            $pending.Enqueue([int]$child.ProcessId)
        }
    }
    foreach ($processId in @($descendants | Select-Object -Last $descendants.Count)) {
        Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
    }
    Stop-Process -Id $RootPid -Force
}

Set-Location -LiteralPath $repoRoot
$requiredServices = @('postgres', 'keycloak', 'minio', 'clamav')
$runningServices = @(docker compose ps --services --status running)
$missingServices = @($requiredServices | Where-Object { $_ -notin $runningServices })
if ($missingServices.Count) {
    throw "Required Compose services are not running: $($missingServices -join ', '). Run: docker compose up -d postgres keycloak minio clamav"
}

$listeners = @(Get-DemoListeners)
if ($listeners.Count) {
    $inventory = Get-ProcessInventory
    $roots = @()
    foreach ($listener in $listeners) {
        $process = $inventory | Where-Object ProcessId -eq $listener.OwningProcess | Select-Object -First 1
        Write-Host "Port $Port owner: PID=$($listener.OwningProcess) EXE=$($process.ExecutablePath) COMMAND=$($process.CommandLine)"
        $root = Get-RegBridgeRootPid -ListenerPid $listener.OwningProcess -Inventory $inventory
        if ($null -eq $root) {
            throw "Port $Port is owned by an unrelated process. Refusing to stop it."
        }
        $roots += $root
    }
    if (-not $ReplaceExistingRegBridge) {
        throw "A confirmed RegBridge backend already owns port $Port. Re-run with -ReplaceExistingRegBridge to replace it safely."
    }
    foreach ($root in $roots | Sort-Object -Unique) {
        Stop-ConfirmedTree -RootPid $root -Inventory $inventory
    }
    $deadline = (Get-Date).AddSeconds(10)
    $remainingListeners = @(Get-DemoListeners)
    while ($remainingListeners.Count -and (Get-Date) -lt $deadline) {
        Start-Sleep -Milliseconds 200
        $remainingListeners = @(Get-DemoListeners)
    }
    if ($remainingListeners.Count) {
        throw "The confirmed RegBridge process did not release port $Port."
    }
}

New-Item -ItemType Directory -Path $artifactDir -Force | Out-Null
$python = (Get-Command python).Source
$effectiveAi = & $python -c "from app.core.config import get_settings; s=get_settings(); print(f'{s.llm_provider}|{s.gemini_model}')"
$provider, $model = $effectiveAi -split '\|', 2
Write-Host "AI provider=$provider model=$model"
$stdout = Join-Path $artifactDir 'demo-runtime.stdout.log'
$stderr = Join-Path $artifactDir 'demo-runtime.stderr.log'
$previousWarmup = [Environment]::GetEnvironmentVariable('REGULATORY_WARMUP_ON_STARTUP', 'Process')
$previousDisableXet = [Environment]::GetEnvironmentVariable('HF_HUB_DISABLE_XET', 'Process')
[Environment]::SetEnvironmentVariable('REGULATORY_WARMUP_ON_STARTUP', 'true', 'Process')
[Environment]::SetEnvironmentVariable('HF_HUB_DISABLE_XET', 'true', 'Process')
try {
    $backend = Start-Process -FilePath $python -ArgumentList @(
        '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', "$Port", '--no-access-log'
    ) -WorkingDirectory $repoRoot -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru
} finally {
    [Environment]::SetEnvironmentVariable('REGULATORY_WARMUP_ON_STARTUP', $previousWarmup, 'Process')
    [Environment]::SetEnvironmentVariable('HF_HUB_DISABLE_XET', $previousDisableXet, 'Process')
}

$healthUri = "http://127.0.0.1:$Port/health"
$deadline = (Get-Date).AddMinutes(30)
$healthy = $false
while ((Get-Date) -lt $deadline) {
    if ($backend.HasExited) {
        throw "RegBridge backend exited during startup. Inspect $stderr."
    }
    try {
        $health = Invoke-RestMethod -Uri $healthUri -TimeoutSec 2
        if ($health.status -eq 'ok') {
            $healthy = $true
            break
        }
    } catch {
        Start-Sleep -Milliseconds 300
    }
}
if (-not $healthy) {
    Stop-Process -Id $backend.Id -Force -ErrorAction SilentlyContinue
    throw "RegBridge did not become healthy within 30 minutes. Inspect $stderr."
}
$finalListeners = @(Get-DemoListeners)
if ($finalListeners.Count -ne 1 -or $finalListeners[0].OwningProcess -ne $backend.Id) {
    throw "Expected exactly one listener owned by PID $($backend.Id); found $($finalListeners.Count)."
}

Write-Host "READY http://127.0.0.1:$Port/entrepreneur/ PID=$($backend.Id) reload=NO"
