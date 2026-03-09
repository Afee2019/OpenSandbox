# 005 — jcdo 在 OpenSandbox 中运行可行性分析

> 分析日期：2026-03-09
> 分析依据：jcdo 源码（~/dev/jcdo/）、OpenSandbox 源码（~/dev/JcSandbox/）、已有 examples/jcdo/ 示例

---

## 一、结论：完全可行，且已有可工作的原型

**jcdo 已经能在 OpenSandbox 中运行。** 项目中已存在 `examples/jcdo/main.py` 示例脚本，经过验证可以：
- 在 OpenSandbox 沙箱内启动 jcdo Gateway
- 通过 WebSocket 从宿主机连入沙箱内的 Gateway
- 在沙箱内与 LLM 对话、执行代码、使用工具

`notes/003-jcdo沙箱使用指南.md` 中有详细的操作记录和验证结果。

本文档在此基础上，**深入分析 jcdo 的各项能力在 OpenSandbox 中的适配程度**，识别完美适配、需要调整、以及存在限制的场景。

---

## 二、jcdo 与 OpenSandbox 的技术匹配度

### 2.1 基础运行环境

| jcdo 需求 | OpenSandbox 支持 | 匹配度 |
|-----------|-----------------|--------|
| Node.js 22+ 运行时 | 任意 Docker 镜像，jcdo:local 基于 node:22-bookworm | 完美匹配 |
| 非 root 运行（node 用户） | OpenSandbox 支持自定义用户，jcdo 镜像已配置 `USER node` | 完美匹配 |
| 环境变量注入（TOKEN、API KEY 等） | `env={}` 参数支持任意 KV | 完美匹配 |
| 自定义 entrypoint | `entrypoint=[]` 参数 | 完美匹配 |
| 约 4.2GB 镜像 | 无镜像大小限制 | 完美匹配 |

### 2.2 网络

| jcdo 需求 | OpenSandbox 支持 | 匹配度 |
|-----------|-----------------|--------|
| 端口 8255（Gateway WebSocket） | `get_endpoint(port)` 动态暴露 | 完美匹配 |
| 出站访问 LLM API（deepseek、dashscope 等） | FQDN egress 白名单 | 完美匹配 |
| 出站访问搜索/工具 API（Brave、Tavily 等） | 按需添加 egress 规则 | 需手动配置 |
| 端口 8256（Bridge/UI） | 可额外暴露 | 完美匹配 |
| 端口 8266-8365（CDP 浏览器调试） | 可暴露，但端口范围较大 | 需评估 |

### 2.3 存储

| jcdo 需求 | OpenSandbox 支持 | 匹配度 |
|-----------|-----------------|--------|
| `~/.jcdo/jcdo.json` 配置文件 | Host Volume 只读挂载 + 容器内复制 | 完美匹配（已实现） |
| `~/.jcdo/workspace/` 工作区 | Host Volume 只读挂载 + 容器内复制 | 完美匹配（已实现） |
| Session 历史（JSONL 文件） | 容器内可写，沙箱销毁后丢失 | 部分匹配 |
| Memory 向量库（SQLite） | 容器内可写，沙箱销毁后丢失 | 部分匹配 |
| Cron 任务定义/历史 | 容器内可写，沙箱销毁后丢失 | 部分匹配 |

### 2.4 计算资源

| jcdo 需求 | OpenSandbox 支持 | 匹配度 |
|-----------|-----------------|--------|
| CPU（Agent 推理+消息路由） | `resourceLimits.cpu` 可配置 | 完美匹配 |
| 内存（Node.js + 可选 Playwright） | `resourceLimits.memory` 可配置 | 完美匹配 |
| 进程数（子进程 Bridge、Playwright 等） | `pids_limit` 默认 512，可调大 | 需调整 |

---

## 三、jcdo 核心能力在沙箱中的适配分析

### 3.1 已验证可用的能力

| 能力 | 沙箱内行为 | 验证状态 |
|------|-----------|---------|
| LLM 对话（Agent） | 通过 egress 白名单访问 LLM API，正常工作 | 已验证 |
| WebSocket 远程控制（acp） | 通过 OpenSandbox 端口代理暴露，宿主机 CLI 可连入 | 已验证 |
| 有状态 Session | 同一 session-id 多次调用保持上下文 | 已验证 |
| Agent 内置工具（exec/read/write/edit） | 在沙箱容器内执行，隔离安全 | 已验证 |
| 多实例并行（A/B 测试） | 每个沙箱独立端口，互不干扰 | 已验证 |

