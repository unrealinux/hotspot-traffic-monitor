#!/usr/bin/env bash
# 用 gh 认证后的 token 推送 hotspot-traffic-monitor 到 GitHub
# 前置: 先运行 gh auth login 完成认证
set -e
GH="$(cd "$(dirname "$0")/.." && pwd)/ghbin/gh_2.102.0_linux_amd64/bin/gh"
[ -x "$GH" ] || { echo "找不到 gh, 先安装: curl -L -o /tmp/gh.tgz https://gh-proxy.com/https://github.com/cli/cli/releases/download/v2.102.0/gh_2.102.0_linux_amd64.tar.gz && tar xzf /tmp/gh.tgz -C $(dirname "$0")/.."; exit 1; }

cd "$(dirname "$0")"   # 进入 vnstat-local 目录

# 若没配代理且需要
export https_proxy="${https_proxy:-http://127.0.0.1:10808}"
export http_proxy="${http_proxy:-http://127.0.0.1:10808}"

TOKEN="$("$GH" auth token 2>/dev/null || true)"
if [ -z "$TOKEN" ]; then
  echo "未登录 gh, 请先运行: $GH auth login"
  exit 1
fi

echo "用 gh token 推送 main 到 origin..."
git push "https://x-access-token:${TOKEN}@github.com/unrealinux/hotspot-traffic-monitor.git" main
echo "完成。推送完建议: unset https_proxy http_proxy; git config --unset http.https://github.com/.extraheader || true"
