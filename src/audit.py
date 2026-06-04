"""ArgoDesk audit logging (GDPR / EU AI Act basics).

Thin helpers over the ``audit_logs`` table. ``log_event`` is best-effort and
must never raise into a request path; ``purge_old`` enforces retention.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

DEFAULT_RETENTION_DAYS = 90


def _client_ip(request) -> Optional[str]:
    try:
        client = getattr(request, "client", None)
        return client.host if client else None
    except Exception:
        return None


def log_event(action: str, *, username: Optional[str] = None, resource: Optional[str] = None,
              detail: Optional[str] = None, ip: Optional[str] = None, status: str = "ok",
              request=None) -> None:
    """Record an audit event. Best-effort: never raises into the caller."""
    try:
        from core.database import get_db_session, AuditLog
        if request is not None and ip is None:
            ip = _client_ip(request)
        with get_db_session() as db:
            db.add(AuditLog(
                action=action[:128] if action else "unknown",
                username=(username or None),
                resource=(str(resource)[:256] if resource else None),
                detail=(str(detail)[:1000] if detail else None),
                ip=ip,
                status=(str(status)[:32] if status else None),
            ))
    except Exception as e:  # pragma: no cover - logging must not break requests
        logger.debug("audit log_event failed (%s): %s", action, e)


def list_events(limit: int = 200, username: Optional[str] = None,
                action: Optional[str] = None) -> List[Dict[str, Any]]:
    """Most recent audit events, newest first, with optional filters."""
    from core.database import get_db_session, AuditLog
    out: List[Dict[str, Any]] = []
    limit = max(1, min(int(limit or 200), 1000))
    with get_db_session() as db:
        q = db.query(AuditLog)
        if username:
            q = q.filter(AuditLog.username == username)
        if action:
            q = q.filter(AuditLog.action == action)
        rows = q.order_by(AuditLog.timestamp.desc()).limit(limit).all()
        for r in rows:
            out.append({
                "id": r.id,
                "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                "username": r.username,
                "action": r.action,
                "resource": r.resource,
                "detail": r.detail,
                "ip": r.ip,
                "status": r.status,
            })
    return out


def get_retention_days() -> int:
    try:
        from src.settings import get_setting
        v = int(get_setting("audit_retention_days", DEFAULT_RETENTION_DAYS))
        return v if v > 0 else 0
    except Exception:
        return DEFAULT_RETENTION_DAYS


def purge_old(days: Optional[int] = None) -> int:
    """Delete audit rows older than ``days`` (0/None disables). Returns count."""
    if days is None:
        days = get_retention_days()
    if not days or days <= 0:
        return 0
    from core.database import get_db_session, AuditLog
    cutoff = datetime.utcnow() - timedelta(days=days)
    try:
        with get_db_session() as db:
            n = db.query(AuditLog).filter(AuditLog.timestamp < cutoff).delete(synchronize_session=False)
        if n:
            logger.info("Audit retention: purged %d rows older than %d days", n, days)
        return n or 0
    except Exception as e:
        logger.warning("Audit purge failed: %s", e)
        return 0


def anonymize_user(username: str) -> int:
    """GDPR erasure helper: blank the username on a user's audit rows (keeps the
    aggregate trail without the personal identifier). Returns rows updated."""
    if not username:
        return 0
    from core.database import get_db_session, AuditLog
    try:
        with get_db_session() as db:
            n = (db.query(AuditLog)
                 .filter(AuditLog.username == username)
                 .update({AuditLog.username: "[anonimizzato]"}, synchronize_session=False))
        return n or 0
    except Exception as e:
        logger.warning("Audit anonymize failed: %s", e)
        return 0
