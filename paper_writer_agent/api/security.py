from __future__ import annotations

import hmac

from fastapi import Header, HTTPException


def verify_api_key(configured_api_key: str, x_api_key: str | None) -> None:
    if not configured_api_key:
        return
    if not hmac.compare_digest(x_api_key or "", configured_api_key):
        raise HTTPException(status_code=401, detail="invalid api key")


def extract_api_key_header(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> str | None:
    return x_api_key
