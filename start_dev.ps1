# AI Browser Assistant - 一键启动开发环境
# 用法: 在项目根目录右键 -> "使用 PowerShell 运行" 或终端输入 .\start_dev.ps1

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  AI Browser Assistant  开发模式" -ForegroundColor Cyan
Write-Host "  后端 :8080 (auto-reload)  |  前端 :5173 (HMR)" -ForegroundColor Cyan
Write-Host "  改代码自动生效，无需手动重启！" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 启动后端
Write-Host ">>> 启动后端..." -ForegroundColor Green
Start-Process pwsh -ArgumentList "-NoExit", "-Command", "cd 'e:\AI browser\backend'; Write-Host '=== 后端 FastAPI :8080 (自动reload) ===' -ForegroundColor Green; python -m uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload" -WindowStyle Normal

Start-Sleep -Seconds 2

# 启动前端
Write-Host ">>> 启动前端..." -ForegroundColor Blue
Start-Process pwsh -ArgumentList "-NoExit", "-Command", "cd 'e:\AI browser\frontend'; Write-Host '=== 前端 Vite :5173 (HMR) ===' -ForegroundColor Blue; npm run dev" -WindowStyle Normal

Write-Host ""
Write-Host "两个窗口已打开，分别显示后端和前端日志" -ForegroundColor Yellow
Write-Host "关闭窗口 = 停止对应服务" -ForegroundColor Yellow
