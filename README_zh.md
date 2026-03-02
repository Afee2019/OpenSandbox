<div align="center">
  <img src="docs/assets/logo.svg" alt="OpenSandbox logo" width="150" />

  <h1>OpenSandbox</h1>

<p align="center">
  <a href="https://github.com/alibaba/OpenSandbox">
    <img src="https://img.shields.io/github/stars/alibaba/OpenSandbox.svg?style=social" alt="GitHub stars" />
  </a>
  <a href="https://deepwiki.com/alibaba/OpenSandbox">
    <img src="https://deepwiki.com/badge.svg" alt="Ask DeepWiki" />
  </a>
  <a href="https://www.apache.org/licenses/LICENSE-2.0.html">
    <img src="https://img.shields.io/github/license/alibaba/OpenSandbox.svg" alt="license" />
  </a>
  <a href="https://badge.fury.io/py/opensandbox">
    <img src="https://badge.fury.io/py/opensandbox.svg" alt="PyPI version" />
  </a>
  <a href="https://badge.fury.io/js/@alibaba-group%2Fopensandbox">
    <img src="https://badge.fury.io/js/@alibaba-group%2Fopensandbox.svg" alt="npm version" />
  </a>
  <a href="https://github.com/alibaba/OpenSandbox/actions">
    <img src="https://github.com/alibaba/OpenSandbox/actions/workflows/real-e2e.yml/badge.svg?branch=main" alt="E2E Status" />
  </a>
</p>

  <hr />
</div>

[English](README.md) | 中文

