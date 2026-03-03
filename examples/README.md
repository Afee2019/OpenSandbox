# OpenSandbox 示例

常见 OpenSandbox 使用场景的示例代码。每个子目录均包含可直接运行的代码和说明文档。

## 集成 / 沙箱

- 🧰 [**aio-sandbox**](aio-sandbox)：使用 OpenSandbox SDK 和 agent-sandbox 构建的全功能沙箱
- <img src="https://kubernetes.io/icons/favicon-32.png" alt="Kubernetes" width="16" height="16" style="display:inline-block;width:16px;height:16px;vertical-align:middle;margin-right:4px;" /> [**agent-sandbox**](agent-sandbox)：创建 kubernetes-sigs/agent-sandbox 实例并运行命令
- 🧪 [**code-interpreter**](code-interpreter)：Code Interpreter SDK 单例使用示例
- 💾 [**host-volume-mount**](host-volume-mount)：将宿主机目录挂载到沙箱（读写、只读、子路径）
- 🎯 [**rl-training**](rl-training)：在沙箱内运行强化学习训练循环
- <img src="https://img.shields.io/badge/-%20-D97757?logo=claude&logoColor=white&style=flat-square" alt="Claude" width="16" height="16" style="display:inline-block;width:16px;height:16px;vertical-align:middle;margin-right:4px;" /> [**claude-code**](claude-code)：在沙箱内调用 Claude（Anthropic）API/CLI
- <img src="https://cli.iflow.cn/img/favicon.ico" alt="iFlow" width="16" height="16" style="display:inline-block;width:16px;height:16px;vertical-align:middle;margin-right:4px;" /> [**iflow-cli**](iflow-cli)：iFlow / 自定义 HTTP LLM 服务的 CLI 调用模板
- <img src="https://geminicli.com/favicon.ico" alt="Google Gemini" width="16" height="16" style="display:inline-block;width:16px;height:16px;vertical-align:middle;margin-right:4px;" /> [**gemini-cli**](gemini-cli)：在沙箱内调用 Google Gemini
- <img src="https://developers.openai.com/favicon.png" alt="OpenAI" width="16" height="16" style="display:inline-block;width:16px;height:16px;vertical-align:middle;margin-right:4px;" /> [**codex-cli**](codex-cli)：在沙箱内调用 OpenAI/Codex 类模型
- <img src="https://www.kimi.com/favicon.ico" alt="Kimi" width="16" height="16" style="display:inline-block;width:16px;height:16px;vertical-align:middle;margin-right:4px;" /> [**kimi-cli**](kimi-cli)：在沙箱内调用 Kimi Code CLI（月之暗面）
- <img src="https://img.shields.io/badge/-%20-1C3C3C?logo=langgraph&logoColor=white&style=flat-square" alt="LangGraph" width="16" height="16" style="display:inline-block;width:16px;height:16px;vertical-align:middle;margin-right:4px;" /> [**langgraph**](langgraph)：使用 LangGraph Agent 编排沙箱生命周期与工具调用
- <img src="https://google.github.io/adk-docs/assets/agent-development-kit.png" alt="Google ADK" width="16" height="16" style="display:inline-block;width:16px;height:16px;vertical-align:middle;margin-right:4px;" /> [**google-adk**](google-adk)：Google ADK Agent 调用 OpenSandbox 工具
- 🦞 [**nullclaw**](nullclaw)：在沙箱内启动 Nullclaw Gateway
- 🦞 [**openclaw**](openclaw)：在沙箱内运行 OpenClaw Gateway
- 🤖 [**jcdo**](jcdo)：在沙箱内运行 jcdo Gateway（基于 OpenClaw 改造的多渠道 AI 网关）
- 🖥️ [**desktop**](desktop)：启动 VNC 桌面（Xvfb + x11vnc），供 VNC 客户端连接
- <img src="https://playwright.dev/img/playwright-logo.svg" alt="Playwright" width="16" height="16" style="display:inline-block;width:16px;height:16px;vertical-align:middle;margin-right:4px;" /> [**playwright**](playwright)：启动无头浏览器（Playwright + Chromium）抓取网页内容
- <img src="https://code.visualstudio.com/assets/favicon.ico" alt="VS Code" width="16" height="16" style="display:inline-block;width:16px;height:16px;vertical-align:middle;margin-right:4px;" /> [**vscode**](vscode)：启动 code-server（VS Code Web），通过浏览器访问编辑器
- <img src="https://www.google.com/chrome/static/images/chrome-logo.svg" alt="Google Chrome" width="16" height="16" style="display:inline-block;width:16px;height:16px;vertical-align:middle;margin-right:4px;" /> [**chrome**](chrome)：启动无头 Chromium 并暴露 DevTools 端口，支持远程调试

## 如何运行

- 设置基础环境变量（如 `export SANDBOX_DOMAIN=...`、`export SANDBOX_API_KEY=...`）
- 根据需要设置各服务商的专用变量（如 `ANTHROPIC_API_KEY`、`OPENAI_API_KEY`、`GEMINI_API_KEY`、`KIMI_API_KEY`、`IFLOW_API_KEY`/`IFLOW_ENDPOINT` 等；模型选择为可选项）
- 进入对应示例目录，安装依赖：`pip install -r requirements.txt`（或参考目录内的 Dockerfile）
- 执行：`python main.py`
- 如需容器化运行，使用目录内的 `Dockerfile` 构建并运行镜像
- 总结：先通过 `export` 设置所需环境变量，再在对应目录执行 `python main.py`，或构建/运行该目录的 Docker 镜像。
