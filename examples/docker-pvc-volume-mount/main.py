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
Docker PVC (Named Volume) Mount Example
========================================

Demonstrates how to mount Docker named volumes into sandbox containers using
the OpenSandbox ``pvc`` backend.  In Docker runtime the ``pvc`` backend maps
``claimName`` to a Docker named volume -- providing a more convenient and
secure alternative to host-path bind mounts for sharing data across sandboxes.

Four scenarios are demonstrated:

1. **Read-write mount**        - Mount a named volume for bidirectional file I/O.
2. **Read-only mount**         - Mount a named volume as read-only.
3. **Cross-sandbox sharing**   - Two sandboxes share data through the same named
   volume without exposing any host path.
4. **SubPath mount**           - Mount only a subdirectory of a named volume,
   keeping the same API as Kubernetes PVC subPath.

Prerequisites:
- OpenSandbox server running with Docker runtime
- Docker named volume created before running this script (see README.md)
"""

import asyncio
import os
import subprocess
from datetime import timedelta

from opensandbox import Sandbox
from opensandbox.config import ConnectionConfig

try:
    from opensandbox.models.sandboxes import PVC, Volume
except ImportError:
    print(
        "错误：当前安装的 opensandbox SDK 不包含 Volume/PVC 模型。\n"
        "       Volume 支持需要使用源码中的最新 SDK。\n"
        "       请从本地仓库安装：\n"
        "\n"
        "           pip install -e sdks/sandbox/python\n"
        "\n"
        "       详见 README.md。"
    )
    raise SystemExit(1)


VOLUME_NAME = "opensandbox-pvc-demo"


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


def ensure_named_volume() -> None:
    """Create the Docker named volume and seed it with test data."""
    print(f"  正在确认 Docker 命名卷 '{VOLUME_NAME}' 存在...")
    subprocess.run(
        ["docker", "volume", "rm", VOLUME_NAME],
        capture_output=True,
    )
    subprocess.run(
        ["docker", "volume", "create", VOLUME_NAME],
        check=True,
        capture_output=True,
    )
    # Seed the volume with a marker file and subpath test data
    subprocess.run(
        [
            "docker", "run", "--rm",
            "-v", f"{VOLUME_NAME}:/data",
            "alpine",
            "sh", "-c",
            "echo 'hello-from-named-volume' > /data/marker.txt && "
            "mkdir -p /data/datasets/train && "
            "echo 'id,value' > /data/datasets/train/data.csv && "
            "echo '1,100' >> /data/datasets/train/data.csv && "
            "echo '2,200' >> /data/datasets/train/data.csv",
        ],
        check=True,
        capture_output=True,
    )
    print(f"  已创建卷 '{VOLUME_NAME}'（包含 marker.txt 和 datasets/train/）")


async def demo_readwrite_mount(config: ConnectionConfig, image: str) -> None:
    """
    Scenario 1: Read-write named volume mount.

    Mount a Docker named volume into the sandbox at /mnt/data.
    Write a file inside the sandbox, then read it back to verify.
    """
    print("\n" + "=" * 60)
    print("场景一：PVC（命名卷）读写挂载")
    print("=" * 60)
    print(f"  卷名称    ：{VOLUME_NAME}")
    print(f"  挂载路径  ：/mnt/data")

    sandbox = await Sandbox.create(
        image=image,
        connection_config=config,
        timeout=timedelta(minutes=2),
        volumes=[
            Volume(
                name="demo-data",
                pvc=PVC(claimName=VOLUME_NAME),
                mountPath="/mnt/data",
                readOnly=False,
            ),
        ],
    )

    async with sandbox:
        try:
            # Read the seeded marker file
            print("\n  [1] 读取命名卷中的标记文件：")
            await print_exec(sandbox, "cat /mnt/data/marker.txt")

            # Write a new file
            print("\n  [2] 在沙箱内写入文件：")
            await print_exec(
                sandbox,
                "echo 'written-by-sandbox' > /mnt/data/sandbox-output.txt",
            )
            print("  -> 已写入：/mnt/data/sandbox-output.txt")

            # Read it back
            print("\n  [3] 读取刚写入的文件：")
            await print_exec(sandbox, "cat /mnt/data/sandbox-output.txt")

            # List all files
            print("\n  [4] 列出卷内容：")
            await print_exec(sandbox, "ls -la /mnt/data/")

        finally:
            await sandbox.kill()

    print("\n  场景一完成。")


async def demo_readonly_mount(config: ConnectionConfig, image: str) -> None:
    """
    Scenario 2: Read-only named volume mount.

    Mount the same named volume as read-only.  Verify reads succeed but
    writes are rejected by the container runtime.
    """
    print("\n" + "=" * 60)
    print("场景二：PVC（命名卷）只读挂载")
    print("=" * 60)
    print(f"  卷名称    ：{VOLUME_NAME}")
    print(f"  挂载路径  ：/mnt/readonly")

    sandbox = await Sandbox.create(
        image=image,
        connection_config=config,
        timeout=timedelta(minutes=2),
        volumes=[
            Volume(
                name="readonly-vol",
                pvc=PVC(claimName=VOLUME_NAME),
                mountPath="/mnt/readonly",
                readOnly=True,
            ),
        ],
    )

    async with sandbox:
        try:
            # Read the marker file
            print("\n  [1] 从只读挂载读取 marker.txt：")
            await print_exec(sandbox, "cat /mnt/readonly/marker.txt")

            # Attempt to write (should fail)
            print("\n  [2] 尝试写入（应当失败）：")
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


async def demo_cross_sandbox_sharing(config: ConnectionConfig, image: str) -> None:
    """
    Scenario 3: Cross-sandbox data sharing via named volume.

    Two sandboxes mount the same named volume.  Sandbox A writes a file,
    then Sandbox B reads it -- demonstrating data sharing without any host
    path exposure.
    """
    print("\n" + "=" * 60)
    print("场景三：通过 PVC（命名卷）实现跨沙箱数据共享")
    print("=" * 60)
    print(f"  卷名称：{VOLUME_NAME}")

    volume_spec = Volume(
        name="shared-vol",
        pvc=PVC(claimName=VOLUME_NAME),
        mountPath="/mnt/shared",
        readOnly=False,
    )

    # --- Sandbox A: write ---
    print("\n  [沙箱 A] 正在创建沙箱并写入数据...")
    sandbox_a = await Sandbox.create(
        image=image,
        connection_config=config,
        timeout=timedelta(minutes=2),
        volumes=[volume_spec],
    )
    async with sandbox_a:
        try:
            await print_exec(
                sandbox_a,
                "echo 'message-from-sandbox-a' > /mnt/shared/cross-sandbox.txt",
            )
            print("  [沙箱 A] 已写入 /mnt/shared/cross-sandbox.txt")
        finally:
            await sandbox_a.kill()

    # --- Sandbox B: read ---
    print("\n  [沙箱 B] 正在创建沙箱并读取数据...")
    sandbox_b = await Sandbox.create(
        image=image,
        connection_config=config,
        timeout=timedelta(minutes=2),
        volumes=[volume_spec],
    )
    async with sandbox_b:
        try:
            print("  [沙箱 B] 正在读取沙箱 A 写入的文件：")
            text = await print_exec(sandbox_b, "cat /mnt/shared/cross-sandbox.txt")
            if text and "message-from-sandbox-a" in text:
                print("\n  跨沙箱数据共享验证通过！")
        finally:
            await sandbox_b.kill()

    print("\n  场景三完成。")


async def demo_subpath_mount(config: ConnectionConfig, image: str) -> None:
    """
    Scenario 4: SubPath mount on a named volume.

    Mount only a subdirectory (datasets/train) of the named volume.  The server
    resolves the volume's host-side Mountpoint via ``docker volume inspect`` and
    appends the subPath, producing a standard bind mount.  This keeps the API
    consistent with Kubernetes PVC subPath semantics.
    """
    print("\n" + "=" * 60)
    print("场景四：PVC（命名卷）子路径挂载")
    print("=" * 60)
    print(f"  卷名称    ：{VOLUME_NAME}")
    print(f"  子路径    ：datasets/train")
    print(f"  挂载路径  ：/mnt/training-data")

    sandbox = await Sandbox.create(
        image=image,
        connection_config=config,
        timeout=timedelta(minutes=2),
        volumes=[
            Volume(
                name="train-data",
                pvc=PVC(claimName=VOLUME_NAME),
                mountPath="/mnt/training-data",
                readOnly=True,
                subPath="datasets/train",
            ),
        ],
    )

    async with sandbox:
        try:
            # List contents -- should only show the subpath
            print("\n  [1] 列出子路径挂载内容：")
            await print_exec(sandbox, "ls -la /mnt/training-data/")

            # Read the CSV data
            print("\n  [2] 读取 data.csv：")
            await print_exec(sandbox, "cat /mnt/training-data/data.csv")

            # Verify the root marker.txt is NOT visible (we're inside datasets/train)
            print("\n  [3] 验证卷根路径不可见：")
            result = await sandbox.commands.run("test -f /mnt/training-data/marker.txt && echo FOUND || echo NOT-FOUND")
            text = "\n".join(msg.text for msg in result.logs.stdout)
            print(f"  挂载根路径的 marker.txt：{text}")
            if "NOT-FOUND" in text:
                print("  -> 确认：子路径隔离正常工作")

        finally:
            await sandbox.kill()

    print("\n  场景四完成。")


async def main() -> None:
    domain = os.getenv("SANDBOX_DOMAIN", "localhost:8080")
    api_key = os.getenv("SANDBOX_API_KEY")
    image = os.getenv("SANDBOX_IMAGE", "ubuntu")

    config = ConnectionConfig(
        domain=domain,
        api_key=api_key,
        request_timeout=timedelta(minutes=3),
    )

    print(f"OpenSandbox 服务器：{config.domain}")
    print(f"沙箱镜像          ：{image}")
    print(f"Docker 卷名称      ：{VOLUME_NAME}")

    # Ensure the named volume exists with seed data
    ensure_named_volume()

    await demo_readwrite_mount(config, image)
    await demo_readonly_mount(config, image)
    await demo_cross_sandbox_sharing(config, image)
    await demo_subpath_mount(config, image)

    print("\n" + "=" * 60)
    print("所有场景均已成功完成！")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
