# 003 — jcdo 沙箱使用指南

本文档基于实际验证，记录如何通过 OpenSandbox 将 jcdo Gateway 运行在隔离沙箱中，以及这个沙箱能做什么、怎么用。

---

## 一、背景

jcdo 是基于 OpenClaw 改造的多渠道 AI 网关平台，支持 40+ 消息渠道、52+ 技能，内置代码执行、浏览器自动化、记忆系统等能力。

将 jcdo 运行在 OpenSandbox 沙箱中，意味着：

- jcdo Gateway 跑在一个隔离的 Docker 容器内
- 通过 OpenSandbox 的代理层暴露 WebSocket 端口
- 宿主机 LLM 配置（`~/.jcdo/jcdo.json`）以只读方式挂载到容器，沙箱启动时复制为可写副本
- 网络出站策略由 OpenSandbox 统一控制

---

## 二、前置条件

| 条件 | 验证方式 |
|------|---------|
| Docker Desktop 运行中 | `docker version` |
| jcdo 镜像已构建 | `docker images jcdo:local` |
| OpenSandbox Server 运行中 | `curl http://localhost:8310/health` |
| `~/.jcdo/jcdo.json` 存在 | `ls ~/.jcdo/jcdo.json` |

如果 jcdo 镜像未构建：

```bash
cd ~/dev/jcdo
docker build -t jcdo:local .   # 约 5~15 分钟，构建产物约 4.2GB
```

---

## 三、启动沙箱

在 OpenSandbox 仓库根目录执行：

```bash
cd ~/dev/OpenSandbox

SANDBOX_DOMAIN="localhost:8310" uv run \
  --with opensandbox --with requests \
  python examples/jcdo/main.py
```

成功后输出：

```text
正在创建 jcdo 沙箱，镜像=jcdo:local，OpenSandbox Server=http://localhost:8310...
配置来源：/Users/shawn/.jcdo/jcdo.json（只读挂载）
[检查] jcdo gateway 就绪，耗时 17.6s

jcdo gateway 已启动。
  WebSocket  ：ws://127.0.0.1:40274/proxy/8255
  Token      ：dummy-token-for-sandbox
  沙箱 ID    ：bd4b1036-33d0-416e-a1de-2152bf9b8575

连接方式：
  jcdo acp --url ws://127.0.0.1:40274/proxy/8255 --token dummy-token-for-sandbox
```

> **端口每次启动都会变化**（OpenSandbox 动态分配），以实际输出为准。

### 启动原理

```
main.py
  ↓ SandboxSync.create()
OpenSandbox Server（:8310）
  ↓ Docker API
jcdo 容器启动：
  sh -c "
    mkdir -p ~/.jcdo &&
    cp /jcdo-host/jcdo.json ~/.jcdo/jcdo.json &&    ← 复制配置（可写）
    cp -r /jcdo-workspace-host ~/.jcdo/workspace &&  ← 复制工作区（可写）
    node dist/index.js gateway --bind=lan --port 8255 --verbose
  "
  ↓ 健康检查轮询（HTTP GET port 8255，最多 30s）
WebSocket 端点通过 OpenSandbox 代理层暴露
```

---

## 四、能做什么

### 4.1 对话 LLM（已验证 ✅）

最直接的用法：进容器调用 jcdo agent，与配置好的 LLM 对话。

```bash
# 找到容器 ID
CONTAINER=$(docker ps -q --filter "ancestor=jcdo:local" | head -1)

# 发送消息
docker exec $CONTAINER node jcdo.mjs agent \
  --local \
  --session-id my-session \
  --message "帮我写一段读取 CSV 文件的 Python 代码"
```

实测输出（bailian/qwen3.5-plus，响应时间 ~3.5s）：

```text
你好，绍俊！🚀🤖🌱

有什么我可以帮你的吗？
```

**会话是有状态的**：同一个 `--session-id` 多次调用会保持上下文，可以连续对话。

```bash
# 第一轮
docker exec $CONTAINER node jcdo.mjs agent \
  --local --session-id chat-001 \
  --message "我想写一个 Python 爬虫"

# 第二轮（上下文延续）
docker exec $CONTAINER node jcdo.mjs agent \
  --local --session-id chat-001 \
  --message "帮我加上异步并发支持"
```

