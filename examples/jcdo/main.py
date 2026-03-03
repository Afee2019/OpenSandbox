# Copyright 2026 Alibaba Group Holding Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import time
from datetime import timedelta
from pathlib import Path

import requests
from opensandbox import SandboxSync
from opensandbox.config import ConnectionConfigSync
from opensandbox.models.sandboxes import Host, NetworkPolicy, NetworkRule, Volume

# jcdo gateway port inside the container
GATEWAY_PORT = 8255

# Mount the local ~/.jcdo directory here (read-only).
# The entrypoint copies jcdo.json into the writable ~/.jcdo before starting
# the gateway, so jcdo can write session/log files without restriction.
READONLY_MOUNT_PATH = "/home/node/.jcdo-host"
WORKSPACE_MOUNT_PATH = "/home/node/.jcdo-workspace-host"

# Entrypoint: copy config and workspace from read-only mounts into the
# writable ~/.jcdo, then start gateway.
#
# Important: both mounts use paths outside ~/.jcdo so Docker does NOT
# pre-create ~/.jcdo with root ownership (which would block the node user).
ENTRYPOINT = (
    f"sh -c '"
    f"mkdir -p /home/node/.jcdo && "
    f"cp {READONLY_MOUNT_PATH}/jcdo.json /home/node/.jcdo/jcdo.json && "
    f"cp -r {WORKSPACE_MOUNT_PATH} /home/node/.jcdo/workspace && "
    f"node dist/index.js gateway --bind=lan --port {GATEWAY_PORT} --verbose"
    f"'"
)


def check_jcdo(sbx: SandboxSync) -> bool:
    """
    健康检查：轮询 jcdo gateway，直到返回 HTTP 200。

    返回值：
        True  — 就绪
        False — 超时或发生异常
    """
    try:
        endpoint = sbx.get_endpoint(GATEWAY_PORT)
        start = time.perf_counter()
        url = f"http://{endpoint.endpoint}"
        for _ in range(150):  # 最多等待约 30 秒
            try:
                resp = requests.get(url, timeout=1)
                if resp.status_code == 200:
                    elapsed = time.perf_counter() - start
                    print(f"[检查] jcdo gateway 就绪，耗时 {elapsed:.1f}s")
                    return True
            except Exception:
                pass
            time.sleep(0.2)
        return False
    except Exception as exc:
        print(f"[检查] 失败：{exc}")
        return False


def main() -> None:
    server = os.getenv("SANDBOX_SERVER", "http://localhost:8310")
    # Build jcdo locally first: cd ~/dev/jcdo && docker build -t jcdo:local .
    image = os.getenv("JCDO_IMAGE", "jcdo:local")
    timeout_seconds = 3600  # 1 hour
    token = os.getenv("JCDO_GATEWAY_TOKEN", "dummy-token-for-sandbox")

    # Mount local ~/.jcdo read-only; entrypoint copies jcdo.json before starting.
    jcdo_config_dir = str(Path.home() / ".jcdo")

    print(f"正在创建 jcdo 沙箱，镜像={image}，OpenSandbox Server={server}...")
    print(f"配置来源：{jcdo_config_dir}/jcdo.json（只读挂载）")

    sandbox = SandboxSync.create(
        image=image,
        timeout=timedelta(seconds=timeout_seconds),
        metadata={"example": "jcdo"},
        entrypoint=[ENTRYPOINT],
        connection_config=ConnectionConfigSync(domain=server),
        health_check=check_jcdo,
        env={
            "JCDO_GATEWAY_TOKEN": token,
            "NODE_ENV": "production",
        },
        volumes=[
            Volume(
                name="jcdo-config",
                host=Host(path=jcdo_config_dir),
                mountPath=READONLY_MOUNT_PATH,
                readOnly=True,
            ),
            # Mount workspace files (AGENTS.md, SOUL.md, TOOLS.md, etc.)
            # so the AI assistant has its full persona and context.
            # NOTE: mounted to a sibling path, NOT inside ~/.jcdo, to avoid
            # Docker pre-creating ~/.jcdo with root ownership.
            Volume(
                name="jcdo-workspace",
                host=Host(path=str(Path.home() / ".jcdo" / "workspace")),
                mountPath=WORKSPACE_MOUNT_PATH,
                readOnly=True,
            ),
        ],
        # Allow outbound access to configured LLM API endpoints.
        # Adjust to match your jcdo.json providers.
        network_policy=NetworkPolicy(
            defaultAction="deny",
            egress=[
                NetworkRule(action="allow", target="api.deepseek.com"),
                NetworkRule(action="allow", target="dashscope.aliyuncs.com"),
                NetworkRule(action="allow", target="registry.npmjs.org"),
            ],
        ),
    )

    endpoint = sandbox.get_endpoint(GATEWAY_PORT)
    ws_url = f"ws://{endpoint.endpoint}"
    print(f"\njcdo gateway 已启动。")
    print(f"  WebSocket  ：{ws_url}")
    print(f"  Token      ：{token}")
    print(f"  沙箱 ID    ：{sandbox.id}")
    print(f"\n连接方式：")
    print(f"  jcdo acp --url {ws_url} --token {token}")


if __name__ == "__main__":
    main()
