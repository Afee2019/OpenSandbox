"""
JcSandbox CLI — Bot 军团编排命令行工具。

用法:
    jcsandbox up fleet.yaml          # 启动军团
    jcsandbox status fleet.yaml      # 查看状态
    jcsandbox down fleet.yaml        # 停止军团
    jcsandbox scale fleet.yaml <deployment> --replicas=N
"""

from __future__ import annotations

import logging
import signal
import sys
from pathlib import Path

import typer
from opensandbox.config import ConnectionConfigSync

from .config import load_fleet_config
from .health import HealthMonitor
from .reconciler import Reconciler

app = typer.Typer(
    name="jcsandbox",
    help="JcSandbox — Bot 军团编排控制器",
    add_completion=False,
)

# 全局 reconciler 引用（用于 signal handler）
_reconciler: Reconciler | None = None


def _setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s  %(levelname)-5s  %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )


def _build_reconciler(fleet_path: str, config_dir: str | None = None) -> Reconciler:
    fleet = load_fleet_config(fleet_path)

    # 从 fleet.yaml 的 defaults.sandbox_server 构建连接配置
    server_url = fleet.defaults.sandbox_server
    # 解析 domain（去掉 http:// 前缀）
    domain = server_url.replace("http://", "").replace("https://", "")
    protocol = "https" if server_url.startswith("https") else "http"

    connection_config = ConnectionConfigSync(
        domain=domain,
        protocol=protocol,
    )

    health_monitor = HealthMonitor(
        connection_config,
        readiness_endpoint=fleet.health.readiness_endpoint,
        liveness_failures=fleet.health.liveness_failures,
    )

    cd = Path(config_dir) if config_dir else None

    return Reconciler(
        fleet=fleet,
        connection_config=connection_config,
        health_monitor=health_monitor,
        config_dir=cd,
    )


@app.command()
def up(
    fleet_path: str = typer.Argument(..., help="fleet.yaml 配置文件路径"),
    config_dir: str | None = typer.Option(None, "--config-dir", "-c", help="生成的 jcdo 配置存储目录"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="详细日志"),
) -> None:
    """启动 Bot 军团（阻塞运行，Ctrl+C 停止）。"""
    global _reconciler
    _setup_logging(verbose)
    logger = logging.getLogger("jcsandbox")

    fleet = load_fleet_config(fleet_path)
    total_bots = sum(d.replicas for d in fleet.deployments)
    logger.info("Fleet: %d deployments, %d total bots", len(fleet.deployments), total_bots)

    for dep in fleet.deployments:
        logger.info("  %s: replicas=%d, image=%s", dep.name, dep.replicas, dep.image or fleet.defaults.image)

    reconciler = _build_reconciler(fleet_path, config_dir)
    _reconciler = reconciler

    def handle_signal(signum: int, frame: object) -> None:
        logger.info("Received signal %d, shutting down...", signum)
        reconciler.shutdown()
        reconciler.health_monitor.close()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        reconciler.run_loop()
    except KeyboardInterrupt:
        pass
    finally:
        reconciler.shutdown()
        reconciler.health_monitor.close()