[文档](https://open-sandbox.ai/zh/) | [Documentation](https://open-sandbox.ai/)

OpenSandbox 是一个面向 AI 应用的**通用沙箱平台**，提供多语言 SDK、统一沙箱 API，以及 Docker/Kubernetes 运行时，适用于 Coding Agent、GUI Agent、Agent 评估、AI 代码执行、强化学习训练等场景。

## 功能特性

- **多语言 SDK**：提供 Python、Java/Kotlin、JavaScript/TypeScript、C#/.NET、Go（路线图）等多种语言的沙箱 SDK。
- **沙箱协议**：定义沙箱生命周期管理 API 和沙箱执行 API，支持扩展自定义沙箱运行时。
- **沙箱运行时**：内置支持 Docker 和[高性能 Kubernetes 运行时](./kubernetes)的生命周期管理，兼顾本地运行与大规模分布式调度。
- **沙箱环境**：内置命令执行、文件系统和代码解释器实现。示例涵盖 Coding Agent（如 Claude Code）、浏览器自动化（Chrome、Playwright）、桌面环境（VNC、VS Code）等场景。
- **网络策略**：统一的[入口网关](components/ingress)支持多种路由策略，并提供沙箱级[出口流量控制](components/egress)。

## 快速开始

### 前置要求

- Docker（本地运行必需）
- Python 3.10+（推荐用于示例和本地运行时）

### 第一步：安装并配置沙箱服务器

```bash
uv pip install opensandbox-server
opensandbox-server init-config ~/.sandbox.toml --example docker
```

> 如果希望从源码开发，可以克隆仓库：
>
> ```bash
> git clone https://github.com/alibaba/OpenSandbox.git
> cd OpenSandbox/server
> uv sync
> cp example.config.toml ~/.sandbox.toml  # 复制配置文件
> uv run python -m src.main               # 启动服务
> ```

### 第二步：启动沙箱服务器

```bash
opensandbox-server

# 查看帮助
opensandbox-server -h
```

服务器启动后默认监听 `http://0.0.0.0:8310`。健康检查：

```bash
curl http://localhost:8310/health
# {"status": "healthy"}
```

交互式 API 文档：
- **Swagger UI**：http://localhost:8310/docs
- **ReDoc**：http://localhost:8310/redoc

### 第三步：创建代码解释器并执行代码

安装代码解释器 SDK：

```bash
uv pip install opensandbox-code-interpreter
```

创建沙箱并执行代码：

```python
import asyncio
from datetime import timedelta

from code_interpreter import CodeInterpreter, SupportedLanguage
from opensandbox import Sandbox
from opensandbox.models import WriteEntry

async def main() -> None:
    # 1. 创建沙箱
    sandbox = await Sandbox.create(
        "opensandbox/code-interpreter:v1.0.1",
        entrypoint=["/opt/opensandbox/code-interpreter.sh"],
        env={"PYTHON_VERSION": "3.11"},
        timeout=timedelta(minutes=10),
    )

    async with sandbox:

        # 2. 执行 Shell 命令
        execution = await sandbox.commands.run("echo 'Hello OpenSandbox!'")
        print(execution.logs.stdout[0].text)

        # 3. 写入文件
        await sandbox.files.write_files([
            WriteEntry(path="/tmp/hello.txt", data="Hello World", mode=644)
        ])

        # 4. 读取文件
        content = await sandbox.files.read_file("/tmp/hello.txt")
        print(f"Content: {content}")  # Content: Hello World

        # 5. 创建代码解释器
        interpreter = await CodeInterpreter.create(sandbox)

        # 6. 执行 Python 代码（单次运行，直接指定语言）
        result = await interpreter.codes.run(
              """
                  import sys
                  print(sys.version)
                  result = 2 + 2
                  result
              """,
              language=SupportedLanguage.PYTHON,
        )

        print(result.result[0].text)       # 4
        print(result.logs.stdout[0].text)  # 3.11.14

    # 7. 清理沙箱
    await sandbox.kill()

if __name__ == "__main__":
    asyncio.run(main())
```

## 更多示例

OpenSandbox 提供丰富的示例，演示不同场景下的沙箱用法。所有示例代码位于 `examples/` 目录。

### 🎯 基础示例

- **[code-interpreter](examples/code-interpreter/README.md)** - 在沙箱中完整演示 Code Interpreter SDK 工作流。
- **[aio-sandbox](examples/aio-sandbox/README.md)** - 使用 OpenSandbox SDK 的一体化沙箱配置。
- **[agent-sandbox](examples/agent-sandbox/README.md)** - 通过 [kubernetes-sigs/agent-sandbox](https://github.com/kubernetes-sigs/agent-sandbox) 在 Kubernetes 上运行 OpenSandbox。

### 🤖 Coding Agent 集成

- **[claude-code](examples/claude-code/README.md)** - 在 OpenSandbox 中运行 Claude Code。
- **[gemini-cli](examples/gemini-cli/README.md)** - 在 OpenSandbox 中运行 Google Gemini CLI。
- **[codex-cli](examples/codex-cli/README.md)** - 在 OpenSandbox 中运行 OpenAI Codex CLI。
- **[kimi-cli](examples/kimi-cli/README.md)** - 在 OpenSandbox 中运行 [Kimi CLI](https://github.com/MoonshotAI/kimi-cli)（月之暗面）。
- **[iflow-cli](examples/iflow-cli/README.md)** - 在 OpenSandbox 中运行 iFLow CLI。
- **[langgraph](examples/langgraph/README.md)** - 使用 LangGraph 状态机工作流创建并运行沙箱任务（含故障重试）。
- **[google-adk](examples/google-adk/README.md)** - 使用 Google ADK Agent 通过 OpenSandbox 工具读写文件、执行命令。
- **[nullclaw](examples/nullclaw/README.md)** - 在沙箱内启动 [Nullclaw](https://github.com/nullclaw/nullclaw) Gateway。
- **[openclaw](examples/openclaw/README.md)** - 在沙箱内启动 OpenClaw Gateway。

### 🌐 浏览器与桌面环境

- **[chrome](examples/chrome/README.md)** - 带 VNC 和 DevTools 访问的无头 Chromium，用于自动化/调试。
- **[playwright](examples/playwright/README.md)** - Playwright + Chromium 无头爬取与测试示例。
- **[desktop](examples/desktop/README.md)** - 在沙箱中运行完整桌面环境，支持 VNC 访问。
- **[vscode](examples/vscode/README.md)** - 在沙箱内运行 code-server（VS Code Web），实现远程开发。

### 🧠 机器学习与训练

- **[rl-training](examples/rl-training/README.md)** - 在沙箱内进行 DQN CartPole 强化学习训练，支持检查点与摘要输出。

更多详情请参考 [examples](examples/README.md) 及各示例目录中的 README 文件。

## 项目结构

| 目录 | 说明 |
|------|------|
| [`sdks/`](sdks/) | 多语言 SDK（Python、Java/Kotlin、TypeScript/JavaScript、C#/.NET） |
| [`specs/`](specs/README.md) | OpenAPI 规范与生命周期规范 |
| [`server/`](server/README.md) | Python FastAPI 沙箱生命周期服务器 |
| [`kubernetes/`](kubernetes/README.md) | Kubernetes 部署与示例 |
| [`components/execd/`](components/execd/README.md) | 沙箱执行守护进程（命令与文件操作） |
| [`components/ingress/`](components/ingress/README.md) | 沙箱流量入口代理 |
| [`components/egress/`](components/egress/README.md) | 沙箱网络出口控制 |
| [`sandboxes/`](sandboxes/) | 运行时沙箱实现 |
| [`examples/`](examples/README.md) | 集成示例与使用场景 |
| [`oseps/`](oseps/README.md) | OpenSandbox 增强提案 |
| [`docs/`](docs/) | 架构与设计文档 |
| [`tests/`](tests/) | 跨组件 E2E 测试 |
| [`scripts/`](scripts/) | 开发与维护脚本 |

## 整体架构

OpenSandbox 采用四层架构设计：

```
┌──────────────────────────────────────────────────┐
│          SDKs 层（多语言客户端库）                │
│    Python · Java/Kotlin · TypeScript · C#/.NET   │
├──────────────────────────────────────────────────┤
│          Specs 层（OpenAPI 协议规范）             │
│   sandbox-lifecycle.yml · execd-api.yaml          │
├──────────────────────────────────────────────────┤
│          Runtime 层（FastAPI 控制平面）           │
│   生命周期管理 · Docker 运行时 · K8s 运行时       │
├──────────────────────────────────────────────────┤
│          Sandbox 实例层（运行中的容器）           │
│   execd 守护进程 · Jupyter 内核 · 用户进程        │
└──────────────────────────────────────────────────┘
```

### 沙箱生命周期状态

```
     create()
        │
        ▼
   ┌─────────┐
   │ Pending │────────────────────┐
   └────┬────┘                    │
        │ (provisioning)          │
        ▼                         │
   ┌─────────┐    pause()         │
   │ Running │───────────────┐    │
   └────┬────┘               │    │
        │      resume()      │    │
        │   ┌────────────────┘    │
        │   ▼                     │
        │ ┌────────┐              │
        ├─│ Paused │              │
        │ └────────┘              │
        │                         │
        │ delete() or expire()    │
        ▼                         │
   ┌──────────┐                   │
   │ Stopping │                   │
   └────┬─────┘                   │
        │                         │
        ├────────────────┬────────┘
        ▼                ▼
   ┌────────────┐   ┌────────┐
   │ Terminated │   │ Failed │
   └────────────┘   └────────┘
```

### execd 执行守护进程

execd 是一个基于 Go 的 HTTP 守护进程，在沙箱创建时自动注入到容器内，无需修改用户镜像：

```bash
# 容器启动序列
/opt/opensandbox/start.sh
  ↓
# 启动 Jupyter Server（支持多语言内核）
jupyter notebook --port=54321 --no-browser --ip=0.0.0.0
  ↓
# 启动 execd 守护进程
/opt/opensandbox/execd --jupyter-host=http://127.0.0.1:54321 --port=44772
  ↓
# 执行用户入口
exec "${USER_ENTRYPOINT[@]}"
```

execd 提供以下核心能力：

| 功能 | 说明 |
|------|------|
| 代码执行 | 通过 Jupyter 内核支持 Python、Java、JavaScript、TypeScript、Go、Bash |
| 命令执行 | Shell 命令执行，支持前台/后台模式及 SSE 实时流式输出 |
| 文件操作 | 完整的文件 CRUD（含分块上传/下载、glob 搜索、权限管理） |
| 系统指标 | CPU、内存、运行时间的实时监控与流式推送 |

### 代码执行流程

```
用户/SDK
  │ 1. 创建沙箱 & 获取 execd 端点
  ▼
CodeInterpreter SDK
  │ 2. POST /code/context（创建会话）
  │ 3. POST /code（执行代码）
  ▼
execd（执行 API）
  │ 4. 通过 WebSocket 连接 Jupyter Server
  ▼
Jupyter 内核（Python/Java/等）
  │ 5. 执行代码，流式返回输出事件
  ▼
execd → SSE 事件流 → SDK → 用户
```

## 服务器配置参考

### 配置文件

配置文件默认路径为 `~/.sandbox.toml`，通过以下命令生成模板：

```bash
opensandbox-server init-config ~/.sandbox.toml --example docker       # Docker 运行时
opensandbox-server init-config ~/.sandbox.toml --example k8s          # Kubernetes 运行时
opensandbox-server init-config ~/.sandbox.toml --example docker-zh    # Docker（国内镜像源）
```

### Docker 运行时（Host 网络模式）

```toml
[server]
host = "0.0.0.0"
port = 8310
log_level = "INFO"
api_key = "your-secret-api-key-change-this"

[runtime]
type = "docker"
execd_image = "opensandbox/execd:v1.0.6"

[docker]
network_mode = "host"  # 容器共享宿主机网络，同时只支持一个沙箱实例
```

### Docker 运行时（Bridge 网络模式）

```toml
[docker]
network_mode = "bridge"  # 独立容器网络
# host_ip = "host.docker.internal"  # 在 Docker Compose 内部运行时需要配置
```

### Kubernetes 运行时

Kubernetes 版本需要先在集群内部署 Sandbox Operator，参考 [kubernetes/](kubernetes/) 目录。

```toml
[runtime]
type = "kubernetes"
execd_image = "opensandbox/execd:v1.0.5"

[kubernetes]
kubeconfig_path = "~/.kube/config"
namespace = "opensandbox"
workload_provider = "batchsandbox"   # 或 "agent-sandbox"
informer_enabled = true
```

### 安全加固

```toml
[docker]
drop_capabilities = ["AUDIT_WRITE", "MKNOD", "NET_ADMIN", "NET_RAW", "SYS_ADMIN",
                     "SYS_MODULE", "SYS_PTRACE", "SYS_TIME", "SYS_TTY_CONFIG"]
no_new_privileges = true
apparmor_profile = ""    # 可设置为 "docker-default"（需 AppArmor 支持）
pids_limit = 512
seccomp_profile = ""
```

### 出口网络策略（Egress）

当沙箱创建请求包含 `networkPolicy` 时，必须配置 egress sidecar 镜像（仅支持 Docker bridge 模式）：

```toml
[egress]
image = "opensandbox/egress:v1.0.1"
```

创建沙箱时携带网络策略示例：

```json
{
  "image": {"uri": "python:3.11-slim"},
  "entrypoint": ["python", "-m", "http.server", "8000"],
  "timeout": 3600,
  "resourceLimits": {"cpu": "500m", "memory": "512Mi"},
  "networkPolicy": {
    "defaultAction": "deny",
    "egress": [
      {"action": "allow", "target": "pypi.org"},
      {"action": "allow", "target": "*.python.org"}
    ]
  }
}
```

### 配置参数速查

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `server.host` | string | `"0.0.0.0"` | 监听地址 |
| `server.port` | integer | `8310` | 监听端口 |
| `server.log_level` | string | `"INFO"` | 日志级别 |
| `server.api_key` | string | `null` | API 认证密钥（为空时禁用认证） |
| `runtime.type` | string | 必填 | `"docker"` 或 `"kubernetes"` |
| `runtime.execd_image` | string | 必填 | 包含 execd 二进制的容器镜像 |
| `docker.network_mode` | string | `"host"` | `"host"` 或 `"bridge"` |
| `egress.image` | string | 使用 networkPolicy 时必填 | egress sidecar 镜像 |

环境变量：

| 变量 | 说明 |
|------|------|
| `SANDBOX_CONFIG_PATH` | 覆盖配置文件路径 |
| `DOCKER_HOST` | Docker 守护进程 URL |
| `PENDING_FAILURE_TTL` | 失败 Pending 沙箱的 TTL（秒，默认 3600） |

## API 认证

API 认证仅在 `server.api_key` 非空时生效，通过请求头传递：

```bash
curl -H "OPEN-SANDBOX-API-KEY: your-secret-api-key" \
  http://localhost:8310/v1/sandboxes
```

`/health`、`/docs`、`/redoc` 端点无需认证。本地开发时可将 `api_key` 置空以禁用认证。

## REST API 参考

### 生命周期 API（`/v1`）

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/sandboxes` | 创建沙箱 |
| `GET` | `/sandboxes` | 列举沙箱（支持状态/元数据过滤与分页） |
| `GET` | `/sandboxes/{id}` | 查询沙箱详情 |
| `DELETE` | `/sandboxes/{id}` | 删除沙箱 |
| `POST` | `/sandboxes/{id}/pause` | 暂停沙箱（异步） |
| `POST` | `/sandboxes/{id}/resume` | 恢复沙箱 |
| `POST` | `/sandboxes/{id}/renew-expiration` | 续期沙箱 TTL |
| `GET` | `/sandboxes/{id}/endpoints/{port}` | 获取服务端口的访问端点 |

**创建沙箱示例：**

```bash
curl -X POST "http://localhost:8310/v1/sandboxes" \
  -H "OPEN-SANDBOX-API-KEY: your-secret-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "image": {"uri": "python:3.11-slim"},
    "entrypoint": ["python", "-m", "http.server", "8000"],
    "timeout": 3600,
    "resourceLimits": {"cpu": "500m", "memory": "512Mi"},
    "env": {"PYTHONUNBUFFERED": "1"},
    "metadata": {"team": "backend", "project": "api-testing"}
  }'
```

**获取 execd 端点（用于代码执行）：**

```bash
curl -H "OPEN-SANDBOX-API-KEY: your-secret-api-key" \
  http://localhost:8310/v1/sandboxes/{sandbox-id}/endpoints/44772
```

**通过服务器代理访问 Bridge 模式端点：**

```bash
curl -H "OPEN-SANDBOX-API-KEY: your-secret-api-key" \
  "http://localhost:8310/v1/sandboxes/{sandbox-id}/endpoints/44772?use_server_proxy=true"
```

### execd 执行 API

execd 内置于每个沙箱容器中，通过 `X-EXECD-ACCESS-TOKEN` 头进行认证。

| 类别 | 方法 | 路径 | 说明 |
|------|------|------|------|
| 健康检查 | `GET` | `/ping` | 服务健康检查 |
| 代码执行 | `POST` | `/code/context` | 创建代码执行上下文 |
| 代码执行 | `POST` | `/code` | 执行代码（SSE 流式输出） |
| 代码执行 | `DELETE` | `/code` | 中断代码执行 |
| 命令执行 | `POST` | `/command` | 执行 Shell 命令 |
| 命令执行 | `DELETE` | `/command` | 中断命令执行 |
| 命令执行 | `GET` | `/command/status/{session}` | 查询命令状态 |
| 命令执行 | `GET` | `/command/output/{session}` | 获取命令输出 |
| 文件操作 | `POST` | `/files/upload` | 上传文件 |
| 文件操作 | `GET` | `/files/download` | 下载文件（支持 Range 请求） |
| 文件操作 | `GET` | `/files/search` | 按 glob 模式搜索文件 |
| 文件操作 | `POST` | `/files/mv` | 移动/重命名文件 |
| 文件操作 | `DELETE` | `/files` | 删除文件 |
| 文件操作 | `POST` | `/files/permissions` | 修改文件权限 |
| 目录操作 | `POST` | `/directories` | 创建目录（mkdir -p 语义） |
| 目录操作 | `DELETE` | `/directories` | 递归删除目录 |
| 系统指标 | `GET` | `/metrics` | 获取系统资源指标快照 |
| 系统指标 | `GET` | `/metrics/watch` | 实时监控系统指标（SSE） |

SSE 事件类型：`init`、`status`、`stdout`、`stderr`、`result`、`execution_complete`、`execution_count`、`error`

## SDK 文档

### 沙箱基础 SDK（生命周期管理）

提供沙箱创建、管理、销毁以及命令执行、文件操作等能力。

| 语言 | 安装 | 文档 |
|------|------|------|
| Python | `uv pip install opensandbox` | [README](sdks/sandbox/python/README.md) |
| Java/Kotlin | Maven/Gradle 依赖 | [README](sdks/sandbox/kotlin/README.md) |
| JavaScript/TypeScript | `npm install @alibaba-group/opensandbox` | [README](sdks/sandbox/javascript/README.md) |
| C#/.NET | NuGet 包 | [README](sdks/sandbox/csharp/README.md) |

### 代码解释器 SDK

提供多语言代码执行、会话状态管理等能力，基于 Jupyter 内核协议。

| 语言 | 安装 | 文档 |
|------|------|------|
| Python | `uv pip install opensandbox-code-interpreter` | [README](sdks/code-interpreter/python/README.md) |
| Java/Kotlin | Maven/Gradle 依赖 | [README](sdks/code-interpreter/kotlin/README.md) |
| JavaScript/TypeScript | npm 包 | [README](sdks/code-interpreter/javascript/README.md) |
| C#/.NET | NuGet 包 | [README](sdks/code-interpreter/csharp/README.md) |

### SDK 核心能力

**Sandbox（生命周期）：**
- 异步/同步双 API（`Sandbox` / `SandboxSync`）
- TTL 管理与自动续期
- 资源配额（CPU、内存、GPU）
- 元数据与环境变量注入

**Filesystem（文件系统）：**
- 文件 CRUD（含批量操作）
- glob 模式文件搜索
- Unix 权限管理（owner/group/mode）
- 分块上传/下载

**Commands（命令执行）：**
- 前台/后台执行模式
- SSE 实时流式输出
- 进程中断支持
- 自定义工作目录

**CodeInterpreter（代码解释器）：**
- 支持 Python、Java、JavaScript、TypeScript、Go、Bash
- 会话状态跨次执行持久化
- 多种 MIME 类型展示数据（文本、HTML、图像）
- 执行中断与计时统计

## Kubernetes 高性能运行时

OpenSandbox 提供专为 AI 大规模推理和强化学习训练优化的 Kubernetes Controller。

### BatchSandbox 性能对比

与 Kubernetes SIG agent-sandbox 的沙箱分发吞吐量对比（交付 100 个沙箱总耗时）：

| 测试场景 | 总耗时（秒） |
|----------|-------------|
| SIG Agent-Sandbox（并发=1） | 76.35 |
| SIG Agent-Sandbox（并发=10） | 23.17 |
| BatchSandbox（并发=1） | **0.63** |

BatchSandbox 通过资源预热池实现 O(1) 沙箱分配，性能比标准实现快约 **100 倍**。

### 主要特性

- **资源池（Pool CR）**：维护预热资源池，支持配置最小/最大缓冲区和容量上限
- **批量沙箱（BatchSandbox CR）**：支持 replicas=1（单用户交互）和 replicas=N（批量高吞吐场景）
- **任务编排**：可选的进程级任务调度，支持异构任务分发（shardTaskPatches）
- **自动过期清理**：基于 TTL 的自动资源回收

详情参考 [kubernetes/](kubernetes/README.md)。

## 设计原则

- **协议优先（Protocol-First）**：所有交互由 OpenAPI 规范定义，组件间契约清晰，支持多语言实现和自定义运行时扩展。
- **关注点分离**：SDK 负责客户端抽象、Specs 定义协议、Runtime 管理编排、execd 实现沙箱内操作。
- **可扩展性**：可插拔运行时、自定义沙箱镜像、多语言 SDK、额外 Jupyter 内核均可自由扩展。
- **安全性**：API Key 认证、Token 认证执行操作、沙箱隔离、资源配额、网络隔离。
- **可观测性**：结构化状态转换日志、实时指标流、健康检查端点。

## 应用场景

| 场景 | 说明 | 相关示例 |
|------|------|----------|
| AI 代码生成与执行 | 在隔离环境中安全执行 AI 生成的代码 | [claude-code](examples/claude-code/)、[codex-cli](examples/codex-cli/) |
| 交互式编程环境 | 构建 Web 编程平台和 Notebook | [code-interpreter](examples/code-interpreter/) |
| 浏览器自动化与测试 | 无头浏览器自动化与视觉调试 | [chrome](examples/chrome/)、[playwright](examples/playwright/) |
| 远程开发环境 | 云端开发工作区 | [vscode](examples/vscode/)、[desktop](examples/desktop/) |
| 强化学习训练 | 大规模并行 RL 训练环境 | [rl-training](examples/rl-training/) |

## 文档

- [docs/architecture.md](docs/architecture.md) — 整体架构与设计理念
- [specs/README.md](specs/README.md) — 沙箱生命周期 API 与执行 API 的 OpenAPI 定义
- [server/README.md](server/README.md) — 服务器启动与配置（Docker 和 Kubernetes 运行时）
- [server/TROUBLESHOOTING.md](server/TROUBLESHOOTING.md) — 常见问题排查
- SDK 文档：见各 SDK 目录的 README

## 贡献指南

欢迎贡献！推荐流程：

1. Fork 本仓库
2. 创建特性分支（`git checkout -b feature/amazing-feature`）
3. 为新功能编写测试
4. 确保所有测试通过（`uv run pytest`）
5. 运行代码检查（`uv run ruff check`）
6. 提交清晰的 commit 信息
7. Push 到你的 Fork
8. 提交 Pull Request

**何时需要提交 OSEP（增强提案）？**

以下情况需要先通过 [OSEP 流程](oseps/README.md)：
- 引入新功能或重大增强
- 修改核心沙箱 API 或运行时行为
- 影响安全模型或隔离保证

小型 Bug 修复、文档更新和小型重构可直接提交 PR，无需 OSEP。

## 路线图

### SDK

- [ ] **Go SDK** — 支持沙箱生命周期管理、命令执行和文件操作的 Go 客户端 SDK。

### 沙箱运行时

- [ ] **持久化存储** — 沙箱可挂载持久化存储卷（参见 [提案 0003](oseps/0003-volume-and-volumebinding-support.md)）。
- [ ] **Ingress 多网络策略** — 入口网关支持多 Kubernetes 集群供应和多网络模式。
- [ ] **本地轻量沙箱** — 可直接在 PC 上运行 AI 工具的轻量级沙箱。

### 部署

- [ ] **Kubernetes Helm Chart** — 通过 Helm Chart 部署所有组件。

## 联系与讨论

- **Issues**：通过 GitHub Issues 提交 Bug、功能请求或设计讨论
- **Discussions**：使用 GitHub Discussions 进行问答与想法交流

## Star 历史

[![Star History Chart](https://api.star-history.com/svg?repos=alibaba/OpenSandbox&type=date&legend=top-left)](https://www.star-history.com/#alibaba/OpenSandbox&type=date&legend=top-left)

## 许可证

本项目基于 [Apache 2.0 License](LICENSE) 开源。
