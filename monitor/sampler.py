#!/usr/bin/env python3
"""免 root 的按进程流量采样器(必须在沙箱外运行才能读取宿主 /proc)。

原理:每 2 秒调用一次 ss -tinp/-uinp,读取每条 TCP/UDP 连接的内核累计
计数器(bytes_acked=上行载荷, bytes_received=下行载荷),对相邻两次采样
做差分,按进程(名字)累加,最后原子写入 proc_stats.json 供 Web 面板读取。

说明:
  - 只统计会消耗热点流量的连接:非回环、非 docker 网桥;
  - 走本地代理(xray/v2rayN 等)的程序按"客户端 → 代理端口"的回环跳归因,
    代理核心的外发连接跳过,避免重复计数;
  - 统计的是 TCP 载荷字节,不含 IP/TCP 头和重传,数值会略小于 vnstat;
  - 连接关闭时未采样的最后一小段增量会丢失(误差很小)。
"""
import json
import os
import re
import signal
import subprocess
import time

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "proc_stats.json")
INTERVAL = 2.0
WATCHDOG = os.path.join(HERE, "watchdog.py")
WATCHDOG_LOG = os.path.join(HERE, "watchdog.log")
WATCHDOG = os.path.join(HERE, "watchdog.py")

RE_ACKED = re.compile(r"bytes_acked:(\d+)")
RE_RECV = re.compile(r"bytes_received:(\d+)")
RE_SENT = re.compile(r"bytes_sent:(\d+)")
RE_USER = re.compile(r'users:\(\("([^"]+)",pid=(\d+)')

# 本地代理端口(v2rayN 默认 HTTP 10808 / SOCKS 10809 及常见替代端口)。
# 客户端 → 这些端口的回环连接代表"该进程经代理出去的真实流量",按客户端归因;
# 代理核心(xray 等)自己的外发 socket 整条排除,避免同一份流量被算两遍。
PROXY_PORTS = {"10808", "10809", "1080", "7890", "7891", "20171", "20172",
               "3128", "8118", "8888", "8889", "1081"}
PROXY_CORES = {"xray", "v2ray", "v2ray-core", "sing-box", "singbox", "clash",
               "mihomo", "trojan", "privoxy", "tinyproxy", "polipo",
               "ss-local", "sslocal", "gost", "microsocks"}


def sample():
    """抓取一次所有 TCP/UDP 连接的状态,返回 {socket_key: (up, down, name, pid)}。"""
    socks = {}
    for proto in ("-tinp", "-uinp"):
        try:
            out = subprocess.run(["ss", proto], capture_output=True, text=True,
                                 timeout=5).stdout
        except Exception:
            continue
        lines = out.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i]
            i += 1
            if not line or line.startswith("State") or line.startswith("Recv-Q"):
                continue
            parts = line.split()
            if len(parts) < 5:
                continue
            local, peer = parts[3], parts[4]
            laddr = local.split("%")[0].split(":")[0]
            is_loop = (local.startswith("127.") or local.startswith("[::1]")
                       or laddr in ("::1", "*") or laddr == "[")
            # docker 网桥流量不经过热点网卡
            if laddr.startswith("172.17.") or laddr.startswith("172.18."):
                continue
            # 回环连接只保留"客户端 → 本地代理端口"这一跳(其余回环与热点无关)
            peer_port = peer.rsplit(":", 1)[-1]
            is_proxy_hop = is_loop and peer_port in PROXY_PORTS
            if is_loop and not is_proxy_hop:
                continue
            # 详情行(以空白开头,可能缺失)
            detail = ""
            if i < len(lines) and lines[i][:1].isspace():
                detail = lines[i]
                i += 1
            m_acked = RE_ACKED.search(detail)
            m_recv = RE_RECV.search(detail)
            m_sent = RE_SENT.search(detail)
            if not (m_acked or m_recv or m_sent):
                continue
            m_user = RE_USER.search(line) or RE_USER.search(detail)
            if m_user:
                name, pid = m_user.group(1), m_user.group(2)
            else:
                name, pid = "未知进程", "?"
            # 代理核心的外发连接已被客户端的"→代理端口"回环归因过,这里跳过防重复
            if name.lower() in PROXY_CORES and not is_proxy_hop:
                continue
            up = int(m_acked.group(1)) if m_acked else int(m_sent.group(1)) if m_sent else 0
            down = int(m_recv.group(1)) if m_recv else 0
            key = (proto, local, peer)
            socks[key] = (up, down, name, pid)
    return socks


