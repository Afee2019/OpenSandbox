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

import asyncio
from datetime import timedelta

from opensandbox.sandbox import Sandbox
from opensandbox.config import ConnectionConfig
from opensandbox.exceptions import SandboxException

async def main():
    try:
        sandbox = await Sandbox.create(
            image="opensandbox/chrome:latest",
            timeout=timedelta(minutes=5),
            entrypoint=["/entrypoint"],
            metadata={"examples.opensandbox.io": "chrome"},
            connection_config=ConnectionConfig(
                domain="localhost:8080"
            )
        )

        # Got execd process endpoint
        execd = await sandbox.get_endpoint(44772)
        print(f"execd 守护进程已启动，地址：{execd.endpoint}")

        vnc = await sandbox.get_endpoint(5901)
        print(f"VNC 已启动，地址：{vnc.endpoint}")

        devtools = await sandbox.get_endpoint(9222)
        print(f"DevTools 已启动，地址：{devtools.endpoint}/json")

    except SandboxException as e:
        # Handle Sandbox specific exceptions
        print(f"沙箱错误：[{e.error.code}] {e.error.message}")
    except Exception as e:
        print(f"错误：{e}")

if __name__ == "__main__":
    asyncio.run(main())
