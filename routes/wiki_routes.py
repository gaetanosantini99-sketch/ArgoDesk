# routes/wiki_routes.py
"""Routes for the ArgoDesk company wiki.

Reads are available to any authenticated user (including guests, who consume
knowledge read-only); create/update/delete are admin-only. Wiki pages are
company-level (owner = ORG_OWNER) and are mirrored into ChromaDB so the agent
can consult them with a high-confidence, wiki-only filter before free RAG.
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Request, Depends, Query
from pydantic import BaseModel

from src.auth_helpers import require_user, get_current_user
from core.middleware import require_admin
from src import wiki as wiki_service

logger = logging.getLogger(__name__)


class WikiPageBody(BaseModel):
    title: str
    content: str = ""
    tags: Optional[List[str]] = None
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None


def setup_wiki_routes():
    router = APIRouter(prefix="/api/wiki")

    @router.get("")
    def list_wiki(_user: str = Depends(require_user)):
        return {"pages": wiki_service.list_pages()}

    @router.get("/search")
    def search_wiki(q: str = Query(...), k: int = 3, _user: str = Depends(require_user)):
        return {"results": wiki_service.search_wiki(q, k=k)}

    @router.get("/{page_id}")
    def get_wiki(page_id: str, _user: str = Depends(require_user)):
        page = wiki_service.get_page(page_id)
        if not page:
            raise HTTPException(404, "Page not found")
        return page

    @router.post("")
    def create_wiki(body: WikiPageBody, request: Request, _admin: None = Depends(require_admin)):
        try:
            return wiki_service.save_page(
                page_id=None, title=body.title, content=body.content,
                tags=body.tags, valid_from=body.valid_from, valid_to=body.valid_to,
                updated_by=get_current_user(request) or "",
            )
        except ValueError as e:
            raise HTTPException(400, str(e))

    @router.put("/{page_id}")
    def update_wiki(page_id: str, body: WikiPageBody, request: Request, _admin: None = Depends(require_admin)):
        try:
            return wiki_service.save_page(
                page_id=page_id, title=body.title, content=body.content,
                tags=body.tags, valid_from=body.valid_from, valid_to=body.valid_to,
                updated_by=get_current_user(request) or "",
            )
        except ValueError as e:
            raise HTTPException(404 if str(e) == "page not found" else 400, str(e))

    @router.delete("/{page_id}")
    def delete_wiki(page_id: str, _admin: None = Depends(require_admin)):
        if not wiki_service.delete_page(page_id):
            raise HTTPException(404, "Page not found")
        return {"ok": True}

    return router
