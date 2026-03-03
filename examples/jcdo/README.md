# jcdo Gateway 示例

在 OpenSandbox 沙箱实例中启动 jcdo Gateway，并暴露 WebSocket 访问端点。脚本会轮询 Gateway，直到返回 HTTP 200，然后打印可访问地址和连接命令。

jcdo 是基于 [OpenClaw](https://github.com/openclaw/openclaw) 改造的多渠道 AI 网关平台，支持 Telegram、Discord、Slack、iMessage、LINE 等 40+ 消息渠道，以及代码执行沙箱、浏览器自动化等能力。

## 前置准备

### 1. 构建 jcdo 镜像

jcdo 是私有项目，需要在本地构建 Docker 镜像：

```shell
cd ~/dev/jcdo
docker build -t jcdo:local .
```

构建完成后验证：

```shell
docker images | grep jcdo
```

### 2. 确认 Docker 运行时可用

OpenSandbox Server 默认使用 `runtime.type = "docker"`，因此 **必须** 能访问可用的 Docker daemon。

- **Docker Desktop**：确保已启动，然后执行 `docker version` 验证。
- **Colima（macOS）**：先启动 (`colima start`)，再在启动 Server 前导出 socket：

```shell
export DOCKER_HOST="unix://${HOME}/.colima/default/docker.sock"
```

### 3. 启动 OpenSandbox Server

```shell
cd ~/dev/OpenSandbox/server
uv run opensandbox-server
```

另开一个终端验证：

```shell
curl http://localhost:8310/health
# 期望输出：{"status":"healthy"}
```

## 配置参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `SANDBOX_SERVER` | `http://localhost:8310` | OpenSandbox Server 地址 |
| `JCDO_IMAGE` | `jcdo:local` | jcdo Docker 镜像名 |
| `JCDO_GATEWAY_TOKEN` | `dummy-token-for-sandbox` | Gateway 认证 Token |
| Gateway 端口 | `8255` | jcdo WebSocket 网关端口 |
| 超时时间 | `3600s` | 沙箱最长存活时间 |

## 运行示例

在 OpenSandbox 仓库根目录运行：

```shell
# 可选：设置真实 token（建议生产环境使用）
export JCDO_GATEWAY_TOKEN="$(openssl rand -hex 32)"

# 运行示例
SANDBOX_DOMAIN="localhost:8310" uv run \
  --with opensandbox \
  --with requests \
  python examples/jcdo/main.py
```

预期输出类似：

```text
Creating jcdo sandbox with image=jcdo:local on OpenSandbox server http://localhost:8310...
[check] jcdo gateway ready after 8.3s
jcdo gateway started. WebSocket endpoint: ws://127.0.0.1:56123
Gateway token: dummy-token-for-sandbox
Connect with: jcdo connect ws://127.0.0.1:56123 --token dummy-token-for-sandbox
```

最后打印的地址（如 `127.0.0.1:56123`）就是沙箱中 jcdo Gateway 的 WebSocket 端点，使用打印的 `jcdo connect` 命令即可连接。

## 网络策略说明

示例中使用了网络隔离策略（默认拒绝所有出站流量），仅放行 `registry.npmjs.org`（用于运行时技能安装）。

如果 jcdo 需要访问特定 LLM API 或渠道服务，在 `main.py` 的 `network_policy.egress` 中按需添加规则：

```python
egress=[
    NetworkRule(action="allow", target="registry.npmjs.org"),
    NetworkRule(action="allow", target="api.anthropic.com"),   # Claude API
    NetworkRule(action="allow", target="api.openai.com"),      # OpenAI API
    NetworkRule(action="allow", target="api.telegram.org"),    # Telegram Bot API
],
```

## 参考

- [OpenClaw](https://github.com/openclaw/openclaw)（jcdo 上游项目）
- [OpenSandbox Python SDK](https://pypi.org/project/opensandbox/)
- [OpenSandbox 新手指南](../../notes/002-新手使用指南（macOS-Docker）.md)
