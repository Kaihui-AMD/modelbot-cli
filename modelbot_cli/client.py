"""HTTP client and local configuration (~/.modelbot.yaml)."""

from __future__ import annotations

import os
from pathlib import Path

import requests
import yaml

# Public contest entry; override with --api, $MODELBOT_API_URL, or ~/.modelbot.yaml.
DEFAULT_API = "https://rocm-challenge.amddev.ai"


class ApiError(Exception):
    def __init__(self, status: int, detail: str, reason: str | None = None):
        super().__init__(detail)
        self.status = status
        self.detail = detail
        self.reason = reason


def config_path() -> Path:
    return Path(os.environ.get("MODELBOT_CONFIG", Path.home() / ".modelbot.yaml"))


def load_config() -> dict:
    path = config_path()
    if path.is_file():
        return yaml.safe_load(path.read_text()) or {}
    return {}


def save_config(cfg: dict) -> None:
    path = config_path()
    path.write_text(yaml.safe_dump(cfg, sort_keys=True))
    path.chmod(0o600)


class Client:
    def __init__(self, api_url: str | None = None, token: str | None = None, timeout: float = 60):
        cfg = load_config()
        self.api = (api_url or os.environ.get("MODELBOT_API_URL") or cfg.get("api_url") or DEFAULT_API).rstrip("/")
        self.token = token or os.environ.get("MODELBOT_TOKEN") or cfg.get("token")
        self.timeout = timeout
        self.session = requests.Session()

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    def request(self, method: str, path: str, **kw):
        try:
            resp = self.session.request(method, self.api + path, headers=self._headers(), timeout=self.timeout, **kw)
        except requests.RequestException as e:
            raise ApiError(0, f"cannot reach {self.api}: {e}") from e
        if resp.status_code >= 400:
            try:
                body = resp.json()
                detail, reason = body.get("detail", resp.text), body.get("reason")
            except ValueError:
                detail, reason = resp.text, None
            if isinstance(detail, list):
                detail = "; ".join(str(d.get("msg", d)) for d in detail)
            raise ApiError(resp.status_code, str(detail), reason)
        return resp

    def get(self, path: str, **kw):
        return self.request("GET", path, **kw).json()

    def text(self, path: str) -> str:
        return self.request("GET", path).text

    def bytes(self, path: str) -> tuple[bytes, dict]:
        """GET a binary body; returns (content, response headers)."""
        resp = self.request("GET", path)
        return resp.content, resp.headers

    def post(self, path: str, **kw):
        return self.request("POST", path, **kw).json()
