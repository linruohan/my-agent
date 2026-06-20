# 使用 Python 3.13 创建虚拟环境并安装 PaddleOCR 依赖
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "检查 Python 3.13 …"
py -3.13 --version | Out-Null

if (Test-Path ".venv") {
    Write-Host "删除旧 .venv …"
    Remove-Item -Recurse -Force ".venv"
}

Write-Host "创建 .venv (Python 3.13) …"
py -3.13 -m venv .venv

$pip = Join-Path $Root ".venv\Scripts\pip.exe"
$py = Join-Path $Root ".venv\Scripts\python.exe"

Write-Host "升级 pip …"
& $py -m pip install -U pip wheel

Write-Host "安装项目依赖 + PaddleOCR …"
& $pip install -e ".[input,dev]"

Write-Host ""
Write-Host "完成。激活虚拟环境："
Write-Host "  .\.venv\Scripts\Activate.ps1"
Write-Host "运行："
Write-Host "  python main.py"
