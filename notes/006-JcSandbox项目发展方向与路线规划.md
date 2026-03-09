# 006 — JcSandbox 项目发展方向与路线规划

> 日期：2026-03-09
> 前置：019（多Bot协同路线图）、020（军团架构蓝图）、021（Synapse协议）、022（K8s对标分析）、005（可行性分析）
> 定位：本项目（JcSandbox）的战略方向文档，明确"下一步做什么、为什么做、怎么做"

---

## 一、形势判断：JcSandbox 是整个军团体系的瓶颈

从四份文档中提炼出一个清晰的现状：

```
JCLink 平台:        ████████████████████░░  ~90%   ← 就绪
jcdo Synapse 适配:   ██████████████████░░░░  ~90%   ← 就绪
jcmdm 业务集成:      ██████████████░░░░░░░░  ~65%   ← 在建
JcSandbox:          ████░░░░░░░░░░░░░░░░░░  ~20%   ← 瓶颈
```

**通信协议（Synapse）就绪了，执行单元（jcdo）就绪了，但编排能力几乎为零。**

当前状态：
- OpenSandbox 上游平台可用（沙箱 CRUD、Docker/K8s 运行时、网络隔离、健康检查）
- `examples/jcdo/main.py` 可以手动拉起单个 jcdo 沙箱
- 没有声明式状态管理、没有调谐循环、没有批量编排、没有自愈

用 022 文档的类比：**Bot 编排处于 K8s v0.4 阶段——Bot 能跑、能通信、能协作，但"编排"还在手动挡。**

---

## 二、战略定位：从"沙箱平台"到"Bot 编排器"

### JcSandbox 不只是 OpenSandbox 的使用者

如果只是用 OpenSandbox 跑 jcdo，`examples/jcdo/main.py` 已经够了。JcSandbox 的真正价值在于在 OpenSandbox 之上构建 **Bot 军团的编排控制面**——类比 K8s 的 Controller Manager。

### 核心定位

```
OpenSandbox    →  容器运行时（类比 containerd）
JcSandbox      →  编排控制器（类比 kube-controller-manager）
JCLink         →  通信网络 + 状态存储（类比 Pod Network + etcd）
jcdo           →  工作负载（类比 Pod）
```

### 核心能力目标

| 能力 | 一句话描述 |
|------|-----------|
| **声明式管理** | 定义"我要 3 个翻译 Bot 始终在线"，而不是手动拉起 3 个容器 |
| **调谐循环** | 持续检测实际状态与期望状态的差异，自动修复 |
| **健康监控** | 三级探针（启动/就绪/存活），区分"活着"和"能干活" |
| **配置分发** | 从模板自动生成每个 jcdo 实例的差异化配置 |
| **弹性伸缩** | 根据任务负载自动增减 Bot 实例（远期） |

---

## 三、架构设计

### 3.1 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│  JcSandbox 编排控制器                                         │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │ Fleet Config  │  │ Reconciler   │  │ Health       │       │
│  │ Parser        │  │ (调谐循环)    │  │ Monitor      │       │
│  │              │  │              │  │              │       │
│  │ 读取军团配置  │→│ 对比期望/实际  │←│ 采集探针数据  │       │
│  │ 验证合法性    │  │ 创建/销毁实例  │  │ 更新实例状态  │       │
│  │ 生成实例配置  │  │ 替换故障实例   │  │ 触发告警      │       │
│  └──────────────┘  └──────┬───────┘  └──────────────┘       │
│                           │                                   │
│  ┌────────────────────────┴──────────────────────────────┐   │
│  │              OpenSandbox Client (SDK)                   │   │
│  │  SandboxSync.create() / .delete() / .get_endpoint()    │   │
│  └────────────────────────┬──────────────────────────────┘   │
│                           │                                   │
└───────────────────────────┼───────────────────────────────────┘
                            │  REST API
                            ▼
┌───────────────────────────────────────────────────────────────┐
│  OpenSandbox Server (:8310)                                    │
│  沙箱 CRUD / Docker Runtime / 网络策略 / 健康检查              │
└───────────────────────────┬───────────────────────────────────┘
                            │  Docker API
                            ▼
┌──────────┐  ┌──────────┐  ┌──────────┐
│ jcdo #1  │  │ jcdo #2  │  │ jcdo #N  │
│ 编码专家  │  │ 数据分析  │  │ 通用助手  │
└──────┬───┘  └──────┬───┘  └──────┬───┘
       │             │             │
       └─────────────┼─────────────┘
                     │  WebSocket
                     ▼
              ┌──────────────┐
              │   JCLink     │
              │   Server     │
              └──────────────┘