@app.command()
def status(
    fleet_path: str = typer.Argument(..., help="fleet.yaml 配置文件路径"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """查看当前军团运行状态（快照）。"""
    _setup_logging(verbose)

    fleet = load_fleet_config(fleet_path)

    # 通过 OpenSandbox API 查询由 jcsandbox 管理的沙箱
    from opensandbox import SandboxManagerSync
    from opensandbox.models.sandboxes import SandboxFilter

    domain = fleet.defaults.sandbox_server.replace("http://", "").replace("https://", "")
    protocol = "https" if fleet.defaults.sandbox_server.startswith("https") else "http"
    conn = ConnectionConfigSync(domain=domain, protocol=protocol)

    manager = SandboxManagerSync.create(connection_config=conn)
    result = manager.list_sandbox_infos(
        SandboxFilter(
            metadata={"jcsandbox.managed": "true"},
        )
    )

    # 按 deployment 分组
    by_deployment: dict[str, list] = {}
    for info in result.sandbox_infos:
        meta = info.metadata or {}
        dep_name = meta.get("jcsandbox.deployment", "unknown")
        by_deployment.setdefault(dep_name, []).append(info)

    # 打印表格
    print()
    print(f"  {'DEPLOYMENT':<22} {'DESIRED':>7} {'ACTUAL':>6} {'RUNNING':>7}  STATUS")
    print(f"  {'─' * 22} {'─' * 7} {'─' * 6} {'─' * 7}  {'─' * 12}")

    for dep in fleet.deployments:
        infos = by_deployment.get(dep.name, [])
        running = sum(1 for i in infos if i.status.state == "Running")
        total = len(infos)
        if running >= dep.replicas:
            status_str = "Healthy"
            icon = "\033[32m●\033[0m"  # green
        elif running > 0:
            status_str = "Degraded"
            icon = "\033[33m●\033[0m"  # yellow
        else:
            status_str = "Down"
            icon = "\033[31m●\033[0m"  # red

        print(f"  {dep.name:<22} {dep.replicas:>7} {total:>6} {running:>7}  {icon} {status_str}")

    print()

    # 实例明细
    if result.sandbox_infos:
        print(f"  {'INSTANCE':<28} {'STATE':<12} {'SANDBOX ID':<14} {'EXPIRES'}")
        print(f"  {'─' * 28} {'─' * 12} {'─' * 14} {'─' * 20}")

        for info in result.sandbox_infos:
            meta = info.metadata or {}
            dep = meta.get("jcsandbox.deployment", "?")
            idx = meta.get("jcsandbox.index", "?")
            name = f"{dep}-{idx}"
            state = info.status.state
            sid = info.id[:12]
            expires = info.expires_at.strftime("%H:%M:%S") if info.expires_at else "?"
            print(f"  {name:<28} {state:<12} {sid:<14} {expires}")

        print()

    manager.close()


@app.command()
def down(
    fleet_path: str = typer.Argument(..., help="fleet.yaml 配置文件路径"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """停止并销毁所有由 JcSandbox 管理的沙箱。"""
    _setup_logging(verbose)
    logger = logging.getLogger("jcsandbox")

    fleet = load_fleet_config(fleet_path)
    domain = fleet.defaults.sandbox_server.replace("http://", "").replace("https://", "")
    protocol = "https" if fleet.defaults.sandbox_server.startswith("https") else "http"
    conn = ConnectionConfigSync(domain=domain, protocol=protocol)

    from opensandbox import SandboxManagerSync, SandboxSync
    from opensandbox.models.sandboxes import SandboxFilter

    manager = SandboxManagerSync.create(connection_config=conn)
    result = manager.list_sandbox_infos(
        SandboxFilter(metadata={"jcsandbox.managed": "true"})
    )

    if not result.sandbox_infos:
        logger.info("No managed sandboxes found.")
        manager.close()
        return

    logger.info("Destroying %d managed sandbox(es)...", len(result.sandbox_infos))

    for info in result.sandbox_infos:
        meta = info.metadata or {}
        name = f"{meta.get('jcsandbox.deployment', '?')}-{meta.get('jcsandbox.index', '?')}"
        try:
            sbx = SandboxSync.connect(info.id, connection_config=conn, skip_health_check=True)
            sbx.kill()
            logger.info("  Destroyed %s (sandbox=%s)", name, info.id[:8])
        except Exception as exc:
            logger.warning("  Failed to destroy %s: %s", name, exc)

    manager.close()
    logger.info("Done.")


@app.command()
def scale(
    fleet_path: str = typer.Argument(..., help="fleet.yaml 配置文件路径"),
    deployment: str = typer.Argument(..., help="Deployment 名称"),
    replicas: int = typer.Option(..., "--replicas", "-r", help="目标副本数"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """动态调整 deployment 的副本数（需要 up 命令正在运行）。

    注意：此命令修改 fleet.yaml 中的 replicas 值，
    下次 up 命令启动时会使用新的值。当前运行中的调谐循环
    会在下一个检查周期自动感知变化。
    """
    _setup_logging(verbose)
    logger = logging.getLogger("jcsandbox")

    fleet = load_fleet_config(fleet_path)
    dep = next((d for d in fleet.deployments if d.name == deployment), None)
    if dep is None:
        logger.error("Deployment '%s' not found in %s", deployment, fleet_path)
        raise typer.Exit(1)

    old_replicas = dep.replicas
    logger.info("Scaling %s: %d → %d", deployment, old_replicas, replicas)

    # 读取原始 YAML 并修改 replicas
    import yaml

    path = Path(fleet_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    for d in data.get("deployments", []):
        if d.get("name") == deployment:
            d["replicas"] = replicas
            break

    path.write_text(yaml.dump(data, default_flow_style=False, allow_unicode=True), encoding="utf-8")
    logger.info("Updated %s. Changes take effect on next reconciliation cycle.", fleet_path)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
