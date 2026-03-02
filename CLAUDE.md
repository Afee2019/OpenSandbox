# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概览

OpenSandbox 是阿里巴巴开源的 AI 应用通用沙箱平台，支持多语言 SDK、统一沙箱 API，以及 Docker/Kubernetes 运行时。适用于 Coding Agent、GUI Agent、代码执行、RL 训练等场景。

## 仓库结构

这是一个 **Monorepo**，主要模块：

- `server/` — FastAPI 控制平面（Python），负责沙箱生命周期管理
- `components/execd/` — 执行守护进程（Go），注入到沙箱容器内，处理代码执行、命令、文件操作
- `components/ingress/` — 沙箱流量入口代理（Go）
- `components/egress/` — 出站网络控制（Go）
- `sdks/sandbox/` — 沙箱生命周期 SDK（Python、JavaScript、Kotlin、C#）
- `sdks/code-interpreter/` — 代码执行 SDK（多语言）
- `sdks/mcp/` — Model Context Protocol 集成
- `specs/` — OpenAPI 规范（`sandbox-lifecycle.yml`、`execd-api.yaml`）
- `kubernetes/` — Kubernetes Controller 和 Helm Chart
- `tests/` — E2E 测试（Python、JavaScript、Java、C#）
- `examples/` — 25+ 集成示例

## 常用命令

### Server（Python/FastAPI）

```bash
cd server

# 安装依赖
uv sync

# 源码启动
uv run python -m src.main

# 代码检查与格式化
uv run ruff check          # 检查
uv run ruff check --fix    # 自动修复
uv run ruff format         # 格式化

# 运行测试
uv run pytest
uv run pytest tests/test_docker_service.py::test_specific_function  # 单个测试
uv run pytest --cov=src --cov-report=html  # 带覆盖率
```

### Components（Go）

每个组件（execd、ingress、egress）各有独立的 Go 模块：

```bash
cd components/execd   # 或 ingress / egress

make fmt       # 格式化
make vet       # 静态检查 + go mod tidy
make test      # 单元测试（含覆盖率）
make build     # 构建二进制
make golint    # 运行 golangci-lint
```

### SDKs（JavaScript/TypeScript）

`sdks/` 目录是 pnpm monorepo，使用 pnpm 9+：

```bash
cd sdks
pnpm install
pnpm build:js   # 构建所有 JS SDK
pnpm lint:js    # 检查所有 JS SDK
pnpm clean:js   # 清理构建产物
```

### SDKs（Python）

```bash
cd sdks/sandbox/python   # 或 sdks/code-interpreter/python
make build
make test
make lint
```

## 架构与核心流程

### 分层架构

```
SDKs（多语言）
    ↓
OpenAPI 规范（specs/）
    ↓
Server 控制平面（FastAPI）+ Components 守护进程
    ↓
沙箱容器（Docker / Kubernetes）
```

### 沙箱生命周期状态

`Pending → Running → Paused → Stopping → Terminated / Failed`

Server 的 `server/src/services/docker.py`（Docker 运行时）和 `server/src/services/k8s/`（Kubernetes 运行时）实现具体调度逻辑。

### execd 执行守护进程

execd 被注入到每个沙箱容器内，提供：
- 多语言代码执行（Python、Java、Go、JS、Bash 等）
- Jupyter Kernel 管理（WebSocket 通信）
- SSE 实时流式输出
- 文件 CRUD（含分块上传/下载、glob 搜索）
- CPU / 内存 / 运行时间指标

### Kubernetes 优化

`kubernetes/` 中的 BatchSandbox 控制器通过预热池实现 O(1) 沙箱分配，比标准 SIG Agent-Sandbox 快 100 倍以上。

## 运行时配置

服务器配置文件默认路径 `~/.sandbox.toml`，通过以下命令生成模板：

```bash
opensandbox-server init-config ~/.sandbox.toml --example docker      # Docker 运行时
opensandbox-server init-config ~/.sandbox.toml --example kubernetes  # K8s 运行时
```

## API 规范

- `specs/sandbox-lifecycle.yml` — 沙箱创建/列表/查询/删除/暂停/恢复/续期/获取端点
- `specs/execd-api.yaml` — 代码执行/命令/文件操作/指标

SDK 客户端代码由 OpenAPI 规范自动生成，修改 API 时需先更新规范文件。

## 测试基础设施

- Server 单元测试：`server/tests/`，使用 pytest
- Go 组件测试：各 `components/*/` 目录，使用 `go test`
- E2E 测试：`tests/` 目录（Python、JavaScript、Java、C#）
- Smoke 测试：`server/smoke.sh`
- K8s E2E：`.github/workflows/sandbox-k8s-e2e.yml`

## 代码规范

- **Python**：ruff（检查 + 格式化）
- **Go**：gofmt + golangci-lint
- **TypeScript**：ESLint + TypeScript strict 模式
- Pre-commit hooks 配置见 `.pre-commit-config.yaml`
