"""Sync httpx client to be-api. One Client per app instance (lifetime = app).

`BeApiError` wraps any 5xx / timeout / transport failure. The FastAPI surface
translates it to an HTTP 503 (`/healthz` swallows it as upstream-down). 4xx
status is also raised so the FE sees the same code-path as if be-api had
answered directly — except we mask 404 by raising as well, so the BFF can
choose to re-shape (currently passthrough as 503 to keep the surface boring).
"""
from __future__ import annotations
from typing import Any
import httpx


class BeApiError(Exception):
    """Raised when be-api returns 5xx or times out. BFF translates to 503."""
    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class BeApiClient:
    def __init__(self, base_url: str, timeout_s: float = 12.0) -> None:
        self._client = httpx.Client(base_url=base_url, timeout=timeout_s)

    def close(self) -> None:
        self._client.close()

    def get(self, path: str, **params: Any) -> Any:
        try:
            r = self._client.get(path, params={k: v for k, v in params.items() if v is not None})
        except httpx.TimeoutException as e:
            raise BeApiError(f"timeout calling {path}") from e
        except httpx.HTTPError as e:
            raise BeApiError(f"http error calling {path}: {e}") from e
        if r.status_code >= 500:
            raise BeApiError(f"be-api {r.status_code} on {path}", status=r.status_code)
        if r.status_code == 404:
            raise BeApiError(f"be-api 404 on {path}", status=404)
        r.raise_for_status()
        return r.json()

    def post_json(self, path: str, body: Any) -> Any:
        try:
            r = self._client.post(path, json=body)
        except httpx.TimeoutException as e:
            raise BeApiError(f"timeout calling {path}") from e
        except httpx.HTTPError as e:
            raise BeApiError(f"http error calling {path}: {e}") from e
        if r.status_code >= 500:
            raise BeApiError(f"be-api {r.status_code} on {path}", status=r.status_code)
        r.raise_for_status()
        return r.json()

    def delete(self, path: str) -> Any:
        r = self._client.delete(path)
        r.raise_for_status()
        return r.json() if r.text else {}
