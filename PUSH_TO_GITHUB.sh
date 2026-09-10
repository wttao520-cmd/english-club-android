#!/usr/bin/env bash
# 初始化 git 仓库并提交，方便后续推送到 GitHub 触发云端打包
set -e
cd "$(dirname "$0")"

if [ ! -d .git ]; then
  git init
  echo "已初始化 git 仓库"
fi

git add -A

# 首次提交（若已存在提交则跳过，避免重复产生 commit）
if git diff --cached --quiet; then
  echo "没有需要提交的文件"
else
  git -c user.name="${GIT_USER_NAME:-sentence-club}" \
      -c user.email="${GIT_USER_EMAIL:-dev@example.com}" \
      commit -m "句子俱乐部安卓版：Kivy + Buildozer，含内置课程与自然拼读"
  echo "已创建提交"
fi

git branch -M main

echo
echo "================ 下一步 ================"
echo "1) 在 https://github.com/new 创建空仓库（不要勾选 README/LICENSE）"
echo "   仓库名建议：english-club-android"
echo
echo "2) 回到本终端执行（把地址换成你自己的）："
echo "     git remote remove origin 2>/dev/null || true"
echo "     git remote add origin https://github.com/<你的用户名>/english-club-android.git"
echo "     git push -u origin main"
echo
echo "3) 打开 GitHub 仓库 → Actions → Build Android APK → Run workflow"
echo "   约 20~40 分钟后，在 Artifacts 下载 english-club-debug-apk"
echo "========================================"