```

### 3.2 数据流

```
1. 管理员定义 fleet.yaml（军团配置）
2. JcSandbox 解析配置，生成每个 Bot 实例的 jcdo.json
3. JcSandbox 调用 OpenSandbox API 创建沙箱
4. 沙箱内 jcdo 启动，连接 JCLink
5. JcSandbox 持续监控：
   a. OpenSandbox 层：容器存活、资源使用
   b. jcdo 层：HTTP /health 端点
   c. JCLink 层：WebSocket 连接状态（远期）
6. 检测到异常 → 销毁旧实例 → 创建新实例（保留 Bot Token）
```

---

## 四、Fleet 配置格式设计

### 4.1 fleet.yaml — 军团声明文件

这是整个编排系统的输入，类比 K8s 的 Deployment YAML。

```yaml
# fleet.yaml — jcdo Bot 军团声明
apiVersion: jcsandbox/v1
kind: Fleet

# 全局默认值
defaults:
  image: jcdo:local
  timeout: 3600              # 沙箱 TTL（秒）
  sandbox_server: http://localhost:8310
  jclink_base_url: http://101.200.166.189:8306

# 网络策略模板
network_policies:
  base_llm:
    defaultAction: deny
    egress:
      - { action: allow, target: "api.deepseek.com" }
      - { action: allow, target: "dashscope.aliyuncs.com" }
      - { action: allow, target: "api.anthropic.com" }

  with_jclink:
    extends: base_llm
    egress:
      - { action: allow, target: "101.200.166.189" }   # JCLink

  with_tools:
    extends: with_jclink
    egress:
      - { action: allow, target: "api.tavily.com" }
      - { action: allow, target: "api.github.com" }
      - { action: allow, target: "*.npmjs.org" }

# Bot 部署声明
deployments:
  - name: coding-expert
    replicas: 1
    network_policy: with_tools
    template:
      agent:
        id: coding-expert
        model: claude-opus-4-6
        identity: { name: "编码专家" }
        skills: [coding-agent, github]
        tools:
          exec: { enabled: true }
          browser: { enabled: false }
      jclink:
        token: "${JCLINK_BOT_TOKEN_CODER}"    # 从环境变量注入
        group_policy: open

  - name: data-analyst
    replicas: 1
    network_policy: with_jclink
    template:
      agent:
        id: data-analyst
        model: deepseek/deepseek-chat
        identity: { name: "数据分析师" }
        skills: [jcmdm, kb]
      jclink:
        token: "${JCLINK_BOT_TOKEN_DATA}"
        group_policy: open

  - name: general-assistant
    replicas: 2                               # 两个副本
    network_policy: with_tools
    template:
      agent:
        id: general
        model: claude-sonnet-4-6
        identity: { name: "通用助手" }
        skills: [weather, greeting, tavily-search]
      jclink:
        token: "${JCLINK_BOT_TOKEN_GENERAL}"  # 多副本共享 Token?
        group_policy: open

# 健康检查配置
health:
  startup_timeout: 60        # 启动超时（秒）
  check_interval: 30         # 检查间隔（秒）
  liveness_failures: 3       # 连续失败 N 次判定死亡
  readiness_endpoint: /health
```

### 4.2 关键设计问题

#### 多副本的 Bot Token 问题

K8s 的 Pod 没有身份问题，但 jcdo 的每个实例需要一个唯一的 JCLink Bot Token。多副本有两种策略：

| 策略 | 说明 | 适用场景 |
|------|------|---------|
| **共享身份** | 多个实例用同一个 Bot Token，JCLink 需要支持同一 Bot 的多连接负载均衡 | 简单，但需要 JCLink 侧改造 |
| **独立身份** | 每个实例一个独立的 Bot Token，fleet.yaml 列出 token 列表 | 无需改造，但管理复杂 |
| **自动注册** | JcSandbox 拉起实例时自动在 JCLink 创建 Bot 并获取 Token | 最优雅，需要 JCLink 提供 Bot 创建 API |

**推荐**：短期用独立身份（token 列表），中期实现自动注册。

#### 配置生成

从 fleet.yaml 的 `template` 生成每个实例的 `jcdo.json`：

```
fleet.yaml.deployments[i].template
    ↓ 合并 defaults
    ↓ 解析环境变量 ${VAR}
    ↓ 生成 jcdo.json 结构
    ↓ 写入临时文件
    ↓ 通过 Volume 挂载到沙箱
