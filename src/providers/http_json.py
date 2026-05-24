from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from src.providers.types import ProviderError


def post_json(url: str, payload: dict[str, object], headers: dict[str, str] | None = None) -> dict[str, object]:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            **(headers or {}),
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")
    except (HTTPError, URLError, TimeoutError) as exc:
        raise ProviderError(str(exc)) from exc

    try:
        decoded = json.loads(body)
    except json.JSONDecodeError as exc:
        raise ProviderError("Provider returned invalid JSON.") from exc

    if not isinstance(decoded, dict):
        raise ProviderError("Provider returned a non-object JSON payload.")
    return decoded
