"""可观测单测：CMS 配置解析 / 模式判定 / 自建等价物上报。"""

from __future__ import annotations

from servevo_obs.cms import CmsConfig, load_cms_config, mode
from servevo_obs.emitter import LocalObservability, Observability


def test_cms_config_none():
    cfg = load_cms_config({})
    assert cfg.cloud_connected is False
    assert cfg.configured_vars == []
    assert mode(cfg) == "none"


def test_cms_config_cloud():
    cfg = load_cms_config({
        "AGENTTEAMS_CMS_TRACES_ENABLED": "true",
        "AGENTTEAMS_CMS_ENDPOINT": "http://cms",
        "AGENTTEAMS_CMS_LICENSE_KEY": "k",
        "AGENTTEAMS_CMS_WORKSPACE": "ws",
        "AGENTTEAMS_CMS_SERVICE_NAME": "servevo",
    })
    assert cfg.cloud_connected
    assert mode(cfg) == "cloud"


def test_cms_config_local_partial():
    cfg = load_cms_config({"AGENTTEAMS_CMS_ENDPOINT": "http://cms"})
    assert cfg.cloud_connected is False
    assert cfg.configured_vars
    assert mode(cfg) == "local"


def test_local_observability_emits(tmp_path):
    obs = LocalObservability(tmp_path)
    obs.emit_metric("resolution_rate", 0.9, {"kb": "v2"})
    obs.emit_log("info", "进化闭环完成")
    metrics = (tmp_path / "metrics.jsonl").read_text(encoding="utf-8")
    logs = (tmp_path / "logs.jsonl").read_text(encoding="utf-8")
    assert "resolution_rate" in metrics
    assert "进化闭环" in logs


def test_observability_local_mode_emits(tmp_path):
    obs = Observability(CmsConfig(), log_dir=tmp_path)
    assert obs.mode == "none"
    obs.emit_metric("qc", 80.0)
    assert (tmp_path / "metrics.jsonl").exists()


def test_observability_cloud_mode_emits_local_trail(tmp_path):
    cfg = CmsConfig(endpoint="http://cms", license_key="k", workspace="ws")
    obs = Observability(cfg, log_dir=tmp_path)
    assert obs.mode == "cloud"
    # 诚实边界：云接入时仍落本地 jsonl 台账作为等价审计轨迹（不静默丢数据）
    obs.emit_metric("qc", 80.0)
    assert (tmp_path / "metrics.jsonl").exists()