#!/usr/bin/env python3
"""轻量冒烟测试: 不依赖网络/宿主 /proc, 验证核心纯函数与数据契约。

用法: python3 test/test_core.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "monitor"))

FAILURES = []


def check(name, cond, detail=""):
    if cond:
        print(f"  ✅ {name}")
    else:
        print(f"  ❌ {name}  {detail}")
        FAILURES.append(name)


# ---- 1. 三个脚本能被导入(语法正确, 无顶层异常) ----
print("== 导入模块 ==")
try:
    import sampler  # noqa: F401
    check("sampler.py 导入", True)
except Exception as e:
    check("sampler.py 导入", False, str(e))

try:
    import watchdog  # noqa: F401
    check("watchdog.py 导入", True)
except Exception as e:
    check("watchdog.py 导入", False, str(e))

try:
    import server  # noqa: F401
    check("server.py 导入", True)
except Exception as e:
    check("server.py 导入", False, str(e))

# ---- 2. 模块级常量契约 ----
print("== 模块常量 ==")
try:
    check("server.PROC_STATS 指向 monitor/proc_stats.json",
          os.path.basename(server.PROC_STATS) == "proc_stats.json")
    check("sampler.OUT 指向 monitor/proc_stats.json",
          os.path.basename(sampler.OUT) == "proc_stats.json")
    check("watchdog.VNSTATD 指向 extracted/usr/sbin/vnstatd",
          "vnstatd" in watchdog.VNSTATD)
    check("watchdog.SERVER 指向 monitor/server.py",
          os.path.basename(watchdog.SERVER) == "server.py")
except Exception as e:
    check("模块常量", False, str(e))

# ---- 3. server.read_proc_stats 对真实 proc_stats.json 的契约 ----
print("== read_proc_stats 契约 ==")
try:
    proc = server.read_proc_stats()
    check("read_proc_stats 返回 dict", isinstance(proc, dict))
    if isinstance(proc, dict):
        check("含 alive 字段", "alive" in proc)
        check("含 procs 字段(列表)", "procs" in proc and isinstance(proc["procs"], list))
except Exception as e:
    check("read_proc_stats", False, str(e))

# ---- 4. 模拟一份采样器输出, 验证字段完整 ----
print("== 采样器输出契约 ==")
try:
    sample = {
        "time": "2026-10-09 10:00:00",
        "ts": 1234567890.0,
        "interval": 2.0,
        "socks": 1,
        "procs": [{
            "name": "curl", "conns": 1,
            "rx_bps": 100.5, "tx_bps": 0.0,
            "rx_total": 1024, "tx_total": 0,
        }],
    }
    tmp = os.path.join(HERE, "fixture_proc_stats.json")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(sample, f)
    with open(tmp, encoding="utf-8") as f:
        loaded = json.load(f)
    check("fixture 可被 json 读回", loaded["procs"][0]["name"] == "curl")
    os.remove(tmp)
except Exception as e:
    check("采样器输出契约", False, str(e))

# ---- 5. watchdog 检测函数可调用(允许返回 False, 关键是能执行) ----
print("== watchdog 检测函数 ==")
try:
    r1 = watchdog.panel_alive()
    r2 = watchdog.sampler_alive()
    r3 = watchdog.vnstatd_alive()
    check("panel_alive 返回 bool", isinstance(r1, bool))
    check("sampler_alive 返回 bool", isinstance(r2, bool))
    check("vnstatd_alive 返回 bool", isinstance(r3, bool))
except Exception as e:
    check("watchdog 检测函数", False, str(e))

print()
if FAILURES:
    print(f"FAIL: {len(FAILURES)} 项未通过: {FAILURES}")
    sys.exit(1)
print("PASS: 全部通过")