### 3.2 理论可用但需配置的能力

#### 消息渠道（Discord、Telegram、Signal 等）

jcdo 支持 40+ 消息渠道，在沙箱中运行需要：

1. **Egress 白名单扩展**：每个渠道需要对应的域名出口规则

```python
network_policy=NetworkPolicy(
    defaultAction="deny",
    egress=[
        # LLM APIs
        NetworkRule(action="allow", target="api.deepseek.com"),
        NetworkRule(action="allow", target="dashscope.aliyuncs.com"),
        # Discord
        NetworkRule(action="allow", target="*.discord.com"),
        NetworkRule(action="allow", target="*.discord.gg"),
        NetworkRule(action="allow", target="*.discordapp.com"),
        # Telegram
        NetworkRule(action="allow", target="api.telegram.org"),
        # Slack
        NetworkRule(action="allow", target="*.slack.com"),
        # Signal（需要额外的端口/协议支持）
        NetworkRule(action="allow", target="*.signal.org"),
    ],
)
```

2. **环境变量传入渠道凭证**：

```python
env={
    "JCDO_GATEWAY_TOKEN": token,
    "DISCORD_BOT_TOKEN": "...",
    "TELEGRAM_BOT_TOKEN": "...",
}
```

**评估**：技术上完全可行，只是需要根据实际使用的渠道逐个配置 egress 规则。OpenSandbox 的 FQDN 白名单在此场景下的价值非常明显——精确控制 jcdo 可以连哪些渠道。

#### 浏览器自动化（Playwright/Chromium）

jcdo 内置浏览器控制能力（68 个源文件），在沙箱中运行需要：

1. **使用带浏览器的镜像**：jcdo 项目已有 `Dockerfile.sandbox-browser`，包含 Chromium、VNC、noVNC
2. **增加资源配额**：Chromium 需要更多内存（建议 1Gi+）和更高 pids_limit
3. **暴露额外端口**：CDP（9222）、VNC（5900）、noVNC（6080）

```python
sandbox = SandboxSync.create(
    image="jcdo:sandbox-browser",  # 带浏览器的专用镜像
    env={"JCDO_GATEWAY_TOKEN": token},
    resource_limits={"memory": "2Gi", "cpu": "2"},
    # ...
)
# 暴露浏览器调试端口
cdp_endpoint = sandbox.get_endpoint(9222)
vnc_endpoint = sandbox.get_endpoint(6080)
```

**评估**：可行，但需要专门的镜像和更多资源。OpenSandbox 的 Chrome 和 Desktop 示例（`examples/chrome/`、`examples/desktop/`）提供了很好的参考模式。

#### Skill 系统（39 个内置 Skill）

jcdo 的 skill 体系（1password、github、notion、send-email 等）在沙箱中运行，每个 skill 有自己的外部依赖：

| Skill | 需要的 egress 规则 | 需要的凭证 |
|-------|-------------------|-----------|
| tavily-search | `api.tavily.com` | `TAVILY_API_KEY` |
| github | `api.github.com` | `GITHUB_TOKEN` |
| send-email | SMTP 服务器域名 | SMTP 凭证 |
| kb (知识库) | 本地 API 或内网地址 | API 密钥 |
| openai-image-gen | `api.openai.com` | `OPENAI_API_KEY` |
| weather | 天气 API 域名 | API 密钥 |

**评估**：每个 skill 都可以工作，只要添加对应的 egress 规则和凭证。这是一个渐进式的过程——先跑核心对话，需要哪个 skill 再开哪个出口。

#### Cron 定时任务

jcdo 支持 cron 定时任务（47 个源文件），在沙箱中：
- 短期沙箱（默认 1 小时 TTL）：cron 任务可以运行，但沙箱过期后丢失
- 长期场景：需要通过 `renew-expiration` API 延长沙箱生命周期，或将 cron 配置持久化到 Volume

**评估**：短期测试可用。长期运行需要配合 TTL 续期或外部持久化方案。

### 3.3 当前受限的能力

#### iMessage 渠道

iMessage 依赖 macOS 系统 API（AppleScript/Contacts Framework），**无法在 Linux 容器中运行**。这是 Docker 容器化的固有限制，与 OpenSandbox 无关。

