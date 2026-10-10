#!/usr/bin/env python3
"""热点流量实时监控面板 — 纯 Python 标准库实现,无第三方依赖。

数据来源:
  1. /proc/net/dev   -> 网卡累计计数器,两次采样求差得到实时速率
  2. vnstat --json    -> vnstatd 持久化的 5 分钟/小时/日/月历史统计

用法: python3 server.py [端口]   默认 8688
"""
import json
import os
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# 网卡名: 改成你自己的热点网卡 (ip link 查看, 手机热点通常是 wlan*/wlx* 开头)
IFACE = "wlx10a4bea81d3f"  # 手机热点网卡(按实际网卡名修改)
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VNSTAT = os.path.join(BASE, "extracted", "usr", "bin", "vnstat")
CONF = os.path.join(BASE, "vnstat.conf")
MONITOR_DIR = os.path.dirname(os.path.abspath(__file__))
PROC_STATS = os.path.join(MONITOR_DIR, "proc_stats.json")
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8688

# ---------- 实时速率:网卡计数器差分 ----------
_prev = {"t": None, "rx": 0, "tx": 0}
_vnstat_cache = {"t": 0.0, "data": None}


def read_proc_counters():
    """读取 /proc/net/dev 中目标网卡的 (rx_bytes, tx_bytes)。"""
    with open("/proc/net/dev", encoding="utf-8") as fh:
        for line in fh:
            parts = line.split()
            if parts and parts[0].rstrip(":") == IFACE:
                return int(parts[1]), int(parts[9])
    return 0, 0


def sample_rate():
    """采样一次并计算 B/s 速率(基于上次采样的时间差)。"""
    rx, tx = read_proc_counters()
    now = time.time()
    rx_bps = tx_bps = 0.0
    if _prev["t"] is not None:
        dt = now - _prev["t"]
        if dt > 0:
            # 计数器回退(网卡重连)时置 0,避免负值
            rx_bps = max(0.0, (rx - _prev["rx"]) / dt)
            tx_bps = max(0.0, (tx - _prev["tx"]) / dt)
    _prev.update(t=now, rx=rx, tx=tx)
    return round(rx_bps, 2), round(tx_bps, 2), rx, tx


def read_vnstat():
    """调用 vnstat 获取 JSON 历史数据(3 秒缓存,避免频繁拉起进程)。"""
    now = time.time()
    if _vnstat_cache["data"] is not None and now - _vnstat_cache["t"] < 3:
        return _vnstat_cache["data"]
    try:
        out = subprocess.run(
            [VNSTAT, "--config", CONF, "-i", IFACE, "--json"],
            capture_output=True, text=True, timeout=10,
        )
        data = json.loads(out.stdout)
        _vnstat_cache.update(t=now, data=data)
        return data
    except Exception as exc:  # vnstat 异常时面板仍可用,只是没有历史数据
        return {"error": str(exc)}


def read_proc_stats():
    """读取沙箱外采样器写出的按进程流量数据(文件超过 10 秒未更新视为停止)。"""
    try:
        age = time.time() - os.path.getmtime(PROC_STATS)
        with open(PROC_STATS, encoding="utf-8") as fh:
            data = json.load(fh)
        data["alive"] = age < 10
        data["age"] = round(age, 1)
        return data
    except Exception:
        return {"alive": False, "age": None, "procs": []}


def build_stats():
    rx_bps, tx_bps, rx_total, tx_total = sample_rate()
    vn = read_vnstat()
    iface = None
    if isinstance(vn, dict) and vn.get("interfaces"):
        iface = vn["interfaces"][0]
    return {
        "iface": IFACE,
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "rate": {"rx": rx_bps, "tx": tx_bps},
        "since_boot": {"rx": rx_total, "tx": tx_total},
        "vnstat": iface,
        "daemon_updated": iface.get("updated") if iface else None,
        "process": read_proc_stats(),
    }


# ---------- HTTP ----------
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.split("?")[0] == "/api/stats":
            body = json.dumps(build_stats(), ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
        elif self.path in ("/", "/index.html"):
            try:
                with open(os.path.join(MONITOR_DIR, "index.html"), "rb") as fh:
                    body = fh.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
            except FileNotFoundError:
                body = b"index.html not found"
                self.send_response(404)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
        else:
            body = b"not found"
            self.send_response(404)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):  # 静默默认访问日志
        pass


if __name__ == "__main__":
    ThreadingHTTPServer.allow_reuse_address = True   # 端口冲突时可立即重启,不等 TIME_WAIT
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"热点流量监控面板已启动: http://127.0.0.1:{PORT}  (接口 {IFACE})", flush=True)
    server.serve_forever()
