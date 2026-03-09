"""
调谐循环（Reconciliation Loop）。

核心编排逻辑：持续对比期望状态与实际状态，驱动创建/销毁/替换操作。
"""

from __future__ import annotations

import logging
import tempfile
import time
from datetime import timedelta
from pathlib import Path
from typing import Any

import requests
from opensandbox import SandboxSync
from opensandbox.config import ConnectionConfigSync
from opensandbox.models.sandboxes import Host, NetworkPolicy, NetworkRule, Volume

from .config import (
    DeploymentConfig,
    FleetConfig,
    resolve_deployment_network_policy,
)
from .health import HealthMonitor
from .jcdo_config import generate_jcdo_config_json
from .models import BotInstance, InstanceHealth

logger = logging.getLogger("jcsandbox.reconciler")

# jcdo gateway 内部端口
GATEWAY_PORT = 8255

# 配置文件在容器中的只读挂载路径
READONLY_CONFIG_MOUNT = "/home/node/.jcdo-host"


def _build_entrypoint() -> str:
    """构建 jcdo 容器的启动命令。"""
    return (
        f"sh -c '"
        f"mkdir -p /home/node/.jcdo && "
        f"cp {READONLY_CONFIG_MOUNT}/jcdo.json /home/node/.jcdo/jcdo.json && "
        f"node dist/index.js gateway --bind=lan --port {GATEWAY_PORT} --allow-unconfigured --verbose"
        f"'"
    )


def _jcdo_health_check(sbx: SandboxSync) -> bool:
    """沙箱创建后的健康检查回调。"""
    try:
        endpoint = sbx.get_endpoint(GATEWAY_PORT)
        url = f"http://{endpoint.endpoint}"
        for _ in range(150):  # ~30 秒
            try:
                resp = requests.get(url, timeout=1)
                if resp.status_code == 200:
                    return True
            except Exception:
                pass
            time.sleep(0.2)
        return False
    except Exception:
        return False


