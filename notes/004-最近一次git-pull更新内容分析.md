# OpenSandbox 最近一次 Git Pull 更新内容分析

> 分析日期：2026-03-08
> 更新范围：`450072f..cc3ea28`（从上游 alibaba/main 合并）
> 非合并提交数：47 个
> 涉及文件：98 个，净增 **4426 行**，删除 433 行

---

## 一、更新概览

本次 pull 是从 alibaba/OpenSandbox 上游仓库同步的一次大版本合并，涵盖了**安全容器运行时支持、Kubernetes Helm 部署体系完善、Server 可观测性增强、多项 Bug 修复与文档改进**等内容。以下按功能领域分类梳理。

---

## 二、重大新特性（Features）

### 2.1 安全容器运行时支持（Secure Container Runtime）

**核心提交：**
- `a64513c` feat(server): add secure container runtime support for docker and kubernetes
- `4b8bd44` feat(secure-container): add gVisor and Kata RuntimeClass support with e2e tests
- `3dd62d9` fix(config): enforce secure_runtime.type 'firecracker' compatibility

**变更内容：**

这是本次更新中**最大的新特性**，新增了对 gVisor 和 Kata Containers 两种安全容器运行时的完整支持。

| 模块 | 变更 |
|------|------|
| `server/src/services/runtime_resolver.py` | **新增文件（255 行）**，实现 `SecureRuntimeResolver` 类，负责将 `secure_runtime` 配置翻译为 Docker OCI runtime 或 K8s RuntimeClass 参数 |
| `server/src/config.py` | 新增 `SecureRuntimeConfig` 配置模型，支持 `gvisor`、`kata`、`firecracker` 三种类型 |
| `server/src/services/docker.py` | 集成安全运行时，创建沙箱容器时可传入 `--runtime runsc` 等参数 |
| `server/src/services/k8s/agent_sandbox_provider.py` | K8s 沙箱创建时注入 `runtimeClassName` |
| `server/src/services/k8s/batchsandbox_provider.py` | BatchSandbox 同样支持安全运行时 |
| `server/src/services/k8s/client.py` | 新增 RuntimeClass API 查询能力 |
| `docs/secure-container.md` | **新增 743 行文档**，完整的安全容器部署指南 |
| `oseps/0004-secure-container-runtime.md` | OSEP 提案文档增加 162 行详细设计说明 |

**架构设计要点：**
- `SecureRuntimeResolver` 通过默认映射表将 `gvisor` → Docker `runsc` / K8s `gvisor` RuntimeClass
- 支持自定义 `docker_runtime` 和 `k8s_runtime_class` 覆盖默认值
- 服务器启动时校验运行时可用性（Docker 检查 runtime 列表，K8s 检查 RuntimeClass 资源）

### 2.2 X-Request-ID 请求追踪中间件

**核心提交：** `7425d71` feat(server): span `X-Request-ID` by server log

**变更内容：**

| 文件 | 说明 |
|------|------|
| `server/src/middleware/request_id.py` | **新增文件（76 行）**，基于 `contextvars` 的请求 ID 中间件 |
| `server/src/main.py` | 注册 `RequestIdMiddleware`，置于中间件链最外层 |
| `server/src/api/lifecycle.py` | API 路由层适配 |

**技术细节：**
- 从请求头 `X-Request-ID` 读取或自动生成 UUID
- 使用 Python `contextvars.ContextVar` 存储，异步上下文安全
- `RequestIdFilter` 日志过滤器注入 `%(request_id)s`，实现全链路日志关联
- 响应头回传 `X-Request-ID`，便于客户端侧追踪

### 2.3 Server EIP 配置支持

**核心提交：** `99aed71` feat(server): add server.eip config for endpoint host in Docker runtime

新增 `server.eip` 配置项，允许在 Docker 运行时下指定沙箱端点的外部主机地址（弹性 IP），解决了沙箱在云环境中外部访问的地址映射问题。同时新增了 `TROUBLESHOOTING.md`（中英双语）文档。

### 2.4 UID/GID 指针化与补充用户组

**核心提交：** `cb899f9` Refactor UID/GID to pointers and add support for supplemental groups

