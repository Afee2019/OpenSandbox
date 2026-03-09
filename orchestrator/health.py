"""
健康监控模块。

实现对 jcdo 沙箱实例的多级健康检查：
1. 容器存活（通过 OpenSandbox API 查询沙箱状态）
2. jcdo 就绪（HTTP GET 健康检查端点）
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import httpx

from .models import BotInstance, InstanceHealth

if TYPE_CHECKING:
    from opensandbox.config import ConnectionConfigSync

logger = logging.getLogger("jcsandbox.health")


class HealthMonitor:
    """Bot 实例健康检查器。"""

    def __init__(
        self,
        connection_config: ConnectionConfigSync,
        *,
        readiness_endpoint: str = "/health",
        liveness_failures: int = 3,
    ):
        self.connection_config = connection_config
        self.readiness_endpoint = readiness_endpoint
        self.liveness_failures = liveness_failures
        self._http = httpx.Client(timeout=5)

    def close(self) -> None:
        self._http.close()

    def check_instance(self, instance: BotInstance) -> InstanceHealth:
        """检查单个实例的健康状态。"""
        if instance.sandbox_id is None:
            instance.mark_dead("no sandbox id")
            return InstanceHealth.DEAD

        # 1. 检查沙箱是否还在运行
        sandbox_alive = self._check_sandbox_alive(instance.sandbox_id)
        if not sandbox_alive:
            instance.mark_dead("sandbox not running")
            return InstanceHealth.DEAD

        # 2. 检查 jcdo 是否就绪
        jcdo_ready = self._check_jcdo_ready(instance)
        if jcdo_ready:
            instance.mark_ready()
            return InstanceHealth.READY
        else:
            instance.mark_not_ready("jcdo health check failed")
            return InstanceHealth.NOT_READY

    def _check_sandbox_alive(self, sandbox_id: str) -> bool:
        """通过 OpenSandbox API 检查沙箱是否在运行。"""
        try:
            from opensandbox import SandboxSync

            sbx = SandboxSync.connect(
                sandbox_id,
                connection_config=self.connection_config,
                skip_health_check=True,
            )
            info = sbx.get_info()
            return info.status.state == "Running"
        except Exception as exc:
            logger.debug("sandbox alive check failed for %s: %s", sandbox_id, exc)
            return False

    def _check_jcdo_ready(self, instance: BotInstance) -> bool:
        """通过 HTTP 端点检查 jcdo 是否就绪。"""
        if instance.sandbox_id is None:
            return False

        try:
            from opensandbox import SandboxSync

            sbx = SandboxSync.connect(
                instance.sandbox_id,
                connection_config=self.connection_config,
                skip_health_check=True,
            )
            endpoint = sbx.get_endpoint(8255)
            url = f"http://{endpoint.endpoint}{self.readiness_endpoint}"
            resp = self._http.get(url)
            return resp.status_code == 200
        except Exception as exc:
            logger.debug("jcdo readiness check failed for %s: %s", instance.display_name, exc)
            return False

    def should_replace(self, instance: BotInstance) -> bool:
        """判断实例是否应该被替换。"""
        if instance.health == InstanceHealth.DEAD:
            return True
        if (
            instance.health == InstanceHealth.NOT_READY
            and instance.consecutive_failures >= self.liveness_failures
        ):
            return True
        return False