**替代方案**：在沙箱外运行 iMessage bridge，通过 WebSocket 连入沙箱内的 Gateway。

#### 本地 LLM 推理（node-llama-cpp）

jcdo 可选依赖 node-llama-cpp 做本地 LLM 推理。在沙箱中：
- **CPU 推理**：可行，但速度慢，需要大量内存
- **GPU 推理**：OpenSandbox 支持 `resourceLimits.gpu`，但需要宿主机有 NVIDIA GPU + nvidia-container-toolkit

**评估**：一般不会在沙箱中跑本地推理，通过 API 调用云端 LLM 是更合理的方案。

#### mDNS/Bonjour 设备发现

jcdo 支持 mDNS 自动发现局域网设备，在沙箱的 bridge 网络中无法到达宿主机局域网。

**替代方案**：使用显式的 `--url` 参数连接，而非依赖自动发现。

#### Tailscale 网络

jcdo 支持 Tailscale VPN 绑定，在沙箱容器中需要额外的网络权限（`CAP_NET_ADMIN`），且与 OpenSandbox 的安全策略可能冲突。

**评估**：不建议在沙箱内使用 Tailscale。应在沙箱外的网络层处理。

---

## 四、架构模式对比

### 模式 A：jcdo 整体运行在沙箱中（当前实现）

```
宿主机
  └─ OpenSandbox Server (:8310)
       └─ jcdo 沙箱容器
            ├─ jcdo Gateway (:8255)
            ├─ Agent + Tools
            ├─ exec（代码执行在沙箱内）
            └─ Browser（如果使用浏览器镜像）
                     ↕ egress 白名单
                LLM API / 渠道 API / 工具 API
```

**优点**：
- 最简单的部署方式，一个沙箱包含一切
- jcdo Agent 的 `exec` 工具天然被沙箱隔离
- 网络出站统一控制
- 适合测试、开发、安全评估场景

**缺点**：
- 沙箱超时后所有状态丢失
- 渠道连接断开需要重建
- 镜像较大（4.2GB）

### 模式 B：jcdo 在宿主机运行，代码执行委托给 OpenSandbox

```
宿主机
  ├─ jcdo Gateway（本地运行）
  │    ├─ Agent + Tools
  │    ├─ 渠道连接（Discord/Telegram/...）
  │    └─ exec 工具 → 委托给 OpenSandbox
  └─ OpenSandbox Server (:8310)
       └─ 代码执行沙箱（轻量容器）
            └─ 执行用户代码，返回结果
```

**优点**：
- jcdo 本身不受沙箱生命周期限制
- 渠道连接稳定（在宿主机直接运行）
- session/memory 持久化正常
- 代码执行仍然被隔离

**缺点**：
- 需要 jcdo 集成 OpenSandbox SDK（目前未实现）
- 比模式 A 更复杂

### 模式 C：混合模式

```
宿主机
  ├─ jcdo Gateway（本地运行）
  │    ├─ 渠道连接
  │    └─ sandbox.docker 配置 → 使用 jcdo 自带的 Docker 沙箱
  └─ OpenSandbox Server（可选）
       └─ 为 jcdo 提供更高级的沙箱能力
```

**关键发现**：jcdo 项目本身已内置 Docker 沙箱能力（`src/config/types.sandbox.ts`），包括：
- `SandboxDockerSettings`：容器镜像、工作目录、只读根文件系统、网络模式、用户、capability drop、资源限制、seccomp/AppArmor 等
- `SandboxBrowserSettings`：独立的浏览器沙箱容器

这意味着 jcdo 的 `exec` 工具已经可以在独立的 Docker 容器中执行代码，而不需要依赖 OpenSandbox。

**但 OpenSandbox 提供了 jcdo 自带沙箱所没有的能力**：
- FQDN 域名级网络策略（jcdo 只有基础的 Docker 网络模式）
- Kubernetes 大规模调度（BatchSandbox）
- gVisor/Kata 安全运行时
- 统一的生命周期管理 API
- execd 注入（给任意镜像加上代码执行能力）

---

## 五、推荐方案与实施路径

### 第一阶段：沿用现有模式 A（已完成）

当前 `examples/jcdo/main.py` 已经工作，适合以下场景：
- 安全地测试新 LLM provider 配置
- 安全地测试新 skill 开发
- A/B 模型对比
- 演示和教学

