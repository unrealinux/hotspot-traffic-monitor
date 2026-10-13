#!/usr/bin/env bash
# hotspot-traffic-monitor 一键安装与启动脚本
# 用法:
#   ./setup.sh                  # 安装 + 启动全部服务(vnstatd/sampler/面板/watchdog)
#   ./setup.sh --stop           # 停止全部服务
#   ./setup.sh --status         # 查看服务状态
#   ./setup.sh --iface=wlan0   # 指定要监控的网卡(默认读 vnstat.conf 里的)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
MONITOR="$ROOT/monitor"
VDIR="$ROOT/data"
PY=python3

# ---- 读取 vnstat.conf 里的网卡名作为默认 ----
IFACE=""
if [ -f "$ROOT/vnstat.conf" ]; then
  IFACE=$(grep -oP 'Interface "\K[^"]+' "$ROOT/vnstat.conf" 2>/dev/null || true)
fi

usage() {
  cat <<EOF
用法: $0 [选项]
  (无选项)        安装并启动全部服务
  --stop          停止全部服务
  --status        查看服务状态
  --iface=NAME    指定要监控的网卡 (ip link 查看)
  --no-watchdog   不启动 watchdog 守护
  -h, --help      显示本帮助
EOF
}

stop_all() {
  echo "停止服务..."
  # 先停 watchdog,避免它把刚杀的服务又拉起来
  pkill -f "python3.*monitor/watchdog.py" 2>/dev/null || true
  sleep 1
  pkill -f "python3.*monitor/server.py" 2>/dev/null || true
  pkill -f "python3.*monitor/sampler.py" 2>/dev/null || true
  pkill -f "extracted/usr/sbin/vnstatd" 2>/dev/null || true
  sleep 1
  echo "已停止。"
}

status_all() {
  echo "=== 服务状态 ==="
  local up=0
  for p in "server.py 8688" "sampler.py" "watchdog.py" "vnstatd"; do
    if pgrep -f "$p" >/dev/null 2>&1; then
      echo "  🟢 $p  (pid $(pgrep -f "$p" | head -1))"
      up=$((up+1))
    else
      echo "  🔴 $p"
    fi
  done
  # 面板可达性
  if curl -s --max-time 3 -o /dev/null http://127.0.0.1:8688/; then
    echo "  🟢 面板 HTTP 200 (http://127.0.0.1:8688)"
  else
    echo "  🔴 面板不可达"
  fi
  echo "($up/4 个进程在跑)"
}

# 若指定了新网卡, 把 vnstat.conf 的 DatabaseDir 改成本机绝对路径
# (vnstat 不展开 $PWD, 必须绝对路径; 换机器时由本脚本自动修正)
fix_database_dir() {
  if [ -f "$ROOT/vnstat.conf" ]; then
    sed -i "s|^DatabaseDir .*|DatabaseDir \"$VDIR\"|" "$ROOT/vnstat.conf"
  fi
}

start_all() {
  local no_watchdog=0
  # 始终修正 DatabaseDir 为本机绝对路径, 避免跨机器时相对路径失效
  fix_database_dir
  if [ "${IFACE_OVERRIDE:-}" != "" ]; then
    echo ">>> 更新 vnstat.conf 网卡名为 $IFACE_OVERRIDE"
    sed -i "s|^Interface \"[^\"]*\"|Interface \"$IFACE_OVERRIDE\"|" "$ROOT/vnstat.conf"
  fi

  mkdir -p "$VDIR"

  # 1) vnstatd
  if ! pgrep -f "extracted/usr/sbin/vnstatd" >/dev/null 2>&1; then
    echo "启动 vnstatd..."
    nohup "$ROOT/extracted/usr/sbin/vnstatd" -n --config "$ROOT/vnstat.conf" \
      > "$ROOT/vnstatd.log" 2>&1 &
    sleep 2
  fi

  # 2) 采样器(读宿主 /proc 做按进程归因, 需能在 ss 里看到进程)
  if ! pgrep -f "python3.*monitor/sampler.py" >/dev/null 2>&1; then
    echo "启动采样器..."
    nohup "$PY" "$MONITOR/sampler.py" > "$MONITOR/sampler.log" 2>&1 &
    sleep 2
  fi

  # 3) 面板
  if ! pgrep -f "python3.*monitor/server.py" >/dev/null 2>&1; then
    echo "启动面板..."
    (cd "$MONITOR" && nohup "$PY" server.py 8688 > server.log 2>&1 &)
    sleep 2
  fi

  # 4) watchdog(可选)
  if [ "$no_watchdog" -eq 0 ]; then
    if ! pgrep -f "python3.*monitor/watchdog.py" >/dev/null 2>&1; then
      echo "启动 watchdog..."
      setsid bash -c "exec $PY '$MONITOR/watchdog.py'" \
        > "$MONITOR/watchdog.log" 2>&1 < /dev/null &
      sleep 2
    fi
  fi

  echo
  echo "=== 启动完成 ==="
  status_all
  echo
  echo "面板地址: http://127.0.0.1:8688"
  echo "查流量:   $ROOT/查询热点流量.sh 今日"
  echo
  echo "提示: 若要开机自启, 参考 README.md 第 4 节"
}

# ---- 解析参数 ----
MODE="start"
NO_WATCHDOG=0
IFACE_OVERRIDE=""
for arg in "$@"; do
  case "$arg" in
    --stop) MODE="stop" ;;
    --status) MODE="status" ;;
    --iface=*) IFACE_OVERRIDE="${arg#--iface=}" ;;
    --no-watchdog) NO_WATCHDOG=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "未知参数: $arg"; usage; exit 1 ;;
  esac
done

export IFACE_OVERRIDE
case "$MODE" in
  start)   start_all ;;
  stop)    stop_all ;;
  status)  status_all ;;
esac