```

---

## 五、分阶段实施路线

### Phase 1：基础编排 — "自动挡"（最高优先级）

> 目标：从"手动拉起单个沙箱"到"声明式管理 N 个沙箱并自愈"
> 预期工作量：5-8 天

#### 1.1 Fleet Config 解析器

```
输入：fleet.yaml
输出：每个 deployment 的实例化参数列表
功能：
  - YAML 解析 + JSON Schema 验证
  - 环境变量 ${VAR} 替换
  - network_policy 继承 (extends)
  - defaults 合并
  - jcdo.json 模板生成
```

**产出文件**：`orchestrator/config.py`

#### 1.2 调谐循环（Reconciliation Loop）

```python
# 伪代码
class Reconciler:
    def __init__(self, fleet_config, sandbox_client):
        self.desired = fleet_config.deployments
        self.client = sandbox_client

    async def reconcile(self):
        for deployment in self.desired:
            actual = await self.list_instances(deployment.name)
            healthy = [i for i in actual if i.healthy]

            # 扩容
            if len(actual) < deployment.replicas:
                await self.scale_up(deployment, deployment.replicas - len(actual))

            # 替换不健康实例
            for instance in actual:
                if not instance.healthy and self.should_replace(instance):
                    await self.replace(deployment, instance)

            # 缩容（仅当超出期望副本数时）
            if len(actual) > deployment.replicas:
                await self.scale_down(deployment, actual, len(actual) - deployment.replicas)

    async def run(self, interval=30):
        while True:
            try:
                await self.reconcile()
            except Exception as e:
                logger.error(f"Reconciliation failed: {e}")
            await asyncio.sleep(interval)
```

**关键设计**：
- 幂等性：多次调谐结果相同
- 容错性：单次调谐失败不影响下次
- 实例跟踪：用 sandbox metadata 记录 deployment 归属

**产出文件**：`orchestrator/reconciler.py`

#### 1.3 健康监控

```python
class HealthMonitor:
    async def check_instance(self, instance) -> HealthStatus:
        # 1. 容器存活（通过 OpenSandbox API 查询沙箱状态）
        sandbox = await self.client.get(instance.sandbox_id)
        if sandbox.status != "Running":
            return HealthStatus.DEAD

        # 2. jcdo 就绪（HTTP GET /health）
        try:
            endpoint = await sandbox.get_endpoint(8255)
            resp = await httpx.get(f"http://{endpoint.endpoint}/health", timeout=5)
            if resp.status_code == 200:
                return HealthStatus.READY
            return HealthStatus.NOT_READY
        except Exception:
            return HealthStatus.NOT_READY

    async def check_all(self, instances):
        for inst in instances:
            status = await self.check_instance(inst)
            inst.health = status
            inst.last_check = datetime.now()
            if status == HealthStatus.DEAD:
                inst.consecutive_failures += 1
            else:
                inst.consecutive_failures = 0
```

**产出文件**：`orchestrator/health.py`

#### 1.4 CLI 入口

```bash
# 启动军团
jcsandbox up fleet.yaml

# 查看状态
jcsandbox status

# 缩放
jcsandbox scale coding-expert --replicas=2

# 停止
jcsandbox down
```

**产出文件**：`orchestrator/cli.py`

#### Phase 1 产出物

```
orchestrator/
├── __init__.py
├── cli.py              # CLI 入口（typer）
├── config.py           # Fleet 配置解析
├── reconciler.py       # 调谐循环
├── health.py           # 健康监控
├── instance.py         # 实例状态模型
└── jcdo_config.py      # jcdo.json 生成器

