# routes/export_routes.py
"""ArgoDesk branded report export ("brain to PDF").

Generates a structured, company-branded report from a chat session. Returns the
report as markdown + self-contained HTML so the frontend can open/print it to
PDF or save it to Documents using already-vendored client libraries.
"""

import logging
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel

from src.auth_helpers import require_user, effective_user
from src import report_export

logger = logging.getLogger(__name__)


class ReportRequest(BaseModel):
    session_id: str
    report_type: str = report_export.DEFAULT_REPORT_TYPE


def setup_export_routes(session_manager):
    router = APIRouter(prefix="/api/export")

    @router.get("/report/types")
    def report_types(_user: str = Depends(require_user)):
        return {"types": [{"id": k, "label": v[0]} for k, v in report_export.REPORT_TYPES.items()]}

    @router.post("/report")
    async def export_report(body: ReportRequest, request: Request):
        user = require_user(request)
        try:
            sess = session_manager.get_session(body.session_id)
        except KeyError:
            raise HTTPException(404, "Sessione non trovata")
        # Owner check: only the session owner (or single-user mode) may export it.
        owner = effective_user(request)
        sess_owner = getattr(sess, "owner", None)
        if user and sess_owner and sess_owner != owner:
            raise HTTPException(404, "Sessione non trovata")

        history = sess.get_context_messages() if hasattr(sess, "get_context_messages") else []
        if not history:
            raise HTTPException(400, "La sessione non ha messaggi da sintetizzare")

        try:
            markdown_text = await report_export.generate_report_markdown(history, body.report_type, owner)
        except ValueError as e:
            raise HTTPException(400, str(e))
        except Exception as e:
            logger.error(f"Report generation failed: {e}")
            raise HTTPException(502, f"Generazione report fallita: {e}")

        title, html = report_export.render_report_html(markdown_text, body.report_type)
        return {"ok": True, "title": title, "markdown": markdown_text, "html": html}

    return router