---

### 4.2 通过 WebSocket 远程控制（已验证 ✅）

从宿主机 jcdo CLI 直接连入沙箱 Gateway，进入完整的 jcdo 交互界面：

```bash
jcdo acp \
  --url ws://127.0.0.1:40274/proxy/8255 \
  --token dummy-token-for-sandbox
```

连接后可以：

- 发送消息给 Agent，实时流式接收回复
- 管理 session（列出、删除、切换）
- 触发技能（tavily 搜索、天气查询等）
- 查看 Gateway 状态

---

### 4.3 使用 Agent 内置工具（已验证 ✅）

沙箱内的 jcdo Agent 拥有完整工具集（共 22 个工具）：

| 工具 | 能力 |
|------|------|
| `exec` | 在沙箱内执行 Shell 命令 / 代码 |
| `read` / `write` / `edit` | 读写沙箱内的文件 |
| `web_search` | 调用 Brave Search API 搜索（需配置 apiKey） |
| `web_fetch` | 抓取网页内容 |
| `browser` | 控制 Chromium 浏览器（截图、点击、填表等） |
| `process` | 管理进程（启动、列出、停止） |
| `canvas` | 生成/编辑 HTML 画布（Agent 可视化输出） |
| `memory_search` / `memory_get` | 语义记忆检索（SQLite + 向量嵌入） |
| `cron` | 设置定时任务 |
| `message` | 通过渠道发送消息（Discord、Telegram 等） |
| `sessions_spawn` | 启动子 Agent 会话 |
| `tts` | 文字转语音 |

**示例：让 Agent 在沙箱内执行代码**

```bash
docker exec $CONTAINER node jcdo.mjs agent \
  --local --session-id code-test \
  --message "用 Python 计算斐波那契数列前 20 项并打印"
```

Agent 会调用 `exec` 工具在沙箱内运行 Python，把结果返回给你。

---

### 4.4 隔离测试新配置（核心价值）

这是沙箱最重要的用途：**在不影响本地环境的前提下，安全地测试任何配置变更**。

#### 测试新的 LLM Provider

在沙箱里测试接入新模型，不动本地 `~/.jcdo/jcdo.json`：

```python
# main.py 中传入临时覆盖配置
env={
    "JCDO_GATEWAY_TOKEN": token,
    "OPENAI_API_KEY": "sk-xxx",     # 注入新 provider 的 key
}
```

或者准备一份修改过的 `jcdo-test.json`，通过 entrypoint 复制：

```python
entrypoint=[
    "sh -c 'mkdir -p ~/.jcdo && "
    "cp /jcdo-host/jcdo-test.json ~/.jcdo/jcdo.json && "   # ← 用测试配置
    "node dist/index.js gateway --bind=lan --port 8255 --verbose'"
]
```

跑崩了、配置错了，沙箱销毁重建，本地分毫不影响。

#### 测试新 Skill

```python
volumes=[
    # 正式配置（只读）
    Volume(name="jcdo-config", host=Host(path=jcdo_config_dir),
           mountPath=READONLY_MOUNT_PATH, readOnly=True),
    # 把开发中的新 skill 挂进去
    Volume(name="new-skill",
           host=Host(path="/Users/shawn/dev/my-new-skill"),
           mountPath="/home/node/.jcdo/skills/my-new-skill",
           readOnly=False),   # 可写，方便在沙箱内迭代调试
],
```

---

### 4.5 多实例并行（A/B 模型对比）

同时运行多个 jcdo 沙箱，每个指向不同 LLM，对比响应质量：

```python
import threading

configs = [
    {"model": "bailian/qwen3.5-plus",    "port": None},
    {"model": "deepseek/deepseek-chat",   "port": None},
]

def start_sandbox(cfg):
    # 启动沙箱，注入不同的 primary model
    ...

threads = [threading.Thread(target=start_sandbox, args=(c,)) for c in configs]
for t in threads: t.start()
for t in threads: t.join()
```

OpenSandbox 会为每个沙箱分配独立端口，互不干扰。

---

### 4.6 安全执行不可信代码

jcdo Agent 内置 `exec` 工具可以执行任意 Shell 命令。在沙箱里运行，意味着：