fleet.yaml.example      # 示例配置
```

---

### Phase 2：智能调度 + 可观测性

> 目标：从"能自愈"到"能看懂运行状态"
> 依赖：Phase 1 完成

#### 2.1 状态看板（Terminal UI）

```
╔══════════════════════════════════════════════════════════╗
║  JcSandbox Fleet Status       uptime: 2h 15m            ║
╠══════════════════════════════════════════════════════════╣
║  DEPLOYMENT        DESIRED  ACTUAL  READY  STATUS       ║
║  coding-expert          1       1      1   ✅ Healthy   ║
║  data-analyst           1       1      1   ✅ Healthy   ║
║  general-assistant      2       2      1   ⚠️ Degraded  ║
╠══════════════════════════════════════════════════════════╣
║  INSTANCES                                               ║
║  coding-expert-0      Ready    2h15m  sandbox:abc123     ║
║  data-analyst-0       Ready    2h15m  sandbox:def456     ║
║  general-assistant-0  Ready    2h15m  sandbox:ghi789     ║
║  general-assistant-1  Starting 0m12s  sandbox:jkl012     ║
╠══════════════════════════════════════════════════════════╣
║  EVENTS (last 10)                                        ║
║  14:30:02  general-assistant-1  Health check failed      ║
║  14:30:05  general-assistant-1  Replacing instance       ║
║  14:30:18  general-assistant-1  New instance starting    ║
╚══════════════════════════════════════════════════════════╝
```

#### 2.2 日志聚合

从每个沙箱容器收集 stdout/stderr，统一格式化输出：

```
[coding-expert-0]      2026-03-09 14:30:00 INFO  Gateway started on :8255
[data-analyst-0]       2026-03-09 14:30:01 INFO  Connected to JCLink
[general-assistant-0]  2026-03-09 14:30:02 WARN  AI call timeout, retrying...
```

#### 2.3 与 JCLink 集成（可选）

如果选择把 BotDeployment 状态存到 JCLink 数据库：

- JCLink 新增 `bot_deployments` + `bot_instances` 表
- JcSandbox 通过 JCLink Bot API 读写 deployment 状态
- JCLink 前端新增"Bot 管理"面板

**或者**保持简单：状态存在 JcSandbox 本地（SQLite 或 JSON 文件），fleet.yaml 就是 single source of truth。

**推荐**：Phase 2 用本地状态文件，Phase 3 再考虑 JCLink 集成。

---

### Phase 3：弹性伸缩 + 高级运维

> 目标：从"手动声明副本数"到"系统自动调整"
> 依赖：Phase 2 完成 + JCLink 指标 API

#### 3.1 自动伸缩

基于 JCLink 的 `bot_task_metrics` 物化视图数据，自动调整副本数：

```yaml
# fleet.yaml 中的伸缩策略
autoscaler:
  enabled: true
  min_replicas: 1
  max_replicas: 5
  metrics:
    - type: task_queue_depth
      target: 3              # 每 Bot 不超过 3 个排队任务
  scale_up:
    stabilization: 60s
    cooldown: 120s
  scale_down:
    stabilization: 300s
    cooldown: 300s
```

#### 3.2 滚动更新

```bash
# 更新镜像版本
jcsandbox rolling-update coding-expert --image jcdo:v2.0

# 过程：逐个替换实例，确保始终有 N-1 个可用
```

#### 3.3 配置热更新

```bash
# 修改 fleet.yaml 后
jcsandbox apply fleet.yaml

# 检测配置变化，仅重建受影响的实例
```

---

## 六、技术选型

### 语言与框架

| 组件 | 选型 | 理由 |
|------|------|------|
| 编排控制器 | **Python** (asyncio) | 与 OpenSandbox Server 同栈，可直接使用 opensandbox SDK |
| CLI | **typer** | Python CLI 框架，自动生成帮助信息 |
| 配置解析 | **pydantic** + **PyYAML** | 类型安全的配置验证 |
| HTTP 客户端 | **httpx** (async) | 健康检查、JCLink API 调用 |
| 状态存储 | **JSON 文件** (Phase 1) → **SQLite** (Phase 2) | 先简单后升级 |
| 日志 | **structlog** | 结构化日志 |

### 依赖关系

```
JcSandbox orchestrator
  ├── opensandbox SDK (Python)     ← 沙箱管理
  ├── httpx                        ← HTTP 健康检查
  ├── pydantic                     ← 配置验证
  ├── PyYAML                       ← fleet.yaml 解析
  ├── typer                        ← CLI
  └── structlog                    ← 日志
```

---

## 七、与现有代码的关系

### 已有内容保留

| 文件 | 作用 | 处理 |
|------|------|------|
| `examples/jcdo/main.py` | 单实例沙箱启动示例 | 保留，作为最简用法参考 |
| `notes/003-jcdo沙箱使用指南.md` | 操作手册 | 保留，作为基础操作参考 |
| `notes/005-可行性分析.md` | jcdo 适配度分析 | 保留，作为能力参考 |

### 新增内容

```
orchestrator/           ← 新增：编排控制器模块
  ├── __init__.py
  ├── cli.py
  ├── config.py
  ├── reconciler.py
  ├── health.py
  ├── instance.py
  └── jcdo_config.py