在 execd 的命令执行层（`components/execd/pkg/runtime/`），将 UID/GID 字段从值类型重构为指针类型，并新增 supplemental groups 支持，使沙箱内进程权限控制更加精细。

---

## 三、Kubernetes 部署体系完善

### 3.1 Helm Chart 体系

| 提交 | 内容 |
|------|------|
| `9f37514` | **新增 `opensandbox-server` Helm Chart**（642 行），包含 Deployment、Ingress Gateway、辅助模板 |
| `afe79c7` | **新增 `opensandbox` 聚合 Chart**（all-in-one），通过 `Chart.yaml` 依赖管理一键部署 |
| `f4fc881` / `f55e0ac` | 更新 Controller Helm 模板，修复 args、values 配置 |
| `c306c8f` | 修复 Chart values 中错误的 server 版本号 |

### 3.2 DNS-1035 资源名称规范化

**核心提交：** `5ee0480` fix: normalize sandbox resource names to DNS-1035 (issue #318)

- 解决 UUID 形式的沙箱 ID（以数字开头）导致 K8s 资源名不合法的问题
- 在 Server 和 Ingress 两侧都实现了 DNS-1035 名称清洗（sanitizer）
- 保留向后兼容的查找回退链：sanitized name → raw name → legacy name

### 3.3 创建超时与 Init Container 资源限制

**核心提交：** `e388b7a` fix: create timeout; init container resource

- `server/src/config.py` 新增沙箱创建超时配置
- Agent/BatchSandbox Provider 支持 init container 资源限制
- 新增大量测试覆盖

### 3.4 其他 K8s 改进

| 提交 | 内容 |
|------|------|
| `d1eed94` | 对不支持的 `image.auth` 返回明确错误信息而非静默失败 |
| `cd6c8cb` | 修复 Makefile 中 namespace 和 deployment name |
| `00ca79e` | 更新 Pool 示例配置 |
| `8c72962` / `a7684d0` | 升级最低 K8s 版本要求到 1.21.1+ |

---

## 四、Bug 修复

### 4.1 Server 端修复

| 提交 | 问题 | 修复方式 |
|------|------|----------|
| `9258f4f` | WebSocket 升级请求未被正确拦截 | 在代理前拒绝 WebSocket 升级请求 |
| `1970410` | 文件下载路径编码错误，宿主机卷挂载目录缺失 | 使用 `quote(path, safe='/')` 编码；`os.makedirs` 自动创建目录 |
| `47bad5e` / `5904d62` | Server 打包和 pytest 配置问题 | 修复 `pyproject.toml` |
| `aa974a0` | Docker 卷验证的错误处理不一致 | 统一 host path 创建失败的错误码（`HOST_PATH_CREATE_FAILED`） |

### 4.2 execd 端修复

| 提交 | 问题 | 修复方式 |
|------|------|----------|
| `35b6563` | 缺失的 code context 返回 500 | 改为返回 404 并附带明确错误信息 |

### 4.3 文档修复

| 提交 | 问题 |
|------|------|
| `6c95a5f` | OSEP-0004 链接逃逸 docs/ 根目录导致 VitePress 构建失败 |
| `9c539d1` | CONTRIBUTING.md 中多处断链 |
| `ac24abd` | README 中 license badge 无效 |

---

## 五、工程化与 CI/CD 改进

### 5.1 SDK 质量管控

**核心提交：** `92f7208` Feature/ruff and pyright check for sdks

- 将 CI workflow 从 `sdk-unit-tests.yml` 重命名为 `sdk-tests.yml`
- 新增 ruff + pyright 静态检查，覆盖 Python SDK 代码质量
- 修复 filesystem_adapter 中 pyright 报错

### 5.2 SDK 打包优化

**核心提交：** `327b557` chore(sdks): refine packaging

- C# SDK 新增 `Directory.Build.props` 统一构建属性
- JavaScript、Python、C# SDK 版本号统一更新
- C# 发布 workflow 增强

### 5.3 构建与发布

| 提交 | 内容 |
|------|------|
| `e7d2b05` | 所有组件（execd/ingress/egress/server）的 `build.sh` 支持 `v` 前缀 TAG |
| `cf449cb` | Ingress 组件支持 `linux/arm64` 镜像构建 |
| `77d6ceb` | 优化 GitHub Actions 触发条件 |

### 5.4 测试强化

| 提交 | 内容 |
|------|------|
| `cb01841` | JS E2E 测试：增强 Java 和 Volume 断言的容错性 |
| `041d193` | gVisor E2E：改进二进制下载和集群初始化流程 |
| `26dcd90` / `ddbf36c` | 清理废弃的 Kata 测试数据和用例 |

---

## 六、文档更新

| 提交 | 内容 |
|------|------|
| `277a0bf` | **新增 `SECURITY.md`**（36 行），安全漏洞报告流程 |
| `98f84b5` | 更新 README badge 和措辞 |
| `4276b94` | README 新增强隔离安全特性描述 |
| `cb8c9b0` | 更新 2026.03 核心 Roadmap |
| `d4458f1` | OSEP-0002 标记 agent-sandbox 支持已实现 |
| `f1efc4e` | 架构文档标注 K8s 运行时就绪状态 |
| `dad0061` | OSEP-0004 安全容器运行时文档大幅扩充 |

---

## 七、变更统计

### 按模块分布

| 模块 | 新增文件 | 修改文件 | 主要变化 |
|------|---------|---------|---------|
| `server/` | 4 | 18 | 安全运行时、Request-ID 中间件、EIP 配置、多项修复 |
| `kubernetes/` | 16 | 12 | Helm Chart 体系、gVisor E2E、Makefile 重构 |
| `components/execd/` | 0 | 5 | UID/GID 重构、404 错误码 |
| `components/ingress/` | 0 | 4 | DNS-1035 规范化、ARM64 支持 |
| `sdks/` | 1 | 9 | 打包优化、pyright 修复 |
| `docs/` | 1 | 3 | 安全容器指南、架构更新 |
| `.github/` | 0 | 4 | CI 优化 |
| 根目录 | 1 | 3 | SECURITY.md、README、CONTRIBUTING |

### 按变更类型分布

| 类型 | 提交数 | 代表性变更 |
|------|--------|-----------|
| feat（新特性） | 6 | 安全容器运行时、Request-ID、EIP 配置、UID/GID 重构 |
| fix（修复） | 11 | WebSocket 拦截、DNS-1035、路径编码、execd 404 |
| docs（文档） | 11 | SECURITY.md、Roadmap、架构图、OSEP 更新 |
| chore（工程） | 11 | Helm Chart、构建脚本、SDK 打包、依赖升级 |
| test（测试） | 4 | gVisor E2E、JS E2E 增强、Kata 清理 |
| style（风格） | 1 | SDK pyright 修复 |

---

## 八、对本地开发的影响

### 需要关注的配置变更

1. **`server/src/config.py`** 新增了 `secure_runtime` 和 `create_timeout` 配置段，如果本地有自定义 `~/.sandbox.toml`，建议重新生成模板确认新增字段。

2. **`server/pyproject.toml`** 有多处修改（依赖、pytest 配置），本地需要重新执行 `uv sync`。

3. **Kubernetes 部署**：新增了 `opensandbox-server` 和 `opensandbox`（all-in-one）两个 Helm Chart，部署方式有较大变化。

### 需要注意的 Breaking Changes

- `components/execd/pkg/runtime/types.go` 中 UID/GID 从值类型改为指针类型，如果有自定义的 execd 扩展代码需要适配。
- K8s Provider 的构造函数签名有变化（新增 `provider_factory` 中的安全运行时参数）。

---

## 九、总结

本次更新是 OpenSandbox 项目的一次**重量级迭代**，核心亮点：

1. **安全容器运行时** — 完成了从配置模型、运行时解析、Docker/K8s 双后端适配到 E2E 测试的全链路实现，是项目安全隔离能力的重大提升。
2. **Helm 部署体系成熟化** — Server Helm Chart 和 All-in-One 聚合 Chart 的引入，使 K8s 部署进入生产可用状态。
3. **可观测性增强** — X-Request-ID 全链路追踪为生产环境的日志排查提供了基础设施。
4. **工程质量提升** — SDK 静态检查、DNS-1035 规范化、ARM64 支持等改进体现了项目向生产级成熟度演进的趋势。
