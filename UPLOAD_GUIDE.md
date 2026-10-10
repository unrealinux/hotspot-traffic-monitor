# 上传 GitHub 操作指引(无需凭据)

## 方式 A:网页直接传包(推荐,零风险)

1. 浏览器打开:https://github.com/unrealinux/hotspot-traffic-monitor
2. 点页面上的 **Add file → Upload an existing file**
3. 把下面这个文件拖进去:

   ```
   ~/文档/deepseek-harness/default-workspace/hotspot-traffic-monitor.tar.gz   (533K)
   ```

4. 点 **Commit changes**,完成。

上传后仓库里会多一个 `.tar.gz` 文件,克隆下来 `tar xzf` 解开即可使用。
如果嫌仓库里留个 tar 包碍眼,传完可以再加个 `.gitattributes` 或手动删掉它(网页 Delete 就行)。

## 方式 B:git 推(需要你自己操作,不要给 AI 发 token)

GitHub 已停用密码登录,必须用 Personal Access Token 或 SSH key。

**B1. HTTPS + PAT(在 GitHub 网页生成 token,勾选 repo 权限)**

在你自己的终端里执行(token 只在你本机输入,不经过 AI/聊天):

```bash
cd ~/文档/deepseek-harness/default-workspace/vnstat-local

# 起好 xray 代理后
export https_proxy=http://127.0.0.1:10808
export http_proxy=http://127.0.0.1:10808

# 交互式推送,弹出 Username 时填 GitHub 用户名,Password 栏填 PAT
git push -u origin main

# 推完立刻清掉代理和可能的缓存凭据
unset https_proxy http_proxy
git config --unset credential.helper || true
```

**B2. SSH key(一劳永逸,之后不用再带 token)**

```bash
# 本机可能已有 SSH key
ls ~/.ssh/id_*.pub 2>/dev/null || ssh-keygen -t ed25519 -C "hotspot-monitor" -N ""
# 把公钥内容加到 GitHub: Settings → SSH and GPG keys → New SSH key
cat ~/.ssh/id_ed25519.pub

# 改 remote 为 SSH
git remote set-url origin git@github.com:unrealinux/hotspot-traffic-monitor.git
# 起好能连 22 端口的代理(SSH 走代理可用: ssh -J 跳板 或 ProxyCommand)
git push -u origin main
```

## 安全原则

- PAT 等价于账号密码,**只在你本机终端输入,不要发给任何人/AI/聊天框**
- 用完可立即在 GitHub 网页 Revoke 该 token
- 如果不小心发过,立即 Revoke 重新生成
