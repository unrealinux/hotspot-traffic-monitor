#!/usr/bin/env python3
"""流量监控 watchdog —— 常驻守护,缺哪个服务就自动拉起哪个。

用法(宿主终端):
    setsid python3 monitor/watchdog.py > monitor/watchdog.log 2>&1 < /dev/null &

每 15 秒检查一次,三个目标:
  1. vnstatd        -> 流量记录(每 5 分钟持久化)
  2. sampler.py     -> 按进程归因(必须在沙箱外运行)
  3. server.py 8688 -> Web 面板

检测方式(刻意不依赖进程名,避免匹配到自己的 shell):
  - 面板:8688 端口是否处于 LISTEN 状态
  - 采样器:proc_stats.json 是否在 10 秒内被更新
  - vnstatd:pgrep -x vnstatd
"""
import os
import signal
import socket
import subprocess
import time

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(HERE)
VNSTATD = f"{BASE}/extracted/usr/sbin/vnstatd"
SAMPLER = f"{HERE}/sampler.py"
SERVER = f"{HERE}/server.py"
CONF = f"{BASE}/vnstat.conf"
PROC_STATS = f"{HERE}/proc_stats.json"
PORT = 8688
INTERVAL = 15


def panel_alive():
    """面板在线 = 8688 端口处于 LISTEN 状态。"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        s.connect(("127.0.0.1", PORT))
        s.close()
        return True
    except OSError:
        return False


def sampler_alive():
    """采样器在线 = proc_stats.json 在 10 秒内被更新过。"""
    try:
        return (time.time() - os.path.getmtime(PROC_STATS)) < 10
    except OSError:
        return False


def vnstatd_alive():
    """vnstatd 在线 = 存在名为 vnstatd 的进程。"""
    try:
        out = subprocess.run(
            ["pgrep", "-x", "vnstatd"], capture_output=True, text=True, timeout=5
        ).stdout
        return bool(out.strip())
    except Exception:
        return False


def launch(name, cmd, logpath):
    """用 os.fork + os.setsid 启动子进程,彻底脱离父会话。"""
    try:
        pid = os.fork()
        if pid > 0:
            print(f"[watchdog] 已启动 {name} (child pid={pid})", flush=True)
            return True
        # 子进程:脱离原会话,忽略会话退出信号
        os.setsid()
        os.umask(0o022)
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        signal.signal(signal.SIGPIPE, signal.SIG_IGN)
        try:
            fd = os.open(logpath, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
            os.dup2(fd, 1)
            os.dup2(fd, 2)
            os.close(fd)
            os.chdir(HERE)
            os.execvp("bash", ["bash", "-c", cmd])
        except Exception as exc:
            print(f"[watchdog] exec 失败: {exc}", flush=True)
            os._exit(127)
    except Exception as exc:
        print(f"[watchdog] 启动 {name} 失败: {exc}", flush=True)
        return False
    return True


def main():
    print(f"[watchdog] 守护进程启动 pid={os.getpid()} (每 {INTERVAL}s 检查)", flush=True)
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    signal.signal(signal.SIGPIPE, signal.SIG_IGN)
    while True:
        checks = [
            ("vnstatd", vnstatd_alive(),
             f"{VNSTATD} -n --config {CONF}", f"{BASE}/vnstatd.log"),
            ("sampler", sampler_alive(),
             f"python3 {SAMPLER}", f"{HERE}/sampler.log"),
            ("面板", panel_alive(),
             f"cd {HERE} && python3 {SERVER} {PORT}", f"{HERE}/server.log"),
        ]
        for name, alive, cmd, logpath in checks:
            if alive:
                continue
            print(f"[watchdog] {name} 已掉线,正在拉起…", flush=True)
            launch(name, cmd, logpath)
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()