- 代码在 Docker 容器内执行，与宿主机完全隔离
- 网络出站受 OpenSandbox 网络策略限制（默认拒绝所有出站）
- 容器销毁后不留痕迹

典型场景：AI Coding Agent 接收用户上传的代码并执行，结果返回给用户，宿主机零风险。

---

## 五、配置参数速查

### main.py 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `SANDBOX_SERVER` | `http://localhost:8310` | OpenSandbox Server 地址 |
| `JCDO_IMAGE` | `jcdo:local` | jcdo Docker 镜像 |
| `JCDO_GATEWAY_TOKEN` | `dummy-token-for-sandbox` | Gateway 认证 Token |

### 沙箱固定参数

| 参数 | 值 | 说明 |
|------|-----|------|
| Gateway 端口 | `8255` | 容器内监听端口 |
| 超时时间 | `3600s` | 沙箱最长存活（到期自动销毁） |
| 挂载：配置 | `~/.jcdo` → `/home/node/.jcdo-host`（只读） | |
| 挂载：工作区 | `~/.jcdo/workspace` → `/home/node/.jcdo-workspace-host`（只读） | |
| 网络出站 | `api.deepseek.com`、`dashscope.aliyuncs.com`、`registry.npmjs.org` | 其余默认拒绝 |

### 常用操作命令

```bash
# 启动沙箱
SANDBOX_DOMAIN="localhost:8310" uv run \
  --with opensandbox --with requests \
  python examples/jcdo/main.py

# 找到运行中的容器
CONTAINER=$(docker ps -q --filter "ancestor=jcdo:local" | head -1)

# 与 LLM 对话
docker exec $CONTAINER node jcdo.mjs agent \
  --local --session-id <session-id> \
  --message "<你的消息>"

# 连接 Gateway（交互式）
jcdo acp --url ws://127.0.0.1:<port>/proxy/8255 --token dummy-token-for-sandbox

# 查看所有运行中的沙箱
curl -s http://localhost:8310/v1/sandboxes | python3 -m json.tool

# 停止所有 jcdo 沙箱
docker stop $(docker ps -q --filter "ancestor=jcdo:local")
```

---

## 六、已知限制

| 限制 | 说明 |
|------|------|
| 工作区文件只读 | workspace 挂载后复制为容器内副本，容器内修改不会回写宿主机 |
| 沙箱超时 1 小时 | 到期自动销毁，session 历史丢失。如需持久化，在销毁前用 `docker exec` 导出 |
| 渠道（Discord/Telegram 等）未激活 | 沙箱内只挂载了 jcdo.json，渠道 token 有效，但渠道服务的网络出站域名需手动加入 egress 白名单 |
| 镜像体积大 | jcdo:local 约 4.2GB，首次构建耗时长 |
| 每次端口变化 | WebSocket 端口由 OpenSandbox 动态分配，脚本或工具集成时需从输出中解析 |

---

## 七、进阶方向

1. **持久化 session**：在 `volumes` 中增加一个可写的 session 目录挂载，让对话历史在沙箱重建后仍可恢复
2. **激活渠道**：在 `network_policy.egress` 中加入 `api.telegram.org`、`discord.com` 等，实现沙箱内真实渠道消息收发
3. **CI/CD 集成**：在 PR 流水线中自动起沙箱，跑 jcdo 集成测试，测完自动销毁
4. **多 Agent 编排**：通过 `sessions_spawn` 工具在沙箱内启动子 Agent，实现任务分解与并行处理
5. **K8s 部署**：将 `main.py` 中的 `ConnectionConfigSync(domain=...)` 指向 K8s 部署的 OpenSandbox Server，利用 BatchSandbox 预热池实现毫秒级沙箱分配

---

## 参考

- [`examples/jcdo/main.py`](../examples/jcdo/main.py) — 沙箱启动脚本
- [`examples/jcdo/README.md`](../examples/jcdo/README.md) — 快速上手
- [`001-项目价值与痛点分析.md`](001-项目价值与痛点分析.md) — OpenSandbox 项目背景
- [`002-新手使用指南（macOS-Docker）.md`](002-新手使用指南（macOS-Docker）.md) — OpenSandbox 环境搭建
- [jcdo 文档](https://docs.jcdo.ai/cli) — jcdo CLI 完整参考