**可以立即优化的点**：

1. **Session 持久化**：添加可写 Volume 挂载 session 目录

```python
Volume(
    name="jcdo-sessions",
    host=Host(path=str(Path.home() / ".jcdo-sandbox-sessions")),
    mountPath="/home/node/.jcdo/agents",
    readOnly=False,
),
```

2. **Memory 持久化**：挂载 SQLite 向量库目录

```python
Volume(
    name="jcdo-memory",
    host=Host(path=str(Path.home() / ".jcdo-sandbox-memory")),
    mountPath="/home/node/.jcdo/memory",
    readOnly=False,
),
```

3. **动态 egress 规则**：根据 jcdo.json 中配置的 LLM provider 自动生成 egress 白名单

### 第二阶段：探索模式 B（未来方向）

如果需要长期稳定运行 jcdo 并集成 OpenSandbox 的代码执行能力：

1. 在 jcdo 的 `sandbox.docker` 配置中支持 OpenSandbox 后端
2. jcdo Agent 的 `exec` 工具调用 OpenSandbox SDK 创建临时沙箱执行代码
3. 主 Gateway 在宿主机运行，保持渠道稳定和数据持久化

这需要在 jcdo 侧开发 OpenSandbox 集成适配器，工作量较大但价值最高。

---

## 六、兼容性矩阵总览

| jcdo 功能 | 模式 A（整体沙箱） | 模式 B（exec 委托） | 模式 C（jcdo 自带沙箱） |
|-----------|-------------------|-------------------|----------------------|
| LLM 对话 | 可用 | 可用 | 可用 |
| WebSocket 控制 | 可用 | 可用 | 可用 |
| exec 代码执行 | 可用（沙箱内） | 可用（二级沙箱） | 可用（Docker 容器） |
| 浏览器自动化 | 需专用镜像 | 可用 | 可用（独立容器） |
| Discord/Telegram | 需 egress 配置 | 可用 | 可用 |
| iMessage | 不可用 | 可用 | 可用 |
| Signal | 需 egress 配置 | 可用 | 可用 |
| Session 持久化 | 需 Volume 挂载 | 原生可用 | 原生可用 |
| Memory 向量库 | 需 Volume 挂载 | 原生可用 | 原生可用 |
| Cron 任务 | 受 TTL 限制 | 原生可用 | 原生可用 |
| Skill 系统 | 需逐个配 egress | 原生可用 | 原生可用 |
| FQDN 网络策略 | 完整支持 | 二级沙箱支持 | 不支持 |
| gVisor/Kata 隔离 | 支持 | 二级沙箱支持 | 不支持 |
| K8s 大规模调度 | 支持 | 支持 | 不支持 |

---

## 七、核心结论

1. **jcdo 在 OpenSandbox 中运行是完全可行的**，且已有可工作的原型代码（`examples/jcdo/main.py`）。

2. **最适合的场景**是开发测试、安全评估、配置隔离验证、多实例 A/B 对比——这些正是沙箱的核心价值。

3. **长期生产运行**（如 24/7 渠道消息服务）不太适合模式 A，因为沙箱有 TTL 限制且渠道连接不稳定。此场景推荐模式 B 或模式 C。

4. **OpenSandbox 相比 jcdo 自带沙箱的独特价值**在于 FQDN 网络策略、gVisor/Kata 安全隔离、Kubernetes 大规模调度。如果不需要这些企业级能力，jcdo 自带的 Docker 沙箱已经够用。

5. **两者的最佳组合**是：jcdo 主 Gateway 在宿主机或 K8s Pod 中长期运行，代码执行能力通过 OpenSandbox 提供隔离沙箱，兼顾稳定性和安全性。

---

## 参考文档

- [`examples/jcdo/main.py`](../examples/jcdo/main.py) — 现有沙箱启动脚本
- [`notes/003-jcdo沙箱使用指南.md`](003-jcdo沙箱使用指南.md) — 实操验证记录
- jcdo `src/config/types.sandbox.ts` — jcdo 内置沙箱配置类型
- jcdo `Dockerfile` / `Dockerfile.sandbox` / `Dockerfile.sandbox-browser` — 三种镜像定义
- jcdo `docker-compose.yml` — Docker Compose 部署参考
