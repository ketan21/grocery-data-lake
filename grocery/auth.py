"""Anonymous token management for AH API."""

import time
from functools import lru_cache

import httpx

from .config import AUTH_ENDPOINT, CLIENT_ID, DEFAULT_HEADERS

_token: str | None = None
_token_expires_at: float = 0


def _get_token() -> str:
    """Fetch a fresh anonymous token from AH."""
    global _token, _token_expires_at

    resp = httpx.post(
        AUTH_ENDPOINT,
        json={"clientId": CLIENT_ID},
        headers=DEFAULT_HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()

    _token = data["access_token"]
    _token_expires_at = time.time() + data.get("expires_in", 604798)
    return _token


def get_token() -> str:
    """Get a valid token, refreshing if expired."""
    if _token and time.time() < _token_expires_at - 300:  # 5min buffer
        return _token
    return _get_token()


def auth_headers(extra: dict | None = None) -> dict:
    """Build headers dict with auth + any extra headers."""
    token = get_token()
    headers = {**DEFAULT_HEADERS, "Authorization": f"Bearer {token}"}
    if extra:
        headers.update(extra)
    return headers
