from __future__ import annotations

import json
import time
from pathlib import Path

import requests

SETTINGS_PATH = Path(__file__).resolve().parents[1] / "desktop_settings.json"
DEFAULT_SETTINGS = {
    "backend_url": "http://127.0.0.1:8000",
    "appearance": "Dark",
}

GET_CACHE_TTLS = {
    "/api/dashboard": 2.5,
    "/api/review-items": 2.0,
    "/api/tasks": 2.0,
    "/api/conversations": 2.0,
    "/api/contacts": 4.0,
    "/api/analytics": 6.0,
    "/api/ai-settings": 4.0,
    "/health": 5.0,
}


def load_settings():
    if SETTINGS_PATH.exists():
        try:
            data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            return DEFAULT_SETTINGS | data
        except Exception:
            return DEFAULT_SETTINGS.copy()
    return DEFAULT_SETTINGS.copy()


def save_settings(data: dict):
    SETTINGS_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


class ApiClient:
    def __init__(self):
        self.settings = load_settings()
        self.session = requests.Session()
        self._cache: dict[tuple[str, str], tuple[float, object]] = {}

    @property
    def base_url(self):
        return self.settings["backend_url"].rstrip("/")

    @property
    def appearance(self):
        return self.settings.get("appearance", "Dark")

    def set_base_url(self, value: str):
        self.settings["backend_url"] = value.rstrip("/")
        save_settings(self.settings)
        self.clear_cache()

    def set_appearance(self, value: str):
        self.settings["appearance"] = value
        save_settings(self.settings)

    def clear_cache(self):
        self._cache.clear()

    def _parse_response(self, response: requests.Response):
        content_type = response.headers.get("content-type", "")
        if content_type.startswith("application/json"):
            return response.json()
        return response.text

    def _build_error_message(self, path: str, exc: requests.RequestException) -> str:
        response = getattr(exc, "response", None)
        if response is not None:
            detail = response.text.strip() or response.reason or "Unexpected server error."
            return f"Request failed for {path}: {detail}"
        return f"Unable to reach backend at {self.base_url}. Check that the API is running."

    def _request(self, method: str, path: str, payload: dict | None = None, timeout: int = 10):
        try:
            response = self.session.request(
                method=method,
                url=f"{self.base_url}{path}",
                json=payload if payload is not None else None,
                timeout=timeout,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise RuntimeError(self._build_error_message(path, exc)) from exc
        return self._parse_response(response)

    def get(self, path: str, *, force: bool = False):
        ttl = GET_CACHE_TTLS.get(path)
        cache_key = (self.base_url, path)
        now = time.monotonic()
        if not force and ttl is not None:
            cached = self._cache.get(cache_key)
            if cached and cached[0] > now:
                return cached[1]
        result = self._request("GET", path)
        if ttl is not None:
            self._cache[cache_key] = (now + ttl, result)
        return result

    def post(self, path: str, payload: dict | None = None):
        result = self._request("POST", path, payload=payload)
        self.clear_cache()
        return result

    def delete(self, path: str):
        result = self._request("DELETE", path)
        self.clear_cache()
        return result

    def health(self):
        try:
            return self.get("/health")
        except RuntimeError as exc:
            return {"ok": False, "error": str(exc)}
