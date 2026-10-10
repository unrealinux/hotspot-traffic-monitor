#!/usr/bin/env bash
# 查询手机热点网卡(按实际网卡名修改) (wlx10a4bea81d3f) 的流量消耗
# 用法: ./查询热点流量.sh [今日|本月|5分钟|小时|全部]
DIR="$(cd "$(dirname "$0")" && pwd)"
VNSTAT="$DIR/extracted/usr/bin/vnstat"
CONF="$DIR/vnstat.conf"

case "${1:-今日}" in
  今日|day)    "$VNSTAT" --config "$CONF" -i wlx10a4bea81d3f -d ;;
  本月|month)  "$VNSTAT" --config "$CONF" -i wlx10a4bea81d3f -m ;;
  5分钟|5min)  "$VNSTAT" --config "$CONF" -i wlx10a4bea81d3f -5 ;;
  小时|hour)   "$VNSTAT" --config "$CONF" -i wlx10a4bea81d3f -h ;;
  实时|live)   "$VNSTAT" --config "$CONF" -i wlx10a4bea81d3f -l ;;
  全部|all)    "$VNSTAT" --config "$CONF" -i wlx10a4bea81d3f ;;
  JSON|json)   "$VNSTAT" --config "$CONF" -i wlx10a4bea81d3f --json ;;
  *) echo "用法: $0 [今日|本月|5分钟|小时|实时|全部|JSON]"; exit 1 ;;
esac
