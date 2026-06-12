"""connect_routes.py — guided email/calendar connection wizard data.

Exposes the static provider presets (`src/connect_presets.py`) to the frontend
wizard. Saving still goes through the existing `/api/email/accounts` and
`/api/calendar/config` endpoints; this only serves the host/port/security
defaults and app-password walkthroughs. Available in both instance modes.
"""

from fastapi import APIRouter, Request

from src.auth_helpers import require_user
from src.connect_presets import CONNECT_PRESETS


def setup_connect_routes() -> APIRouter:
    router = APIRouter(prefix="/api/connect", tags=["connect"])

    @router.get("/presets")
    async def get_connect_presets(request: Request):
        require_user(request)
        return {"presets": CONNECT_PRESETS}

    return router
