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
import os
from datetime import timedelta

from code_interpreter import CodeInterpreter, SupportedLanguage
from opensandbox import Sandbox
from opensandbox.config import ConnectionConfig


async def main() -> None:
    domain = os.getenv("SANDBOX_DOMAIN", "localhost:8080")
    api_key = os.getenv("SANDBOX_API_KEY")
    image = os.getenv(
        "SANDBOX_IMAGE",
        "sandbox-registry.cn-zhangjiakou.cr.aliyuncs.com/opensandbox/code-interpreter:v1.0.1",
    )

    config = ConnectionConfig(
        domain=domain,
        api_key=api_key,
        request_timeout=timedelta(seconds=60),
    )

    sandbox = await Sandbox.create(
        image,
        connection_config=config,
        entrypoint=["/opt/opensandbox/code-interpreter.sh"]
    )

    async with sandbox:
        interpreter = await CodeInterpreter.create(sandbox=sandbox)

        # Python 示例：输出运行时信息并返回简单计算结果
        py_exec = await interpreter.codes.run(
            "import platform\n"
            "print('Hello from Python!')\n"
            "result = {'py': platform.python_version(), 'sum': 2 + 2}\n"
            "result",
            language=SupportedLanguage.PYTHON,
        )
        print("\n=== Python 示例 ===")
        for msg in py_exec.logs.stdout:
            print(f"[Python 输出] {msg.text}")
        if py_exec.result:
            for res in py_exec.result:
                print(f"[Python 返回值] {res.text}")

        # Java 示例：打印到标准输出并返回计算结果
        java_exec = await interpreter.codes.run(
            "System.out.println(\"Hello from Java!\");\n"
            "int result = 2 + 3;\n"
            "System.out.println(\"2 + 3 = \" + result);\n"
            "result",
            language=SupportedLanguage.JAVA,
        )
        print("\n=== Java 示例 ===")
        for msg in java_exec.logs.stdout:
            print(f"[Java 输出] {msg.text}")
        if java_exec.result:
            for res in java_exec.result:
                print(f"[Java 返回值] {res.text}")
        if java_exec.error:
            print(f"[Java 错误] {java_exec.error.name}: {java_exec.error.value}")

        # Go 示例：演示 main 函数结构并打印日志
        go_exec = await interpreter.codes.run(
            "package main\n"
            "import \"fmt\"\n"
            "func main() {\n"
            "    fmt.Println(\"Hello from Go!\")\n"
            "    sum := 3 + 4\n"
            "    fmt.Println(\"3 + 4 =\", sum)\n"
            "}",
            language=SupportedLanguage.GO,
        )
        print("\n=== Go 示例 ===")
        for msg in go_exec.logs.stdout:
            print(f"[Go 输出] {msg.text}")
        if go_exec.error:
            print(f"[Go 错误] {go_exec.error.name}: {go_exec.error.value}")

        # TypeScript 示例：使用类型声明并对数组求和
        ts_exec = await interpreter.codes.run(
            "console.log('Hello from TypeScript!');\n"
            "const nums: number[] = [1, 2, 3];\n"
            "console.log('sum =', nums.reduce((a, b) => a + b, 0));",
            language=SupportedLanguage.TYPESCRIPT,
        )
        print("\n=== TypeScript 示例 ===")
        for msg in ts_exec.logs.stdout:
            print(f"[TypeScript 输出] {msg.text}")
        if ts_exec.error:
            print(f"[TypeScript 错误] {ts_exec.error.name}: {ts_exec.error.value}")

        await sandbox.kill()


if __name__ == "__main__":
    asyncio.run(main())