class Reconciler:
    """Bot 军团调谐控制器。"""

    def __init__(
        self,
        fleet: FleetConfig,
        connection_config: ConnectionConfigSync,
        health_monitor: HealthMonitor,
        *,
        config_dir: Path | None = None,
    ):
        self.fleet = fleet
        self.connection_config = connection_config
        self.health_monitor = health_monitor
        # 临时配置文件目录
        self.config_dir = config_dir or Path(tempfile.mkdtemp(prefix="jcsandbox-"))

        # deployment_name → list[BotInstance]
        self.instances: dict[str, list[BotInstance]] = {}
        for dep in fleet.deployments:
            self.instances[dep.name] = []

        self._running = False
        self._events: list[dict[str, Any]] = []

    @property
    def all_instances(self) -> list[BotInstance]:
        result = []
        for inst_list in self.instances.values():
            result.extend(inst_list)
        return result

    def log_event(self, instance_name: str, message: str) -> None:
        from datetime import datetime, timezone

        event = {
            "time": datetime.now(timezone.utc).strftime("%H:%M:%S"),
            "instance": instance_name,
            "message": message,
        }
        self._events.append(event)
        # 只保留最近 50 条
        if len(self._events) > 50:
            self._events = self._events[-50:]
        logger.info("[%s] %s", instance_name, message)

    def reconcile_once(self) -> None:
        """执行一次调谐循环。"""
        for deployment in self.fleet.deployments:
            self._reconcile_deployment(deployment)

    def _reconcile_deployment(self, deployment: DeploymentConfig) -> None:
        """调谐单个 deployment。"""
        instances = self.instances.get(deployment.name, [])

        # 1. 健康检查所有实例
        for inst in instances:
            if inst.health != InstanceHealth.STARTING:
                self.health_monitor.check_instance(inst)

        # 2. 清理死亡实例（需要替换的）
        to_replace = [inst for inst in instances if self.health_monitor.should_replace(inst)]
        for inst in to_replace:
            self.log_event(inst.display_name, f"Replacing (health={inst.health.value}, failures={inst.consecutive_failures})")
            self._destroy_instance(inst)
            instances.remove(inst)

        # 3. 计算差额
        alive_count = len(instances)
        desired = deployment.replicas

        # 4. 扩容
        if alive_count < desired:
            for _ in range(desired - alive_count):
                idx = self._next_index(deployment.name)
                self._create_instance(deployment, idx)

        # 5. 缩容
        elif alive_count > desired:
            excess = alive_count - desired
            # 优先缩减不健康的，然后是最新创建的
            candidates = sorted(
                instances,
                key=lambda i: (i.health == InstanceHealth.READY, i.created_at),
            )
            for inst in candidates[:excess]:
                self.log_event(inst.display_name, "Scaling down")
                self._destroy_instance(inst)
                instances.remove(inst)

    def _next_index(self, deployment_name: str) -> int:
        """生成下一个实例索引。"""
        existing = self.instances.get(deployment_name, [])
        used = {inst.instance_index for inst in existing}
        idx = 0
        while idx in used:
            idx += 1
        return idx

    def _create_instance(self, deployment: DeploymentConfig, index: int) -> None:
        """创建一个新的 jcdo 沙箱实例。"""
        instance = BotInstance(
            deployment_name=deployment.name,
            instance_index=index,
        )
        instance.health = InstanceHealth.STARTING
        self.instances.setdefault(deployment.name, []).append(instance)

        self.log_event(instance.display_name, "Creating sandbox")

        try:
            # 生成 jcdo.json 配置
            config_json = generate_jcdo_config_json(self.fleet, deployment, index)
            config_path = self.config_dir / deployment.name / str(index)
            config_path.mkdir(parents=True, exist_ok=True)
            config_file = config_path / "jcdo.json"
            config_file.write_text(config_json, encoding="utf-8")

            # 构建沙箱参数
            image = deployment.image or self.fleet.defaults.image
            timeout_seconds = deployment.timeout or self.fleet.defaults.timeout

            volumes = [
                Volume(
                    name="jcdo-config",
                    host=Host(path=str(config_path)),
                    mountPath=READONLY_CONFIG_MOUNT,
                    readOnly=True,
                ),
            ]

            # 挂载宿主机 workspace（如果存在）
            workspace_dir = Path.home() / ".jcdo" / "workspace"
            if workspace_dir.exists():
                volumes.append(
                    Volume(
                        name="jcdo-workspace",
                        host=Host(path=str(workspace_dir)),
                        mountPath="/home/node/.jcdo-workspace-host",
                        readOnly=True,
                    ),
                )

            # 网络策略
            np = self._build_network_policy(deployment)

            # 环境变量
            gateway_token = f"sandbox-{deployment.name}-{index}"
            env: dict[str, str] = {
                "NODE_ENV": "production",
                "JCDO_GATEWAY_TOKEN": gateway_token,
            }

            sandbox = SandboxSync.create(
                image=image,
                timeout=timedelta(seconds=timeout_seconds),
                metadata={
                    "jcsandbox.deployment": deployment.name,
                    "jcsandbox.index": str(index),
                    "jcsandbox.managed": "true",
                },
                entrypoint=[_build_entrypoint()],
                connection_config=self.connection_config,
                health_check=_jcdo_health_check,
                health_check_polling_interval=timedelta(milliseconds=500),
                ready_timeout=timedelta(seconds=self.fleet.health.startup_timeout),
                env=env,
                volumes=volumes,
                network_policy=np,
                skip_health_check=False,
            )

            instance.sandbox_id = sandbox.id

            # 获取 WebSocket 端点
            try:
                ep = sandbox.get_endpoint(GATEWAY_PORT)
                instance.ws_endpoint = f"ws://{ep.endpoint}"
            except Exception:
                pass

            instance.mark_ready()
            self.log_event(instance.display_name, f"Ready (sandbox={sandbox.id[:8]})")

        except Exception as exc:
            instance.mark_dead(str(exc))
            self.log_event(instance.display_name, f"Creation failed: {exc}")
            # 从实例列表中移除失败的
            instances = self.instances.get(deployment.name, [])
            if instance in instances:
                instances.remove(instance)

    def _destroy_instance(self, instance: BotInstance) -> None:
        """销毁一个沙箱实例。"""
        if instance.sandbox_id is None:
            return

        try:
            sbx = SandboxSync.connect(
                instance.sandbox_id,
                connection_config=self.connection_config,
                skip_health_check=True,
            )
            sbx.kill()
            self.log_event(instance.display_name, f"Destroyed (sandbox={instance.sandbox_id[:8]})")
        except Exception as exc:
            self.log_event(instance.display_name, f"Destroy failed: {exc}")

    def _build_network_policy(self, deployment: DeploymentConfig) -> NetworkPolicy | None:
        """构建沙箱网络策略。"""
        resolved = resolve_deployment_network_policy(deployment, self.fleet.network_policies)
        if resolved is None:
            return None

        return NetworkPolicy(
            defaultAction=resolved.default_action,
            egress=[
                NetworkRule(action=rule.action, target=rule.target)
                for rule in resolved.egress
            ],
        )

    def renew_all(self) -> None:
        """续期所有运行中的沙箱，防止 TTL 到期。"""
        for instance in self.all_instances:
            if instance.sandbox_id and instance.is_alive:
                try:
                    sbx = SandboxSync.connect(
                        instance.sandbox_id,
                        connection_config=self.connection_config,
                        skip_health_check=True,
                    )
                    timeout = self.fleet.defaults.timeout
                    sbx.renew(timedelta(seconds=timeout))
                    logger.debug("Renewed %s for %ds", instance.display_name, timeout)
                except Exception as exc:
                    logger.warning("Failed to renew %s: %s", instance.display_name, exc)

    def shutdown(self) -> None:
        """优雅关闭：销毁所有实例。"""
        self._running = False
        logger.info("Shutting down fleet...")
        for instances in self.instances.values():
            for inst in list(instances):
                self._destroy_instance(inst)
            instances.clear()

    def run_loop(self, interval: int | None = None) -> None:
        """运行调谐主循环（阻塞）。"""
        if interval is None:
            interval = self.fleet.health.check_interval
        self._running = True

        logger.info("Starting reconciliation loop (interval=%ds)", interval)

        # 首次调谐：创建所有期望的实例
        self.reconcile_once()

        renew_counter = 0
        renew_interval = max(1, (self.fleet.defaults.timeout // 2) // interval)

        while self._running:
            try:
                time.sleep(interval)
                if not self._running:
                    break

                self.reconcile_once()

                # 定期续期
                renew_counter += 1
                if renew_counter >= renew_interval:
                    self.renew_all()
                    renew_counter = 0

            except KeyboardInterrupt:
                logger.info("Interrupted")
                break
            except Exception as exc:
                logger.error("Reconciliation error: %s", exc)
