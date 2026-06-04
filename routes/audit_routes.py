# routes/audit_routes.py
"""Admin routes for the ArgoDesk audit trail (GDPR / EU AI Act basics)."""

import logging
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel

from core.middleware import require_admin
from src import audit

logger = logging.getLogger(__name__)


class RetentionBody(BaseModel):
    days: int


class AnonymizeBody(BaseModel):
    username: str


def setup_audit_routes():
    router = APIRouter(prefix="/api/audit")

    @router.get("")
    def list_audit(limit: int = 200, username: str = None, action: str = None,
                   _admin: None = Depends(require_admin)):
        return {"events": audit.list_events(limit=limit, username=username, action=action)}

    @router.get("/retention")
    def get_retention(_admin: None = Depends(require_admin)):
        return {"days": audit.get_retention_days()}

    @router.put("/retention")
    def set_retention(body: RetentionBody, _admin: None = Depends(require_admin)):
        days = max(0, int(body.days))
        from src.settings import load_settings, save_settings
        s = load_settings()
        s["audit_retention_days"] = days
        save_settings(s)
        purged = audit.purge_old(days)
        return {"ok": True, "days": days, "purged": purged}

    @router.post("/purge")
    def purge_now(_admin: None = Depends(require_admin)):
        return {"ok": True, "purged": audit.purge_old()}

    @router.post("/anonymize")
    def anonymize(body: AnonymizeBody, _admin: None = Depends(require_admin)):
        return {"ok": True, "updated": audit.anonymize_user(body.username.strip().lower())}

    return router
