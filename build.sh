#!/usr/bin/env bash
# 一键打包 APK（需要 Linux + JDK 17 + 约 6GB 磁盘与网络）
set -e

cd "$(dirname "$0")"

echo "==> 1/4 检查 Java 17"
if ! java -version 2>&1 | grep -q 'version "17'; then
  echo "未检测到 JDK 17。请先安装：sudo apt install openjdk-17-jdk"
  exit 1
fi

echo "==> 2/4 安装 buildozer"
python3 -m pip install --upgrade buildozer cython

echo "==> 3/4 生成中文字体子集（可选，失败不影响打包）"
python3 tools/build_font.py || echo "跳过字体子集，APK 将退回系统字体"

echo "==> 4/4 打包（首次会自动下载 Android SDK/NDK，约 20~40 分钟）"
buildozer -v android debug

echo "==> 完成，APK 位于 bin/ 目录"
ls -la bin/*.apk 2>/dev/null || true
