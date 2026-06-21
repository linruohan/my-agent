#!/usr/bin/env bash
# 安装可选 Web 字体（LXGW WenKai GB 分片）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="$ROOT/web/fonts/lxgwwenkaigb-regular"
TMP="${TMPDIR:-/tmp}/my-agent-font-install"

command -v npm >/dev/null 2>&1 || { echo "需要 npm"; exit 1; }

mkdir -p "$TMP"
cd "$TMP"
[ -f package.json ] || npm init -y >/dev/null 2>&1
npm install lxgw-wenkai-gb-web --no-save
SRC="$TMP/node_modules/lxgw-wenkai-gb-web/fonts/lxgwwenkaigb-regular"
[ -d "$SRC" ] || { echo "字体包路径不存在: $SRC"; exit 1; }

mkdir -p "$TARGET"
cp -R "$SRC/"* "$TARGET/"
CSS_SRC="$TMP/node_modules/lxgw-wenkai-gb-web/css/result.css"
[ -f "$CSS_SRC" ] && cp "$CSS_SRC" "$TARGET/result.css"
echo "完成：$(ls "$TARGET"/*.woff2 2>/dev/null | wc -l | tr -d ' ') 个 woff2 已安装"
