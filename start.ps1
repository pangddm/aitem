# Change to the script directory
Set-Location $PSScriptRoot

Write-Host "================================="
Write-Host "Starting Kubedoctor..."
Write-Host "================================="

# ===============================
# 1. Start Docker services
# ===============================
Write-Host "[1/3] Starting Docker services..."

docker compose up -d 2>$null

if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker services failed to start!"
    exit 1
}

Write-Host "[1/3] Docker services ready."
# ===============================
# 1.5 清理占用的旧后端，保证本次全新启动（多路匹配，避免漏掉占用者）
# ===============================
Write-Host "[1.5/3] 检查并清理旧后端..."

$killPids = @()

# a) 监听 8000 端口的进程
$netPids = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue |
    Where-Object { $_.OwningProcess -gt 0 } |
    Select-Object -ExpandProperty OwningProcess -Unique
$killPids += $netPids

# b) 本项目的 uvicorn 主进程（命令行含 "uvicorn main:app"）
$uvPids = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -match 'uvicorn main:app' } |
    Select-Object -ExpandProperty ProcessId
$killPids += $uvPids

# c) 其 worker 子进程（multiprocessing spawn）
$spawnPids = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -match 'spawn_main' } |
    Select-Object -ExpandProperty ProcessId
$killPids += $spawnPids

$killPids = $killPids | Where-Object { $_ -and $_ -gt 0 } | Select-Object -Unique
foreach ($procId in $killPids) {
    try {
        Stop-Process -Id $procId -Force -ErrorAction Stop
        Write-Host "  已停止旧后端进程 PID=$procId"
    } catch { }
}
Start-Sleep -Seconds 2

Write-Host "[1.5/3] 清理完成。"



# ===============================
# 2. Start FastAPI backend
# ===============================
Write-Host "[2/3] Starting FastAPI..."

# 读取 worker 数（默认 4，可用 .env 的 WEB_WORKERS 覆盖）
$workers = $env:WEB_WORKERS
if (-not $workers) {
    try {
        $workers = (Get-Content "$PSScriptRoot\.env" | Where-Object { $_ -match '^WEB_WORKERS=' }) -split '=',2 | Select-Object -Last 1
    } catch { $workers = $null }
}
if (-not $workers) { $workers = "4" }

Start-Process powershell -ArgumentList @(
    '-NoExit',
    '-Command',
    "conda activate aitem; `$env:PYTHONUNBUFFERED='1'; python -u -m uvicorn main:app --workers $workers --host 0.0.0.0 --port 8000"
)

Write-Host "[2/3] FastAPI process started."


# ===============================
# Wait for FastAPI ready
# ===============================
Write-Host "Waiting for FastAPI + 数据库就绪..."

$maxRetry = 90
$count = 0
$backendReady = $false

while ($count -lt $maxRetry) {
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:8000/health" -UseBasicParsing -TimeoutSec 3
        if ($r.StatusCode -eq 200) { $backendReady = $true; break }
    } catch { }
    $count++
    Write-Host "Waiting for backend+DB... ($count/$maxRetry)"
    Start-Sleep -Seconds 2
}

if (-not $backendReady) {
    Write-Host "FastAPI/数据库未在超时内就绪！"
    exit 1
}

Write-Host "FastAPI + 数据库就绪。"

# 目标集群（SSH + kubectl）冒烟检查：只告警，不阻塞 UI 打开（首次 SSH 冷连接可能超时，加 3 次重试）
try {
    $opsReady = $false
    for ($attempt = 1; $attempt -le 3; $attempt++) {
        $ops = Invoke-WebRequest -Uri "http://127.0.0.1:8000/health/ops" -UseBasicParsing -TimeoutSec 45
        if ($ops.StatusCode -eq 200) { $opsReady = $true; break }
        if ($attempt -lt 3) { Start-Sleep -Seconds 3 }
    }
    if ($opsReady) {
        Write-Host "[OK] 目标集群可达（SSH + kubectl 正常）。"
    } else {
        $clusterMsg = (($ops.Content | ConvertFrom-Json).checks.cluster)
        Write-Host "[警告] 目标集群不可达：$clusterMsg"
        Write-Host "        命令执行（kubectl/SSH）将失败，请检查 TARGET_HOST 是否在线或网络是否连通。"
    }
} catch {
    Write-Host "[警告] 集群冒烟检查失败：$($_.Exception.Message)"
}




# ===============================
# 3. Open UI
# ===============================
Write-Host "[3/3] Starting UI..."

Start-Process "http://localhost:8000/"

Write-Host "[3/3] UI started successfully."

Write-Host "================================="
Write-Host "Kubedoctor is running!"
Write-Host "================================="

