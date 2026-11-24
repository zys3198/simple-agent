import json
import os
from pathlib import Path


def _provider() -> dict:
    models_json = Path.home() / ".pi" / "agent" / "models.json"
    providers = json.loads(models_json.read_text(encoding="utf-8"))["providers"]
    return providers[os.environ.get("BIOAGENT_PROVIDER", "magpie")]


def gateway_config() -> tuple[str, str]:
    """模型网关地址与凭据：优先环境变量，其次本机 pi 的 provider 配置。"""
    base_url = os.environ.get("BIOAGENT_BASE_URL")
    api_key = os.environ.get("BIOAGENT_API_KEY")
    if base_url and api_key:
        return base_url, api_key
    provider = _provider()
    return base_url or provider["baseUrl"], api_key or provider["apiKey"]


def available_models() -> list[dict]:
    """同一网关下可切换的模型，取自同一份 provider 配置。"""
    return [{"id": m["id"], "name": m.get("name", m["id"])} for m in _provider().get("models") or []]