fleet.yaml.example      ← 新增：军团配置示例
pyproject.toml           ← 新增或修改：添加 orchestrator 依赖
```

### 不修改上游代码

OpenSandbox 上游代码不做修改，编排层作为独立模块存在，仅通过 SDK API 与 OpenSandbox 交互。

---

## 八、里程碑与验收标准

### M1：单 Deployment 调谐（Phase 1 核心）

**验收场景**：
1. 编写 fleet.yaml，声明 1 个 coding-expert（replicas=1）
2. 执行 `jcsandbox up fleet.yaml`
3. 自动创建沙箱，jcdo 启动，连接 JCLink
4. 手动 `docker kill` 该容器
5. 30 秒内，JcSandbox 检测到异常，自动拉起新实例
6. 新实例正常工作

### M2：多 Deployment 军团（Phase 1 完成）

**验收场景**：
1. fleet.yaml 声明 3 个 Deployment（编码专家×1、数据分析×1、通用助手×2）
2. 执行 `jcsandbox up fleet.yaml`
3. 4 个沙箱全部启动，各自连接 JCLink
4. 在 JCLink 频道中 `@编码专家 帮我问一下 @数据分析师 现有数据源情况`
5. Synapse 协议完整流程走通：委派 → 接收 → 执行 → 回报 → 整合
6. kill 任意一个容器，30 秒内自愈

### M3：看板 + 日志（Phase 2 核心）

**验收场景**：
1. `jcsandbox status` 显示所有实例状态表格
2. `jcsandbox logs --follow` 实时聚合输出所有实例日志
3. 实例替换事件在看板中可见

---

## 九、风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| OpenSandbox 沙箱 TTL 到期 | Bot 被自动销毁 | 调谐循环自动续期（`renew-expiration` API） |
| jcdo 镜像 4.2GB，创建慢 | 自愈响应时间长 | 预拉取镜像 + 本地缓存 |
| 多副本 Bot Token 管理复杂 | 手动配置易出错 | Phase 2 实现自动注册 |
| JCLink 单点故障 | 所有 Bot 断连 | 短期接受，长期 JCLink 高可用 |
| 调谐循环异常退出 | 失去自愈能力 | 自身 watchdog + systemd/supervisor 守护 |

---

## 十、总结

### 一句话定位

> **JcSandbox 的下一步是构建 Bot 编排控制器——声明式管理 jcdo 实例的生命周期，使 AI Bot 军团从"手动挡"切换到"自动挡"。**

### 为什么现在做

- Synapse 协议 94% 就绪，jcdo 适配 90% 就绪——协同能力已经具备
- 缺的不是通信能力，而是"谁来拉起和管理这些 Bot"
- 022 文档明确指出：BotDeployment + 调谐循环 + 健康探针是从"工具"到"平台"的分水岭

### 做完 Phase 1 能得到什么

一条命令拉起 5 个 jcdo Bot 军团，任意一个挂了自动恢复，管理员不需要盯着。这就是编排的最小可用形态——也是整个军团体系从"Demo"到"可用"的临门一脚。

---

## 参考文档

| 文档 | 与本文关系 |
|------|----------|
| [019-多Bot协同路线图](../../jclink/notes/019-jcdo分身模式-多Bot协同实施路线图.md) | jcdo 侧协同能力已就绪，等待编排 |
| [020-军团架构蓝图](../../jclink/notes/020-军团架构蓝图-JCLink-jcdo-JcSandbox-jcmdm协同体系.md) | JcSandbox 在军团中的定位和待建设能力 |
| [021-Synapse协议](../../jclink/notes/021-Synapse协议-Bot间协同通信协议完整规范.md) | Bot 间通信协议，编排层需要感知 |
| [022-K8s对标分析](../../jclink/notes/022-Bot编排体系与K8s对标分析-差距识别与演进路线.md) | 编排设计的参考框架 |
| [003-jcdo沙箱使用指南](003-jcdo沙箱使用指南.md) | 单实例操作参考 |
| [005-可行性分析](005-jcdo在OpenSandbox中运行可行性分析.md) | jcdo 在沙箱中的适配度 |
