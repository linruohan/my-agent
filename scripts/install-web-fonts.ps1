# 安装可选 Web 字体（LXGW WenKai GB 分片）
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Target = Join-Path $Root "web\fonts\lxgwwenkaigb-regular"
$Tmp = Join-Path $env:TEMP "my-agent-font-install"

Write-Host "安装 lxgw-wenkai-gb-web …"
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-Error "需要 Node.js / npm。请安装后重试，或在设置中使用「系统默认」字体。"
}

New-Item -ItemType Directory -Force -Path $Tmp | Out-Null
Push-Location $Tmp
try {
    if (-not (Test-Path "package.json")) {
        npm init -y | Out-Null
    }
    npm install lxgw-wenkai-gb-web --no-save 2>&1 | Out-Host
    $Src = Join-Path $Tmp "node_modules\lxgw-wenkai-gb-web\fonts\lxgwwenkaigb-regular"
    if (-not (Test-Path $Src)) {
        Write-Error "未找到字体包内容：$Src"
    }
    New-Item -ItemType Directory -Force -Path $Target | Out-Null
    Copy-Item -Path (Join-Path $Src "*") -Destination $Target -Recurse -Force
    $CssSrc = Join-Path $Tmp "node_modules\lxgw-wenkai-gb-web\css\result.css"
    if (Test-Path $CssSrc) {
        Copy-Item $CssSrc (Join-Path $Root "web\fonts\lxgwwenkaigb-regular\result.css") -Force
    }
    $count = (Get-ChildItem (Join-Path $Target "*.woff2") -ErrorAction SilentlyContinue).Count
    Write-Host "完成：已安装 $count 个 woff2 到 $Target"
}
finally {
    Pop-Location
}
