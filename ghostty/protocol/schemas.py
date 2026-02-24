from typing import Any

from .constants import ERR_CONNECTION_LOST


def disconnected_payload() -> dict[str, Any]:
    return {
        "ok": False,
        "error": ERR_CONNECTION_LOST,
        "state": "disconnected",
    }