def ensure_watchdog():
    """启动时顺带拉起 watchdog 守护进程(若尚未运行)。

    用于系统重启场景:开机自启项先启动 sampler,再由 sampler 拉起 watchdog,
    watchdog 接管 vnstatd/sampler/面板三个服务的自愈。
    用 /proc 扫描判断 watchdog 是否已在运行,避免重复启动。
    """
    try:
        for entry in os.listdir("/proc"):
            if not entry.isdigit():
                continue
            if int(entry) == os.getpid():
                continue
            try:
                with open(f"/proc/{entry}/cmdline", "rb") as fh:
                    cmdline = fh.read().replace(b"\x00", b" ").decode("utf-8", "replace")
            except (OSError, PermissionError):
                continue
            if "watchdog.py" in cmdline:
                if "sampler.py" not in cmdline:  # 排除"正在启动sampler"的中间态
                    return   # 已有独立的 watchdog 在跑,跳过
    except OSError:
        pass

    # 没有 watchdog,用 fork + setsid 拉起,彻底脱离当前会话
    try:
        pid = os.fork()
        if pid > 0:
            print(f"已拉起 watchdog 守护 (child pid={pid})", flush=True)
            return
        # 子进程:脱离原会话
        os.setsid()
        os.umask(0o022)
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        signal.signal(signal.SIGPIPE, signal.SIG_IGN)
        fd = os.open(WATCHDOG_LOG, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
        os.dup2(fd, 1)
        os.dup2(fd, 2)
        os.close(fd)
        os.chdir(HERE)
        os.execvp("python3", ["python3", WATCHDOG])
    except Exception as exc:
        print(f"拉起 watchdog 失败: {exc}", flush=True)


def main():
    ensure_watchdog()
    prev = {}                       # key -> (up, down, name, pid)
    totals = {}                     # name -> [rx_total, tx_total]
    print(f"按进程流量采样器启动 -> {OUT} (每 {INTERVAL}s)", flush=True)
    while True:
        now = time.time()
        cur = sample()
        window = {}                 # name -> [rx_delta, tx_delta, conns]
        for key, (up, down, name, pid) in cur.items():
            old = prev.get(key)
            if old:                 # 同一条连接的两次计数差分
                du = max(0, up - old[0])
                dd = max(0, down - old[1])
            else:
                du = dd = 0
            w = window.setdefault(name, [0.0, 0.0, 0])
            w[0] += dd
            w[1] += du
            w[2] += 1
            t = totals.setdefault(name, [0, 0])
            t[0] += dd
            t[1] += du
        prev = {k: (v[0], v[1], v[2], v[3]) for k, v in cur.items()}

        procs = []
        seen = set()
        for name, (rx, tx, conns) in window.items():
            seen.add(name)
            t = totals.get(name, [0, 0])
            procs.append({
                "name": name,
                "conns": conns,
                "rx_bps": round(rx / INTERVAL, 2),
                "tx_bps": round(tx / INTERVAL, 2),
                "rx_total": t[0],
                "tx_total": t[1],
            })
        # 连接已关闭、但累计流量仍有参考价值的进程保留在榜单(实时速率记 0),
        # 否则下载一结束该进程就从表里消失,用户看不到"刚才谁耗的流量"。
        for name, t in totals.items():
            if name in seen or t[0] + t[1] < 1024 * 1024:  # 仅保留累计 ≥1 MiB
                continue
            procs.append({
                "name": name,
                "conns": 0,
                "rx_bps": 0.0,
                "tx_bps": 0.0,
                "rx_total": t[0],
                "tx_total": t[1],
            })
        procs.sort(key=lambda p: (p["rx_bps"] + p["tx_bps"],
                                  p["rx_total"] + p["tx_total"]), reverse=True)
        procs = procs[:20]
        payload = {
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "ts": now,
            "interval": INTERVAL,
            "socks": len(cur),
            "procs": procs,
        }
        tmp = OUT + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False)
        os.replace(tmp, OUT)
        time.sleep(max(0.5, INTERVAL - (time.time() - now)))


if __name__ == "__main__":
    main()
