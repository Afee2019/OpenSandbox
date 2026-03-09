"""
jcdo.json 配置生成器。

从 fleet.yaml 的 deployment template 生成每个实例的 jcdo.json 配置。
"""

from __future__ import annotations

import json
from typing import Any

from .config import DeploymentConfig, FleetConfig


def generate_jcdo_config(
    fleet: FleetConfig,
    deployment: DeploymentConfig,
    instance_index: int,
) -> dict[str, Any]:
    """为指定 deployment 的第 N 个实例生成 jcdo.json 内容。"""
    tmpl = deployment.template
    agent = tmpl.agent
    jclink = tmpl.jclink

    jclink_base_url = jclink.base_url or fleet.defaults.jclink_base_url

    config: dict[str, Any] = {
        "agents": {
            "list": [
                {
                    "id": agent.id,
                    "model": agent.model,
                }
            ]
        },
    }

    agent_entry = config["agents"]["list"][0]

    if agent.identity:
        agent_entry["identity"] = {"name": agent.identity.name}

    if agent.skills:
        agent_entry["skills"] = agent.skills

    if agent.tools:
        agent_entry["tools"] = agent.tools

    # JCLink channel config
    if jclink_base_url and jclink.token:
        config["channels"] = {
            "jclink": {
                "enabled": True,
                "token": jclink.token,
                "baseUrl": jclink_base_url,
                "groupPolicy": jclink.group_policy,
                "historyLimit": jclink.history_limit,
            }
        }

    return config


def generate_jcdo_config_json(
    fleet: FleetConfig,
    deployment: DeploymentConfig,
    instance_index: int,
) -> str:
    """生成 jcdo.json 字符串。"""
    config = generate_jcdo_config(fleet, deployment, instance_index)
    return json.dumps(config, indent=2, ensure_ascii=False)
