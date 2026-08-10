"""AgentLoop/CMS 观测接入（规划 §4.4）。

- 云接入：配置 `AGENTTEAMS_CMS_*` 一组环境变量，Manager/Worker 自动走 OTLP 上报（官方 docs/cms-integration.md）
- 自建等价物：无云资源时用同一套 env 契约，指标落到本地台账（OTLP 同契约，差一个云 endpoint）

env 清单：
  AGENTTEAMS_CMS_TRACES_ENABLED / AGENTTEAMS_CMS_ENDPOINT / AGENTTEAMS_CMS_LICENSE_KEY
  AGENTTEAMS_CMS_WORKSPACE / AGENTTEAMS_CMS_SERVICE_NAME
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

CMS_ENV = (
    "AGENTTEAMS_CMS_TRACES_ENABLED",
    "AGENTTEAMS_CMS_ENDPOINT",
    "AGENTTEAMS_CMS_LICENSE_KEY",
    "AGENTTEAMS_CMS_WORKSPACE",
    "AGENTTEAMS_CMS_SERVICE_NAME",
)


@dataclass
class CmsConfig:
    """AgentLoop/CMS 配置（从 env 读取，不硬编码）。"""

    traces_enabled: bool = False
    endpoint: str | None = None
    license_key: str | None = None
    workspace: str | None = None
    service_name: str = "servevo"
    configured_vars: list[str] = field(default_factory=list)

    @property
    def cloud_connected(self) -> bool:
        """云接入判定：endpoint + license_key + workspace 齐全。"""
        return bool(self.endpoint and self.license_key and self.workspace)


def load_cms_config(env: dict | None = None) -> CmsConfig:
    """从环境变量加载 CMS 配置。"""
    e = env if env is not None else os.environ
    cfg = CmsConfig(
        traces_enabled=_truthy(e.get("AGENTTEAMS_CMS_TRACES_ENABLED")),
        endpoint=e.get("AGENTTEAMS_CMS_ENDPOINT"),
        license_key=e.get("AGENTTEAMS_CMS_LICENSE_KEY"),
        workspace=e.get("AGENTTEAMS_CMS_WORKSPACE"),
        service_name=e.get("AGENTTEAMS_CMS_SERVICE_NAME", "servevo"),
    )
    cfg.configured_vars = [k for k in CMS_ENV if e.get(k)]
    return cfg


def _truthy(v: str | None) -> bool:
    return bool(v) and v.strip().lower() in ("1", "true", "yes", "on")


def mode(cfg: CmsConfig) -> str:
    """返回观测模式：cloud（AgentLoop 云接入）/ local（自建等价物）/ none。"""
    if cfg.cloud_connected:
        return "cloud"
    if cfg.configured_vars:
        return "local"
    return "none"