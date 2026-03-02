# 002 · OpenSandbox 新手完全使用指南

> 文档编号：002
> 适用环境：macOS 26.3 · Apple Silicon (arm64) · Docker 28 · Python 3.11 · uv 已安装
> 创建日期：2026-03-02

---

## 目录

1. [先搞清楚：OpenSandbox 是什么](#一先搞清楚opensandbox-是什么)
2. [整体架构：三个角色](#二整体架构三个角色)
3. [第一步：启动 OpenSandbox 服务器](#三第一步启动-opensandbox-服务器)
4. [第二步：跑通第一个沙箱（Hello World）](#四第二步跑通第一个沙箱hello-world)
5. [第三步：使用代码解释器执行多语言代码](#五第三步使用代码解释器执行多语言代码)
6. [第四步：文件操作](#六第四步文件操作)
7. [第五步：在沙箱里执行 Shell 命令](#七第五步在沙箱里执行-shell-命令)
8. [第六步：使用网络策略限制沙箱出口](#八第六步使用网络策略限制沙箱出口)
9. [直接用 REST API 操作（curl）](#九直接用-rest-api-操作curl)
10. [常见问题排查](#十常见问题排查)
11. [下一步学什么](#十一下一步学什么)

---

## 一、先搞清楚：OpenSandbox 是什么

用一句话解释：**OpenSandbox 是一个"远程安全沙盒"服务——你发一段代码给它，它在一个隔离的 Docker 容器里跑完，把结果还给你，容器随后销毁。**

类比理解：
- 就像"一次性手套"——用完即扔，沙箱里干的任何事都不影响你的电脑
- 就像"远程 Jupyter Notebook"——但更安全，支持多语言，有标准化 API

**整个系统由两部分组成：**

```
你的代码（SDK 调用）
        ↓
OpenSandbox Server（控制台，管理沙箱的生命周期）
        ↓
Docker 容器（沙箱，真正执行代码的地方）
```

---

## 二、整体架构：三个角色

| 角色 | 是什么 | 在哪里运行 |
|------|--------|-----------|
| **OpenSandbox Server** | FastAPI 服务，负责创建/销毁沙箱 | 你的 Mac 上，监听 8310 端口 |
| **沙箱容器（Sandbox）** | Docker 容器，执行实际工作 | Docker 里动态创建和销毁 |
| **SDK / 你的代码** | Python 库，告诉 Server 干什么 | 你的终端里 |

**数据流：**

```
你的 Python 脚本
  → (HTTP) → OpenSandbox Server :8310
  → (Docker API) → 创建容器
  → (HTTP :44772) → execd 守护进程（在容器内）
  → 执行代码/命令/文件操作
  → 结果返回
```

---

## 三、第一步：启动 OpenSandbox 服务器

### 3.1 确认 Docker 正在运行

```bash
docker version
# 看到 Client 和 Server 信息即为正常
```

如果报错 "Cannot connect to the Docker daemon"，请先打开 Docker Desktop。

### 3.2 安装依赖（从源码目录运行）

> **重要**：不要用 `uv pip install opensandbox-server` 全局安装。
> PyPI 发布包（v0.1.4）存在两个已知问题：
> 1. 不附带配置模板文件，`init-config` 命令会报错
> 2. 全局安装后因 Python 路径冲突（Docker SDK 找不到 `http+docker` scheme）导致启动失败
>
> 正确做法是直接使用仓库源码，通过 `uv run` 在隔离环境中启动。

进入服务器源码目录，安装依赖：

```bash
cd /Users/shawn/dev/OpenSandbox/server
uv sync
```

`uv sync` 会自动创建 `.venv` 虚拟环境并安装所有依赖，完全隔离，不污染系统 Python。

### 3.3 生成配置文件

PyPI 版的 `init-config` 命令在当前版本无法找到模板文件，直接从源码目录复制：

```bash
cp /Users/shawn/dev/OpenSandbox/server/example.config.toml ~/.sandbox.toml
```

查看内容确认端口正确：

```bash
cat ~/.sandbox.toml
```

你会看到类似这样的配置（默认值就够用了，不用修改）：

```toml
[server]
host = "127.0.0.1"
port = 8310
log_level = "INFO"
# api_key 没有设置 = 本地开发不需要认证，方便调试

[runtime]
type = "docker"
execd_image = "opensandbox/execd:v1.0.6"   # execd 守护进程镜像

[docker]
network_mode = "bridge"   # bridge 模式：每个沙箱有独立网络
```

> **注意**：`network_mode = "bridge"` 代表每个沙箱有独立的网络，多个沙箱可以同时运行。
> 如果改成 `"host"` 则所有沙箱共享宿主机网络，同时只能运行一个。

### 3.4 启动服务器

**打开一个新的终端窗口**（服务器会一直占用这个窗口），运行：

```bash
cd /Users/shawn/dev/OpenSandbox/server
uv run opensandbox-server
```

看到类似下面的输出就代表启动成功：

```
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8310 (Press CTRL+C to quit)
```

### 3.5 验证服务器健康

**在另一个终端窗口**运行：

```bash
curl http://localhost:8310/health
# 期望输出：{"status":"healthy"}
```

查看 Swagger API 文档（在浏览器打开）：

```
http://localhost:8310/docs
```

---

## 四、第二步：跑通第一个沙箱（Hello World）

### 4.1 关于 SDK 安装

不需要单独安装 SDK。使用 `uv run --with` 在运行时临时引入依赖，完全隔离，不污染任何环境：

```bash
uv run --with opensandbox --with opensandbox-code-interpreter python your_script.py
```

后续章节的示例都用这种方式运行。

### 4.2 拉取沙箱镜像

沙箱本质是一个 Docker 镜像。代码解释器官方镜像包含了 Python/Java/Go/JS 的执行环境：

```bash
# 国内速度更快（推荐）
docker pull sandbox-registry.cn-zhangjiakou.cr.aliyuncs.com/opensandbox/code-interpreter:v1.0.1

# 国际源（Docker Hub）
# docker pull opensandbox/code-interpreter:v1.0.1
```

> **注意**：这个镜像实际大小约 **14GB**（包含 Python/Java/Go/JavaScript/TypeScript 多语言完整运行时），拉取需要 10-30 分钟，取决于网速，耐心等待。
>
> 拉取前请确认 Docker Desktop 有足够磁盘空间（至少 20GB 可用）。可以先运行 `docker system df` 查看当前占用，必要时用 `docker system prune` 清理。

### 4.3 写第一个脚本

创建文件 `~/hello_sandbox.py`：

```python
import asyncio
from datetime import timedelta
from opensandbox import Sandbox

async def main():
    print("正在创建沙箱...")

    # 创建一个沙箱，使用 code-interpreter 镜像
    sandbox = await Sandbox.create(
        # 沙箱使用的 Docker 镜像
        "sandbox-registry.cn-zhangjiakou.cr.aliyuncs.com/opensandbox/code-interpreter:v1.0.1",
        # 镜像启动时运行的命令
        entrypoint=["/opt/opensandbox/code-interpreter.sh"],
        # 沙箱最长存活时间（超时自动销毁）
        timeout=timedelta(minutes=10),
    )

    print(f"沙箱已创建！ID = {sandbox.id}")
    print(f"沙箱状态 = {sandbox.status}")

    # "async with" 块结束时自动关闭连接（但不销毁沙箱）
    async with sandbox:
        # 在沙箱里执行一条 Shell 命令
        result = await sandbox.commands.run("echo 'Hello from sandbox!'")
        print(f"\n命令输出：{result.logs.stdout[0].text}")

        # 查看沙箱里的 Python 版本
        result2 = await sandbox.commands.run("python3 --version")
        print(f"沙箱里的 Python 版本：{result2.logs.stdout[0].text}")

    # 手动销毁沙箱（释放 Docker 容器）
    await sandbox.kill()
    print("\n沙箱已销毁。")


if __name__ == "__main__":
    asyncio.run(main())
```

### 4.4 运行脚本

```bash
SANDBOX_DOMAIN="localhost:8310" uv run --with opensandbox python ~/hello_sandbox.py
```

> `SANDBOX_DOMAIN` 指定服务器地址，覆盖 SDK 内部的默认值（`localhost:8080`）。

**期望输出：**

```
正在创建沙箱...
沙箱已创建！ID = a1b2c3d4-5678-90ab-cdef-1234567890ab
沙箱状态 = Running

命令输出：Hello from sandbox!
沙箱里的 Python 版本：Python 3.11.x

沙箱已销毁。
```

**同时在服务器终端，你会看到创建和销毁的日志。**

> **如果第一次运行很慢（30~60 秒）**：这是正常的，服务器需要拉取 `execd` 镜像并注入到容器中。第二次运行会快很多（镜像已缓存）。

---

## 五、第三步：使用代码解释器执行多语言代码

代码解释器（Code Interpreter）是 OpenSandbox 的核心功能，基于 Jupyter 内核，支持**会话内状态持久化**——前一次执行定义的变量，后续执行中仍然可用。

### 5.1 直接运行官方示例

项目已有完整示例，直接跑：

```bash
cd /Users/shawn/dev/OpenSandbox

SANDBOX_DOMAIN="localhost:8310" uv run \
  --with opensandbox \
  --with opensandbox-code-interpreter \
  python examples/code-interpreter/main.py
```

> SDK 默认连接 `localhost:8080`，通过 `SANDBOX_DOMAIN` 环境变量覆盖为 `localhost:8310`。

**期望输出：**

```
=== Python example ===
[Python stdout] Hello from Python!
[Python result] {'py': '3.14.2', 'sum': 4}

=== Java example ===
[Java stdout] Hello from Java!
[Java stdout] 2 + 3 = 5
[Java result] 5

=== Go example ===
[Go stdout] Hello from Go!
3 + 4 = 7

=== TypeScript example ===
[TypeScript stdout] Hello from TypeScript!
[TypeScript stdout] sum = 6
```

### 5.2 理解代码解释器的工作方式

创建 `~/code_interpreter_demo.py`，演示**状态持久化**：

```python
import asyncio
from datetime import timedelta
from code_interpreter import CodeInterpreter, SupportedLanguage
from opensandbox import Sandbox

IMAGE = "sandbox-registry.cn-zhangjiakou.cr.aliyuncs.com/opensandbox/code-interpreter:v1.0.1"

async def main():
    sandbox = await Sandbox.create(
        IMAGE,
        entrypoint=["/opt/opensandbox/code-interpreter.sh"],
        timeout=timedelta(minutes=10),
    )

    async with sandbox:
        # 创建代码解释器会话
        interpreter = await CodeInterpreter.create(sandbox=sandbox)

        print("=== 演示：变量跨次执行持久化 ===\n")

        # 第 1 次执行：定义变量
        r1 = await interpreter.codes.run(
            "x = 42\nprint(f'定义了 x = {x}')",
            language=SupportedLanguage.PYTHON,
        )
        print("第 1 次执行:", r1.logs.stdout[0].text)

        # 第 2 次执行：使用上次定义的变量（跨次持久化！）
        r2 = await interpreter.codes.run(
            "print(f'x 仍然存在：{x}')\ny = x * 2\ny",
            language=SupportedLanguage.PYTHON,
        )
        print("第 2 次执行:", r2.logs.stdout[0].text)
        print("第 2 次结果:", r2.result[0].text)  # 84

        print("\n=== 演示：安装并使用第三方库 ===\n")

        # 安装并立即使用
        r3 = await interpreter.codes.run(
            "import subprocess\n"
            "subprocess.run(['pip', 'install', 'requests', '-q'])\n"
            "import requests\n"
            "print(f'requests 版本：{requests.__version__}')",
            language=SupportedLanguage.PYTHON,
        )
        print("安装结果:", r3.logs.stdout[-1].text)

    await sandbox.kill()
    print("\n完成，沙箱已销毁。")


if __name__ == "__main__":
    asyncio.run(main())
```

```bash
uv run python ~/code_interpreter_demo.py
```

---

## 六、第四步：文件操作

沙箱的文件系统 API 让你可以在沙箱里读写文件，就像操作远程服务器一样。

创建 `~/file_ops_demo.py`：

```python
import asyncio
from datetime import timedelta
from opensandbox import Sandbox
from opensandbox.models import WriteEntry

IMAGE = "sandbox-registry.cn-zhangjiakou.cr.aliyuncs.com/opensandbox/code-interpreter:v1.0.1"

async def main():
    sandbox = await Sandbox.create(
        IMAGE,
        entrypoint=["/opt/opensandbox/code-interpreter.sh"],
        timeout=timedelta(minutes=10),
    )

    async with sandbox:
        print("=== 文件写入 ===")

        # 写入单个文件
        await sandbox.files.write_files([
            WriteEntry(
                path="/tmp/hello.txt",
                data="你好，OpenSandbox！",
                mode=644,     # Unix 文件权限
            )
        ])
        print("已写入 /tmp/hello.txt")

        # 批量写入多个文件
        await sandbox.files.write_files([
            WriteEntry(path="/tmp/script.py", data="print('来自沙箱的脚本')\n"),
            WriteEntry(path="/tmp/config.json", data='{"key": "value", "num": 42}'),
        ])
        print("批量写入完成")

        print("\n=== 文件读取 ===")

        # 读取文件内容
        content = await sandbox.files.read_file("/tmp/hello.txt")
        print(f"读取结果：{content}")

        print("\n=== 文件搜索 ===")

        # 用 glob 模式搜索文件
        files = await sandbox.files.search("/tmp", "*.txt")
        print(f"找到 .txt 文件：{[f.path for f in files]}")

        print("\n=== 执行写入的脚本 ===")

        # 在沙箱里运行刚写入的脚本
        result = await sandbox.commands.run("python3 /tmp/script.py")
        print(f"脚本输出：{result.logs.stdout[0].text}")

        print("\n=== 文件信息查询 ===")

        # 获取文件元数据
        info = await sandbox.files.get_file_info("/tmp/hello.txt")
        print(f"文件大小：{info.size} 字节")
        print(f"文件权限：{info.mode}")

    await sandbox.kill()
    print("\n沙箱已销毁。")


if __name__ == "__main__":
    asyncio.run(main())
```

```bash
uv run python ~/file_ops_demo.py
```

---

## 七、第五步：在沙箱里执行 Shell 命令

### 7.1 同步命令（等待完成）

```python
import asyncio
from datetime import timedelta
from opensandbox import Sandbox

IMAGE = "sandbox-registry.cn-zhangjiakou.cr.aliyuncs.com/opensandbox/code-interpreter:v1.0.1"

async def main():
    sandbox = await Sandbox.create(
        IMAGE,
        entrypoint=["/opt/opensandbox/code-interpreter.sh"],
        timeout=timedelta(minutes=10),
    )

    async with sandbox:
        # 普通命令
        r = await sandbox.commands.run("ls -la /tmp")
        print("目录内容：")
        print(r.logs.stdout[0].text)

        # 带工作目录的命令
        r2 = await sandbox.commands.run(
            "pwd && ls",
            cwd="/usr"  # 在 /usr 目录下执行
        )
        print("\n工作目录测试：")
        print(r2.logs.stdout[0].text)

        # 执行失败的命令（检查 stderr）
        r3 = await sandbox.commands.run("cat /nonexistent_file")
        if r3.logs.stderr:
            print(f"\n错误输出：{r3.logs.stderr[0].text}")

    await sandbox.kill()

asyncio.run(main())
```

### 7.2 流式输出（实时看到长任务输出）

对于耗时较长的命令，可以用流式接口实时获取输出：

```python
import asyncio
from datetime import timedelta
from opensandbox import Sandbox

IMAGE = "sandbox-registry.cn-zhangjiakou.cr.aliyuncs.com/opensandbox/code-interpreter:v1.0.1"

async def main():
    sandbox = await Sandbox.create(
        IMAGE,
        entrypoint=["/opt/opensandbox/code-interpreter.sh"],
        timeout=timedelta(minutes=10),
    )

    async with sandbox:
        print("实时流式输出（模拟长任务）：")

        # 流式执行，实时打印每一行
        async for event in sandbox.commands.run_stream(
            "for i in 1 2 3 4 5; do echo \"步骤 $i\"; sleep 0.5; done"
        ):
            if event.type == "stdout":
                print(f"  [实时] {event.text}", end="", flush=True)

    await sandbox.kill()

asyncio.run(main())
```

---

## 八、第六步：使用网络策略限制沙箱出口

这是 OpenSandbox 的独特功能——用**域名（FQDN）而不是 IP 地址**来控制沙箱能访问哪些网络。

> **前提**：需要在 `~/.sandbox.toml` 中配置了 egress 镜像，且使用 bridge 网络模式（默认配置已满足）。

```python
import asyncio
from datetime import timedelta
from opensandbox import Sandbox
from opensandbox.models import NetworkPolicy, EgressRule

IMAGE = "sandbox-registry.cn-zhangjiakou.cr.aliyuncs.com/opensandbox/code-interpreter:v1.0.1"

async def main():
    # 创建一个有网络限制的沙箱
    # 默认拒绝所有出口，只允许访问 pypi.org
    sandbox = await Sandbox.create(
        IMAGE,
        entrypoint=["/opt/opensandbox/code-interpreter.sh"],
        timeout=timedelta(minutes=10),
        network_policy=NetworkPolicy(
            default_action="deny",     # 默认拒绝所有出口流量
            egress=[
                EgressRule(action="allow", target="pypi.org"),
                EgressRule(action="allow", target="*.python.org"),
                EgressRule(action="allow", target="files.pythonhosted.org"),
            ]
        ),
    )

    async with sandbox:
        # 这个应该成功（pypi.org 在白名单里）
        r1 = await sandbox.commands.run("pip install requests -q && echo '安装成功'")
        print("访问 pypi.org:", r1.logs.stdout[0].text if r1.logs.stdout else "无输出")

        # 这个应该失败（github.com 不在白名单里）
        r2 = await sandbox.commands.run("curl -s --max-time 5 https://github.com || echo '访问被拒绝'")
        print("访问 github.com:", r2.logs.stdout[0].text if r2.logs.stdout else r2.logs.stderr[0].text)

    await sandbox.kill()
    print("完成。")

asyncio.run(main())
```

---

## 九、直接用 REST API 操作（curl）

不使用 SDK，直接用 curl 调用 REST API 也完全可以：

### 9.1 创建沙箱

```bash
curl -X POST "http://localhost:8310/v1/sandboxes" \
  -H "Content-Type: application/json" \
  -d '{
    "image": {
      "uri": "sandbox-registry.cn-zhangjiakou.cr.aliyuncs.com/opensandbox/code-interpreter:v1.0.1"
    },
    "entrypoint": ["/opt/opensandbox/code-interpreter.sh"],
    "timeout": 600,
    "resourceLimits": {
      "cpu": "500m",
      "memory": "512Mi"
    }
  }'
```

返回示例（记下 `id`）：

```json
{
  "id": "abc123-...",
  "status": {
    "state": "Pending",
    "reason": "CONTAINER_STARTING"
  },
  "expiresAt": "2026-03-02T10:20:00Z"
}
```

### 9.2 查看沙箱状态

```bash
SANDBOX_ID="abc123-..."

curl "http://localhost:8310/v1/sandboxes/$SANDBOX_ID"
```

等待 `"state": "Running"` 再继续操作。

### 9.3 获取 execd 端点（execd 是沙箱内的执行守护进程）

```bash
curl "http://localhost:8310/v1/sandboxes/$SANDBOX_ID/endpoints/44772"
# 返回：{"endpoint": "127.0.0.1:44772"}
```

### 9.4 列出所有沙箱

```bash
curl "http://localhost:8310/v1/sandboxes"
```

### 9.5 删除沙箱

```bash
curl -X DELETE "http://localhost:8310/v1/sandboxes/$SANDBOX_ID"
```

### 9.6 沙箱续期（防止超时销毁）

```bash
curl -X POST "http://localhost:8310/v1/sandboxes/$SANDBOX_ID/renew-expiration" \
  -H "Content-Type: application/json" \
  -d '{"expiresAt": "2026-03-02T12:00:00Z"}'
```

---

## 十、常见问题排查

### 问题 0：`uv pip install opensandbox-server` 报 "No virtual environment found"

```
error: No virtual environment found; run `uv venv` to create an environment,
or pass `--system` to install into a non-virtual environment
```

**不要**用 `--system` 绕过，也不要全局安装这个包（参见问题 0b）。
正确做法是直接从源码目录启动：

```bash
cd /Users/shawn/dev/OpenSandbox/server
uv sync                    # 创建隔离 venv 并安装依赖
uv run opensandbox-server  # 在 venv 中启动
```

---

### 问题 0b：`opensandbox-server init-config` 报 "Missing example config template"

```
Failed to write config template: Missing example config template at
/Library/Frameworks/.../site-packages/example.config.toml
```

PyPI 版（v0.1.4）未将配置模板打包进发布包。直接从源码目录复制：

```bash
cp /Users/shawn/dev/OpenSandbox/server/example.config.toml ~/.sandbox.toml
```

---

### 问题 0c：服务器启动报 "Not supported URL scheme http+docker"

```
requests.exceptions.InvalidURL: Not supported URL scheme http+docker
```

**根本原因**：全局安装 `opensandbox-server` 后，系统 Python 会优先加载用户目录
（`~/Library/Python/3.11/site-packages/`）里的 `requests` 库，与 Docker SDK 使用的
版本产生路径冲突，导致 `http+docker://` 协议无法识别。

**解决方案**：不用全局安装，改从源码目录用 `uv run` 启动，uv 的 venv 完全隔离，
不受系统 Python 路径影响：

```bash
cd /Users/shawn/dev/OpenSandbox/server
uv run opensandbox-server
```

---

### 问题 1：服务器启动报错 "Address already in use"

端口 8310 被占用。解决方案：

```bash
# 查看谁在占用 8310
lsof -i :8310

# 方案 A：修改 OpenSandbox 端口
# 编辑 ~/.sandbox.toml，将 port = 8310 改为其他端口（如 port = 8311）

# 方案 B：终止占用的进程（谨慎操作）
kill -9 <PID>
```

---

### 问题 2：创建沙箱超时或一直 Pending

**可能原因 1：Docker 镜像未拉取**

```bash
# 手动拉取镜像
docker pull sandbox-registry.cn-zhangjiakou.cr.aliyuncs.com/opensandbox/code-interpreter:v1.0.1
docker pull opensandbox/execd:v1.0.6
```

**可能原因 2：Docker Desktop 资源限制太小**

进入 Docker Desktop → Settings → Resources，建议设置：
- 内存：至少 4GB
- CPU：至少 2 核

**可能原因 3：网络问题**

```bash
# 测试 Docker Hub 连通性
docker pull hello-world
```

---

### 问题 3：`Cannot connect to the Docker daemon`

```bash
# 确认 Docker Desktop 已启动
open -a Docker

# 等待 Docker 完全启动后再试
docker version
```

---

### 问题 4：`exec /opt/opensandbox/bootstrap.sh: operation not permitted`

这是 macOS 上 Docker Desktop 的权限问题。

```bash
# 查看沙箱容器日志
docker ps -a  # 找到沙箱容器 ID
docker logs <container-id>
```

解决方案：更新 Docker Desktop 到最新版本，或在 Docker Desktop 设置中关闭 "Use Virtualization framework"。

---

### 问题 5：Bridge 模式下无法访问沙箱端口

在 bridge 网络模式下，沙箱有独立的网络命名空间，需要通过 OpenSandbox Server 代理访问：

```bash
# 通过代理访问（加 use_server_proxy=true 参数）
curl "http://localhost:8310/v1/sandboxes/$SANDBOX_ID/endpoints/44772?use_server_proxy=true"
# 返回的端点是 Server 代理地址，可以直接访问
```

---

### 问题 6：Python 脚本报错 `ModuleNotFoundError`

不要直接 `python your_script.py`，改用 `uv run --with` 携带所需 SDK：

```bash
# 只用 opensandbox SDK
SANDBOX_DOMAIN="localhost:8310" uv run --with opensandbox python your_script.py

# 同时用 code-interpreter SDK
SANDBOX_DOMAIN="localhost:8310" uv run \
  --with opensandbox \
  --with opensandbox-code-interpreter \
  python your_script.py
```

---

### 问题 7：沙箱创建成功但代码执行报错

检查服务器日志（服务器终端窗口），常见原因：
- execd 镜像拉取失败：`docker pull opensandbox/execd:v1.0.6`
- 沙箱镜像不兼容：确保使用官方的 `code-interpreter` 或 `aio-sandbox` 镜像

---

### 清理所有残留沙箱

如果测试后沙箱没有正常销毁，用以下命令清理：

```bash
# 查看正在运行的 OpenSandbox 容器（名字以 sandbox- 开头）
docker ps --filter "name=sandbox"

# 停止并删除所有测试沙箱
docker ps --filter "name=sandbox" -q | xargs docker stop | xargs docker rm

# 或者重启 OpenSandbox Server（会自动清理过期沙箱）
```

---

## 十一、下一步学什么

### 11.1 运行更多官方示例

```bash
cd /Users/shawn/dev/OpenSandbox

# 运行代码解释器完整示例
SANDBOX_DOMAIN="localhost:8310" uv run \
  --with opensandbox \
  --with opensandbox-code-interpreter \
  python examples/code-interpreter/main.py
```

### 11.2 尝试 AIO（All-in-One）沙箱——带浏览器截图

```bash
# 拉取 AIO 镜像（包含完整桌面环境+浏览器）
docker pull ghcr.io/agent-infra/sandbox:latest

# 安装额外依赖
uv pip install agent-sandbox==0.0.18

# 运行（会创建一个沙箱，在里面打开 Google，截图保存到本地）
uv run python examples/aio-sandbox/main.py
```

### 11.3 查看交互式 API 文档

打开浏览器访问：

```
http://localhost:8310/docs
```

你可以直接在网页上测试所有 API，无需写代码。

### 11.4 关键配置项备忘

| 配置项 | 位置 | 作用 |
|--------|------|------|
| `server.api_key` | `~/.sandbox.toml` | 设置 API 密钥（开发时留空） |
| `docker.network_mode` | `~/.sandbox.toml` | `host`（单沙箱）或 `bridge`（多沙箱并行） |
| `runtime.execd_image` | `~/.sandbox.toml` | execd 版本 |
| `SANDBOX_DOMAIN` | 环境变量 | SDK 连接的服务器地址，默认 `localhost:8310` |
| `SANDBOX_API_KEY` | 环境变量 | SDK 使用的 API 密钥 |
| `SANDBOX_IMAGE` | 环境变量 | 默认沙箱镜像地址 |

### 11.5 常用沙箱镜像速查

| 镜像 | 用途 | 拉取命令 |
|------|------|---------|
| `opensandbox/code-interpreter:v1.0.1` | 代码解释器（Python/Java/Go/JS/TS） | 见下方 |
| `ghcr.io/agent-infra/sandbox:latest` | AIO 沙箱（含浏览器+桌面） | `docker pull ghcr.io/agent-infra/sandbox:latest` |
| `python:3.11-slim` | 纯 Python 环境 | `docker pull python:3.11-slim` |

```bash
# 代码解释器镜像（国内源）
docker pull sandbox-registry.cn-zhangjiakou.cr.aliyuncs.com/opensandbox/code-interpreter:v1.0.1

# 如果要用 Docker Hub 源（国际）
docker pull opensandbox/code-interpreter:v1.0.1
```

### 11.6 推荐阅读顺序

1. `notes/001-项目价值与痛点分析.md` — 理解项目背景和设计动机
2. `server/README.md` — 完整的服务器配置文档
3. `examples/` 目录下各示例的 README — 具体场景的使用指南
4. `docs/architecture.md` — 深入理解内部架构

---

## 快速参考卡

### 启动流程（每次使用前）

```bash
# 1. 确认 Docker Desktop 已启动
docker version

# 2. 启动 OpenSandbox Server（新开一个终端，从源码目录运行）
cd /Users/shawn/dev/OpenSandbox/server
uv run opensandbox-server

# 3. 验证（另一个终端）
curl http://localhost:8310/health
```

### SDK 运行方式

```bash
# 运行自己的脚本
SANDBOX_DOMAIN="localhost:8310" uv run --with opensandbox python your_script.py

# 运行官方代码解释器示例
cd /Users/shawn/dev/OpenSandbox
SANDBOX_DOMAIN="localhost:8310" uv run \
  --with opensandbox \
  --with opensandbox-code-interpreter \
  python examples/code-interpreter/main.py
```

### SDK 三行核心代码

```python
from opensandbox import Sandbox

sandbox = await Sandbox.create("IMAGE_URI", entrypoint=["..."])
result = await sandbox.commands.run("your command")
await sandbox.kill()
```

### 最常用的 SDK 操作

```python
# 执行命令
result = await sandbox.commands.run("echo hello")
output = result.logs.stdout[0].text

# 写文件
from opensandbox.models import WriteEntry
await sandbox.files.write_files([WriteEntry(path="/tmp/f.txt", data="content")])

# 读文件
content = await sandbox.files.read_file("/tmp/f.txt")

# 搜索文件
files = await sandbox.files.search("/tmp", "*.py")

# 执行 Python 代码（需要 Code Interpreter）
from code_interpreter import CodeInterpreter, SupportedLanguage
interpreter = await CodeInterpreter.create(sandbox=sandbox)
r = await interpreter.codes.run("print(1+1)", language=SupportedLanguage.PYTHON)
```
