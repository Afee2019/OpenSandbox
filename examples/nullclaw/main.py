# Copyright 2025 Alibaba Group Holding Ltd.
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

import time
from datetime import timedelta

import requests
from opensandbox import SandboxSync
from opensandbox.config import ConnectionConfigSync
from opensandbox.models.sandboxes import NetworkPolicy, NetworkRule


def check_nullclaw(sbx: SandboxSync) -> bool:
    """
    健康检查：轮询 nullclaw gateway，直到返回 HTTP 200。

    返回值：
        True  — 就绪
        False — 超时或发生异常
    """
    try:
        endpoint = sbx.get_endpoint(3000)
        start = time.perf_counter()
        url = f"http://{endpoint.endpoint}/health"
        for _ in range(150):  # 最多等待约 30 秒
            try:
                resp = requests.get(url, timeout=1)
                if resp.status_code == 200:
                    elapsed = time.perf_counter() - start
                    print(f"[检查] 沙箱就绪，耗时 {elapsed:.1f}s")
                    return True
            except Exception:
                pass
            time.sleep(0.2)
        return False
    except Exception as exc:
        print(f"[检查] 失败：{exc}")
        return False


def main() -> None:
    server = "http://localhost:8080"
    image = "ghcr.io/nullclaw/nullclaw:latest"
    timeout_seconds = 3600  # 1 hour

    print(f"正在创建 nullclaw 沙箱，镜像={image}，OpenSandbox Server={server}...")
    sandbox = SandboxSync.create(
        image=image,
        timeout=timedelta(seconds=timeout_seconds),
        metadata={"example": "nullclaw"},
        connection_config=ConnectionConfigSync(domain=server),
        health_check=check_nullclaw,
        # use network policy to limit nullclaw network accesses
        network_policy=NetworkPolicy(
            defaultAction="deny",
            egress=[NetworkRule(action="allow", target="openrouter.ai")],
        ),
    )

    endpoint = sandbox.get_endpoint(3000)
    print(f"nullclaw gateway 已启动。访问地址：{endpoint.endpoint}")


if __name__ == "__main__":
    main()
