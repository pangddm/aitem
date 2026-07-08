# 切换到脚本所在目录
Set-Location $PSScriptRoot

Write-Host "================================="
Write-Host "启动 Kubedoctor..."
Write-Host "================================="

Write-Host "[1/2] 启动 Docker 服务..."
docker compose up -d

if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker Compose 启动失败！"
    exit 1
}

Write-Host "[2/2] 启动 FastAPI..."
uvicorn main:app --reload