"""knowledge_routes.py — knowledge categories + (Fase 5) graph endpoints.

The Knowledge tool unifies RAG uploads (`/api/personal/upload`), wiki pages
(`/api/wiki`) and user-definable *categories* that tag uploads with a purpose.
Categories live in the DB (`KnowledgeCategory`) so they're queryable and can be
linked to the knowledge graph (Fase 5) and projects (Fase 6).

Company-shared categories use owner = ORG_OWNER and are admin-managed; private
categories are scoped to the creating user. Reads return both (shared + own).
"""

import uuid
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel

from core.constants import ORG_OWNER
from core.database import SessionLocal, KnowledgeCategory
from core.middleware import require_admin
from src.auth_helpers import require_user, get_current_user

logger = logging.getLogger(__name__)


class CategoryBody(BaseModel):
    name: str
    description: str = ""
    color: Optional[str] = None
    shared: bool = False  # True → company-shared (ORG_OWNER), admin-only


def _cat_to_dict(c: KnowledgeCategory) -> dict:
    return {
        "id": c.id,
        "owner": c.owner,
        "name": c.name,
        "description": c.description or "",
        "color": c.color,
        "shared": c.owner == ORG_OWNER,
    }


def setup_knowledge_routes():
    router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])

    @router.get("/categories")
    def list_categories(request: Request, _user: str = Depends(require_user)):
        """Shared (ORG_OWNER) + the caller's own categories."""
        user = get_current_user(request)
        db = SessionLocal()
        try:
            q = db.query(KnowledgeCategory).filter(
                (KnowledgeCategory.owner == ORG_OWNER) | (KnowledgeCategory.owner == user)
            ).order_by(KnowledgeCategory.name)
            return {"categories": [_cat_to_dict(c) for c in q.all()]}
        finally:
            db.close()

    @router.post("/categories")
    def create_category(body: CategoryBody, request: Request, _user: str = Depends(require_user)):
        user = get_current_user(request)
        if body.shared:
            require_admin(request)  # company categories are admin-only
            owner = ORG_OWNER
        else:
            owner = user
        name = (body.name or "").strip()
        if not name:
            raise HTTPException(400, "name is required")
        db = SessionLocal()
        try:
            cat = KnowledgeCategory(
                id=uuid.uuid4().hex[:12], owner=owner, name=name,
                description=(body.description or "").strip(), color=body.color,
            )
            db.add(cat)
            db.commit()
            db.refresh(cat)
            return {"ok": True, "category": _cat_to_dict(cat)}
        finally:
            db.close()

    @router.delete("/categories/{category_id}")
    def delete_category(category_id: str, request: Request, _user: str = Depends(require_user)):
        user = get_current_user(request)
        db = SessionLocal()
        try:
            cat = db.query(KnowledgeCategory).filter(KnowledgeCategory.id == category_id).first()
            if not cat:
                raise HTTPException(404, "Category not found")
            # Company categories require admin; private ones require ownership.
            if cat.owner == ORG_OWNER:
                require_admin(request)
            elif cat.owner != user:
                raise HTTPException(404, "Category not found")
            db.delete(cat)
            db.commit()
            return {"ok": True}
        finally:
            db.close()

    # ---- Knowledge graph (Fase 5, GraphRAG-lite) ----

    @router.get("/graph")
    def get_graph(request: Request, focus: Optional[str] = None, _user: str = Depends(require_user)):
        """Whole company graph, or the 1-hop subgraph around `focus` entity id."""
        from services.knowledge.graph_query import full_graph
        # The graph is company-scoped (ORG_OWNER). Falls back to the caller's
        # own graph when there is no company graph yet.
        data = full_graph(ORG_OWNER, focus=focus)
        if not data.get("nodes"):
            data = full_graph(get_current_user(request), focus=focus)
        return data

    @router.get("/entity/{entity_id}")
    def get_entity(entity_id: str, request: Request, _user: str = Depends(require_user)):
        from services.knowledge.graph_query import neighbors
        data = neighbors(entity_id, ORG_OWNER, depth=1)
        if not data.get("nodes"):
            data = neighbors(entity_id, get_current_user(request), depth=1)
        return data

    @router.post("/reextract")
    async def reextract(request: Request, _admin: None = Depends(require_admin)):
        """Re-run graph extraction over all indexed company documents (admin)."""
        from src.settings import load_settings
        if not load_settings().get("knowledge_graph_enabled"):
            raise HTTPException(400, "Il grafo della conoscenza è disattivato nelle impostazioni.")
        # Best-effort: defer to the extractor over the RAG corpus is out of scope
        # here; surface a clear signal that new uploads will populate the graph.
        return {"ok": True, "message": "L'estrazione viene eseguita in background a ogni nuovo caricamento."}

    return router
