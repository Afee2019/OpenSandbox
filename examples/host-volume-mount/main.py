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

"""
Host Volume Mount Example
=========================

Demonstrates how to mount a host directory into a sandbox container using
the OpenSandbox Volume API. This enables sharing files, datasets, or model
checkpoints between the host machine and sandbox environments.

Three scenarios are demonstrated:

1. **Read-write mount** - Share a working directory for bidirectional file exchange.
2. **Read-only mount**  - Provide shared datasets or configs that sandboxes should
   not modify.
3. **SubPath mount**    - Mount a specific subdirectory from the host path.

Prerequisites:
- OpenSandbox server running with Docker runtime
- Server config includes `[storage]` section with appropriate `allowed_host_paths`
- Host directories created before running this script (see README.md)
"""

import asyncio
import os
import tempfile
from datetime import timedelta
from pathlib import Path

from opensandbox import Sandbox
from opensandbox.config import ConnectionConfig

try:
    from opensandbox.models.sandboxes import Host, Volume
except ImportError:
    print(
        "错误：当前安装的 opensandbox SDK 不包含 Volume/Host 模型。\n"
        "       Volume 支持需要使用源码中的最新 SDK。\n"
        "       请从本地仓库安装：\n"
        "\n"
        "           pip install -e sdks/sandbox/python\n"
        "\n"
        "       详见 README.md。"
    )
    raise SystemExit(1)


async def print_exec(sandbox: Sandbox, command: str) -> str | None:
    """Run a command in the sandbox and print/return stdout."""
    result = await sandbox.commands.run(command)
    if result.error:
        print(f"  [错误] {result.error.name}: {result.error.value}")
        return None
    text = "\n".join(msg.text for msg in result.logs.stdout)
    if text:
        print(f"  {text}")
    return text


async def demo_readwrite_mount(config: ConnectionConfig, image: str, host_dir: str) -> None:
    """
    Scenario 1: Read-write mount.

    Mount a host directory into the sandbox at /mnt/shared. Write a file from
    inside the sandbox, then verify it appears on the host.
    """
    print("\n" + "=" * 60)
    print("场景一：宿主机目录读写挂载")
    print("=" * 60)
    print(f"  宿主机路径：{host_dir}")
    print(f"  挂载路径  ：/mnt/shared")

    sandbox = await Sandbox.create(
        image=image,
        connection_config=config,
        timeout=timedelta(minutes=2),
        volumes=[
            Volume(
                name="shared-data",
                host=Host(path=host_dir),
                mountPath="/mnt/shared",
                readOnly=False,
            ),
        ],
    )

    async with sandbox:
        try:
            # Read existing files from host
            print("\n  [1] 列出沙箱内可见的文件：")
            await print_exec(sandbox, "ls -la /mnt/shared/")

            # Write a file from inside the sandbox
            print("\n  [2] 在沙箱内写入文件：")
            await print_exec(
                sandbox,
                "echo 'Hello from sandbox!' > /mnt/shared/sandbox-greeting.txt",
            )
            print("  -> 已写入：/mnt/shared/sandbox-greeting.txt")

            # Verify the file content
            print("\n  [3] 读取刚写入的文件：")
            await print_exec(sandbox, "cat /mnt/shared/sandbox-greeting.txt")

            # Check host-side: the file should now exist on the host
            host_file = Path(host_dir) / "sandbox-greeting.txt"
            if host_file.exists():
                print(f"\n  [4] 宿主机验证：{host_file}")
                print(f"      内容：{host_file.read_text().strip()}")
            else:
                print(f"\n  [4] 提示：{host_file} 在远程 Docker 下无法直接可见（符合预期）")

        finally:
            await sandbox.kill()

    print("\n  场景一完成。")


