"""
Fleet 配置解析器。

解析 fleet.yaml，验证结构，支持环境变量替换和网络策略继承。
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator


class AgentIdentity(BaseModel):
    name: str


class AgentTemplate(BaseModel):
    id: str
    model: str
    identity: AgentIdentity | None = None
    skills: list[str] = Field(default_factory=list)
    tools: dict[str, Any] | None = None


class JCLinkConfig(BaseModel):
    token: str
    base_url: str | None = None
    group_policy: str = "open"
    history_limit: int = 20


class DeploymentTemplate(BaseModel):
    agent: AgentTemplate
    jclink: JCLinkConfig


class EgressRule(BaseModel):
    action: str = "allow"
    target: str


class NetworkPolicyConfig(BaseModel):
    default_action: str = Field(default="deny", alias="defaultAction")
    egress: list[EgressRule] = Field(default_factory=list)
    extends: str | None = None

    model_config = {"populate_by_name": True}


class HealthConfig(BaseModel):
    startup_timeout: int = 60
    check_interval: int = 30
    liveness_failures: int = 3
    readiness_endpoint: str = "/health"


class DeploymentConfig(BaseModel):
    name: str
    replicas: int = 1
    image: str | None = None
    timeout: int | None = None
    network_policy: str | None = None
    template: DeploymentTemplate

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not re.match(r"^[a-z0-9][a-z0-9\-]*[a-z0-9]$", v) and len(v) > 1:
            if not re.match(r"^[a-z0-9\-]+$", v):
                raise ValueError(f"Deployment name must be lowercase alphanumeric with hyphens: {v}")
        return v


class FleetDefaults(BaseModel):
    image: str = "jcdo:local"
    timeout: int = 3600
    sandbox_server: str = "http://localhost:8310"
    jclink_base_url: str = ""


class FleetConfig(BaseModel):
    """fleet.yaml 的完整结构。"""

    api_version: str = Field(default="jcsandbox/v1", alias="apiVersion")
    kind: str = "Fleet"
    defaults: FleetDefaults = Field(default_factory=FleetDefaults)
    network_policies: dict[str, NetworkPolicyConfig] = Field(default_factory=dict)
    deployments: list[DeploymentConfig] = Field(default_factory=list)
    health: HealthConfig = Field(default_factory=HealthConfig)

    model_config = {"populate_by_name": True}


def _substitute_env_vars(text: str) -> str:
    """替换 ${VAR} 和 ${VAR:-default} 格式的环境变量引用。"""

    def replacer(match: re.Match) -> str:
        var_expr = match.group(1)
        if ":-" in var_expr:
            var_name, default_val = var_expr.split(":-", 1)
            return os.environ.get(var_name.strip(), default_val)
        return os.environ.get(var_expr.strip(), match.group(0))

    return re.sub(r"\$\{([^}]+)\}", replacer, text)


def _resolve_network_policy(
    name: str,
    policies: dict[str, NetworkPolicyConfig],
    visited: set[str] | None = None,
) -> NetworkPolicyConfig:
    """解析网络策略继承链（extends），合并 egress 规则。"""
    if visited is None:
        visited = set()
    if name in visited:
        raise ValueError(f"Circular network policy inheritance: {name}")
    visited.add(name)

    policy = policies.get(name)
    if policy is None:
        raise ValueError(f"Unknown network policy: {name}")

    if policy.extends is None:
        return policy

    parent = _resolve_network_policy(policy.extends, policies, visited)
    merged_egress = list(parent.egress) + list(policy.egress)
    return NetworkPolicyConfig(
        defaultAction=policy.default_action,
        egress=merged_egress,
    )


def load_fleet_config(path: str | Path) -> FleetConfig:
    """从 YAML 文件加载 fleet 配置。"""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Fleet config not found: {path}")

    raw_text = path.read_text(encoding="utf-8")
    substituted = _substitute_env_vars(raw_text)
    data = yaml.safe_load(substituted)
    if not isinstance(data, dict):
        raise ValueError(f"Invalid fleet config: expected a mapping, got {type(data).__name__}")

    return FleetConfig.model_validate(data)


def resolve_deployment_network_policy(
    deployment: DeploymentConfig,
    policies: dict[str, NetworkPolicyConfig],
) -> NetworkPolicyConfig | None:
    """为 deployment 解析最终的网络策略（含继承）。"""
    if deployment.network_policy is None:
        return None
    return _resolve_network_policy(deployment.network_policy, policies)
