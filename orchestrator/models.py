"""
Bot 实例状态模型。

跟踪每个 jcdo 沙箱实例的运行状态、健康状况和归属关系。
"""

from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import Any


class InstanceHealth(str, enum.Enum):
    UNKNOWN = "unknown"
    STARTING = "starting"
    READY = "ready"
    NOT_READY = "not_ready"
    DEAD = "dead"


class BotInstance:
    """单个 jcdo 沙箱实例的运行时状态。"""

    def __init__(
        self,
        *,
        deployment_name: str,
        instance_index: int,
        sandbox_id: str | None = None,
    ):
        self.deployment_name = deployment_name
        self.instance_index = instance_index
        self.sandbox_id = sandbox_id

        self.health = InstanceHealth.UNKNOWN
        self.consecutive_failures = 0
        self.created_at = datetime.now(timezone.utc)
        self.last_check: datetime | None = None
        self.ws_endpoint: str | None = None
        self.error: str | None = None

    @property
    def display_name(self) -> str:
        return f"{self.deployment_name}-{self.instance_index}"

    @property
    def is_alive(self) -> bool:
        return self.health in (InstanceHealth.READY, InstanceHealth.NOT_READY, InstanceHealth.STARTING)

    def mark_ready(self) -> None:
        self.health = InstanceHealth.READY
        self.consecutive_failures = 0
        self.last_check = datetime.now(timezone.utc)
        self.error = None

    def mark_not_ready(self, reason: str = "") -> None:
        self.health = InstanceHealth.NOT_READY
        self.consecutive_failures += 1
        self.last_check = datetime.now(timezone.utc)
        self.error = reason

    def mark_dead(self, reason: str = "") -> None:
        self.health = InstanceHealth.DEAD
        self.consecutive_failures += 1
        self.last_check = datetime.now(timezone.utc)
        self.error = reason

    def uptime_str(self) -> str:
        delta = datetime.now(timezone.utc) - self.created_at
        total_seconds = int(delta.total_seconds())
        if total_seconds < 60:
            return f"{total_seconds}s"
        if total_seconds < 3600:
            return f"{total_seconds // 60}m{total_seconds % 60}s"
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        return f"{hours}h{minutes}m"

    def to_dict(self) -> dict[str, Any]:
        return {
            "deployment": self.deployment_name,
            "index": self.instance_index,
            "name": self.display_name,
            "sandbox_id": self.sandbox_id,
            "health": self.health.value,
            "consecutive_failures": self.consecutive_failures,
            "created_at": self.created_at.isoformat(),
            "last_check": self.last_check.isoformat() if self.last_check else None,
            "error": self.error,
        }