async def demo_readonly_mount(config: ConnectionConfig, image: str, host_dir: str) -> None:
    """
    Scenario 2: Read-only mount.

    Mount the same host directory as read-only. Verify reads work but writes
    are rejected by the container runtime.
    """
    print("\n" + "=" * 60)
    print("场景二：宿主机目录只读挂载")
    print("=" * 60)
    print(f"  宿主机路径：{host_dir}")
    print(f"  挂载路径  ：/mnt/readonly")

    sandbox = await Sandbox.create(
        image=image,
        connection_config=config,
        timeout=timedelta(minutes=2),
        volumes=[
            Volume(
                name="readonly-data",
                host=Host(path=host_dir),
                mountPath="/mnt/readonly",
                readOnly=True,
            ),
        ],
    )

    async with sandbox:
        try:
            # Read existing files
            print("\n  [1] 读取只读挂载目录中的文件：")
            await print_exec(sandbox, "ls -la /mnt/readonly/")

            # Read the marker file
            print("\n  [2] 读取 marker.txt：")
            await print_exec(sandbox, "cat /mnt/readonly/marker.txt")

            # Attempt to write (should fail)
            print("\n  [3] 尝试写入（应当失败）：")
            result = await sandbox.commands.run(
                "touch /mnt/readonly/should-fail.txt 2>&1 || echo 'Write denied (expected)'"
            )
            for msg in result.logs.stdout:
                print(f"  {msg.text}")
            for msg in result.logs.stderr:
                print(f"  {msg.text}")

        finally:
            await sandbox.kill()

    print("\n  场景二完成。")


async def demo_subpath_mount(config: ConnectionConfig, image: str, host_dir: str) -> None:
    """
    Scenario 3: SubPath mount.

    Mount only a specific subdirectory from the host path. This is useful when
    the host path contains multiple datasets or project directories, and you
    want to expose only one of them.
    """
    print("\n" + "=" * 60)
    print("场景三：宿主机目录子路径挂载")
    print("=" * 60)

    # Ensure subdirectory exists on host
    sub_dir = Path(host_dir) / "datasets" / "train"
    sub_dir.mkdir(parents=True, exist_ok=True)
    (sub_dir / "data.csv").write_text("id,value\n1,100\n2,200\n3,300\n")

    print(f"  宿主机路径：{host_dir}")
    print(f"  子路径    ：datasets/train")
    print(f"  挂载路径  ：/mnt/training-data")

    sandbox = await Sandbox.create(
        image=image,
        connection_config=config,
        timeout=timedelta(minutes=2),
        volumes=[
            Volume(
                name="training-data",
                host=Host(path=host_dir),
                mountPath="/mnt/training-data",
                subPath="datasets/train",
                readOnly=True,
            ),
        ],
    )

    async with sandbox:
        try:
            # List the mounted subdirectory
            print("\n  [1] 列出子路径挂载内容：")
            await print_exec(sandbox, "ls -la /mnt/training-data/")

            # Read the CSV data
            print("\n  [2] 读取 data.csv：")
            await print_exec(sandbox, "cat /mnt/training-data/data.csv")

        finally:
            await sandbox.kill()

    print("\n  场景三完成。")


async def main() -> None:
    domain = os.getenv("SANDBOX_DOMAIN", "localhost:8080")
    api_key = os.getenv("SANDBOX_API_KEY")
    image = os.getenv("SANDBOX_IMAGE", "ubuntu")
    host_dir = os.getenv("HOST_VOLUME_PATH", "")

    # If no host path specified, create a temporary directory with sample data
    if not host_dir:
        host_dir = tempfile.mkdtemp(prefix="opensandbox-vol-")
        print(f"未设置 HOST_VOLUME_PATH，使用临时目录：{host_dir}")
        marker = Path(host_dir) / "marker.txt"
        marker.write_text("hello-from-host\n")
        print(f"已创建标记文件：{marker}")
    else:
        print(f"使用 HOST_VOLUME_PATH：{host_dir}")

    config = ConnectionConfig(
        domain=domain,
        api_key=api_key,
        request_timeout=timedelta(minutes=3),
    )

    print(f"\nOpenSandbox 服务器：{config.domain}")
    print(f"沙箱镜像          ：{image}")
    print(f"宿主机挂载路径     ：{host_dir}")

    await demo_readwrite_mount(config, image, host_dir)
    await demo_readonly_mount(config, image, host_dir)
    await demo_subpath_mount(config, image, host_dir)

    print("\n" + "=" * 60)
    print("所有场景均已成功完成！")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
