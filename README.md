# 免 root 热点流量监控

纯 Python + vnstat 的实时流量监控面板,无需 sudo 安装。

## 功能

- 📊 实时速率(网卡计数器差分,2 秒刷新)
- 📈 6 分钟实时曲线 + 5 分钟/小时柱状图
- 📅 按日/按月统计表格
- 🔍 **按进程归因**:走 `ss -tinp` 内核 socket 计数器,把 TCP 上行/下行字节按进程名累加
- 🛡️ watchdog 自愈:任何服务挂掉 15 秒内自动拉起

## 文件结构

```
vnstat-local/
├── vnstat.conf              # 配置(网卡名, 数据库路径)
├── setup.sh                # 一键安装/启动/停止/查看状态
├── 查询热点流量.sh          # 便捷查询脚本
├── monitor/
│   ├── server.py            # Web 面板(纯 stdlib, 8688 端口)
│   ├── index.html           # 前端(单文件, 无依赖)
│   ├── sampler.py           # 按进程采样器(读 ss -tinp, 必须沙箱外运行)
│   └── watchdog.py          # 守护进程(缺哪个服务拉哪个)
├── test/
│   └── test_core.py         # 冒烟测试(纯函数 + 数据契约)
├── .github/workflows/ci.yml # GitHub Actions CI
├── extracted/               # vnstat/vnstatd 二进制(免 root 安装)
└── tools/
    └── 截图.js              # Playwright 截图工具
```

## 使用

### 1. 修改网卡名

编辑 `vnstat.conf` 里的 `Interface "xxx"` 为你的热点网卡:

```bash
ip link | grep -i wlan    # 找到你的热点网卡名
```

> ⚠️ `DatabaseDir` 必须是**绝对路径**(vnstat 不展开 `$PWD` 变量,写成相对路径会让 vnstatd 起不来、面板今日/本月累计空白)。
> 换机器 clone 后不用手动改——直接跑 `./setup.sh` 会自动把 `DatabaseDir` 修正为当前机器的绝对路径。

### 2. 启动服务

**最简单:用一键脚本**

```bash
cd vnstat-local
./setup.sh                # 安装并启动 vnstatd + 采样器 + 面板 + watchdog
./setup.sh --status       # 查看状态
./setup.sh --stop         # 停止全部
./setup.sh --iface=wlan0 # 监控指定网卡
```

**或手动逐步启动**

```bash
cd vnstat-local

# 流量记录
nohup ./extracted/usr/sbin/vnstatd -n --config vnstat.conf > vnstatd.log 2>&1 &

# 采样器(必须在宿主终端, 不能在沙箱内)
nohup python3 monitor/sampler.py > monitor/sampler.log 2>&1 &

# Web 面板
cd monitor && nohup python3 server.py 8688 > server.log 2>&1 &

# watchdog(可选, 但推荐)
nohup python3 monitor/watchdog.py > monitor/watchdog.log 2>&1 &
```

### 3. 访问

打开 http://127.0.0.1:8688

### 4. 查询流量

```bash
./查询热点流量.sh 今日
./查询热点流量.sh 本月
```

## 按进程归因原理

走内核 socket 计数器(`ss -tinp`):

| 计数器 | 含义 |
|---|---|
| `bytes_acked` | 本端已确认的上行载荷字节(不含重传) |
| `bytes_received` | 本端接收的下行载荷字节 |

每 2 秒对同一 socket 的计数器做差分,按进程名累加。注意:

- 走本地代理(xray/v2rayN)的程序,socket 是"客户端→代理端口"的回环连接,按**客户端**归因
- 代理核心自己的外发连接跳过,避免重复计数
- 统计的是 TCP 载荷,不含协议头和重传,总和会略小于 vnstat

## 测试与 CI

```bash
python3 test/test_core.py   # 冒烟测试(不依赖网络/宿主 /proc)
```

GitHub Actions 在每次 push 时自动跑:
- 三个脚本的 Python 语法 + 两个 shell 脚本语法
- 冒烟测试(导入模块、常量契约、`read_proc_stats` 行为、watchdog 检测函数)
- 确认 `monitor/` 不引入第三方库(纯 stdlib)

## 系统重启后

三个自启动项(`vnstat-hotspot.desktop`、`hotspot-proc-sampler.desktop`、`hotspot-monitor-panel.desktop`)会自动拉起 vnstatd、sampler、server。sampler 启动时顺带拉起 watchdog,接管自愈。
