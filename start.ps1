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
    "conda activate aitem; uvicorn main:app --workers $workers --host 0.0.0.0 --port 8000"
)

Write-Host "[2/3] FastAPI process started."


# ===============================
# Wait for FastAPI ready
# ===============================
Write-Host "Waiting for FastAPI to be ready..."

$maxRetry = 60
$count = 0
$backendReady = $false

while ($count -lt $maxRetry) {

    try {
        $response = Invoke-WebRequest `
            -Uri "http://127.0.0.1:8000/" `
            -UseBasicParsing `
            -TimeoutSec 2

        if ($response.StatusCode -eq 200) {
            $backendReady = $true
            break
        }
        break
    }
    catch {
        $count++
        Write-Host "Waiting for backend... ($count/$maxRetry)"
        Start-Sleep -Seconds 2
    }
}


if (-not $backendReady) {
    Write-Host "FastAPI failed to start within timeout!"
    exit 1
}

Write-Host "FastAPI is ready."


# ===============================
# 3. Open UI
# ===============================
Write-Host "[3/3] Starting UI..."

Start-Process "http://localhost:8000/"

Write-Host "[3/3] UI started successfully."

Write-Host "================================="
Write-Host "Kubedoctor is running!"
Write-Host "================================="