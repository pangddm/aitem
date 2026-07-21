# Change to the script directory
Set-Location $PSScriptRoot

Write-Host "================================="
Write-Host "Starting Kubedoctor..."
Write-Host "================================="

Write-Host "[1/3] Starting Docker services..."
docker compose up -d 2>$null
# 忽略已运行容器的非零退出码

Write-Host "[1/3] Docker services ready."

Write-Host "[2/3] Starting FastAPI..."
Start-Process powershell -ArgumentList @(
    '-NoExit',
    '-Command',
    'conda activate aitem; uvicorn main:app --reload'
)

if ($LASTEXITCODE -ne 0) {
    Write-Host "FastAPI failed to start!"
    exit 1
}

Write-Host "[2/3] Starting FastAPI successfully."

Write-Host "[3/3] Starting UI..."
python gui/main.py

if ($LASTEXITCODE -ne 0) {
    Write-Host "UI failed to start!"
    exit 1
}

Write-Host "[3/3] Starting UI successfully."
