# Windows exe 构建脚本（PyInstaller 单文件 + 发布目录组装）
param(
    [switch]$SkipFonts,
    [switch]$IncludeDevData,
    [switch]$NoInitDatabases,
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Invoke-Checked {
    param([string[]]$Command, [string]$Label)
    Write-Host ">> $Label"
    & @Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Label 失败 (exit $LASTEXITCODE)"
    }
}

Write-Host "=== my-agent Windows 构建 ==="
Write-Host "项目目录: $Root"

if (-not $SkipFonts) {
    $woffCount = (Get-ChildItem "web\fonts\lxgwwenkaigb-regular\*.woff2" -ErrorAction SilentlyContinue).Count
    if ($woffCount -lt 1) {
        Write-Host "未检测到 LXGW 字体，尝试安装（可用 -SkipFonts 跳过）…"
        if (Get-Command npm -ErrorAction SilentlyContinue) {
            & "$Root\scripts\install-web-fonts.ps1"
        } else {
            Write-Warning "未安装 npm，将使用系统字体打包。"
        }
    }
}

Invoke-Checked @($Python, "-m", "pip", "install", "--upgrade", "pip") "升级 pip"
Invoke-Checked @($Python, "-m", "pip", "install", "-e", ".") "安装项目依赖"
Invoke-Checked @($Python, "-m", "pip", "install", "-e", ".[build]") "安装构建依赖"

Invoke-Checked @($Python, "-m", "PyInstaller", "--noconfirm", "--clean", "packaging/my-agent.spec") "PyInstaller 打包"

$stageArgs = @(
    "packaging/stage_release.py",
    "--release-dir", "dist/my-agent"
)
if ($IncludeDevData) {
    $stageArgs += "--include-dev-data"
}
if ($NoInitDatabases) {
    $stageArgs += "--no-init-databases"
}
Invoke-Checked @($Python, @stageArgs) "组装发布目录"

$releaseDir = Join-Path $Root "dist\my-agent"
$exe = Join-Path $releaseDir "my-agent.exe"
if (-not (Test-Path $exe)) {
    throw "未找到输出文件: $exe"
}

Write-Host ""
Write-Host "构建完成: $releaseDir"
Write-Host "  my-agent.exe"
Write-Host "  config/  web/  data/  (主题位于 web/themes/)"
Write-Host "可直接将整个 dist\my-agent 文件夹分发给用户。"
