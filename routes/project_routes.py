"""project_routes.py — Notion-style Projects (Fase 6).

A Project ties together notes, documents, gallery albums, chat sessions and
knowledge (categories/entities) through a polymorphic ProjectLink table. There
is no FK integrity on ProjectLink.target_id (kinds span tables), so
`/contents` resolves each link and silently skips orphans.

owner = ORG_OWNER → company-shared (visible to all); a username → private.
"""

import uuid
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel

from core.constants import ORG_OWNER
from core.database import (
    SessionLocal, Project, ProjectLink,
    Note, Document, GalleryAlbum, GalleryImage, Session as ChatSession,
    KnowledgeCategory, KnowledgeEntity,
)
from src.auth_helpers import require_user, get_current_user

logger = logging.getLogger(__name__)

VALID_KINDS = {"note", "document", "album", "session", "knowledge_entity", "knowledge_category"}


class ProjectBody(BaseModel):
    name: str
    description: str = ""
    color: Optional[str] = None
    cover: Optional[str] = None
    shared: bool = False  # True → company-shared (ORG_OWNER)


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None
    cover: Optional[str] = None
    archived: Optional[bool] = None
    sort_order: Optional[int] = None


class LinkBody(BaseModel):
    kind: str
    target_id: str


def _project_dict(p: Project) -> dict:
    return {
        "id": p.id, "owner": p.owner, "name": p.name,
        "description": p.description or "", "color": p.color, "cover": p.cover,
        "archived": bool(p.archived), "sort_order": p.sort_order or 0,
        "shared": p.owner == ORG_OWNER,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


def setup_project_routes():
    router = APIRouter(prefix="/api/projects", tags=["projects"])

    def _visible_filter(q, user):
        return q.filter((Project.owner == ORG_OWNER) | (Project.owner == user))

    def _get_owned_project(db, project_id, user):
        p = db.query(Project).filter(Project.id == project_id).first()
        if not p:
            raise HTTPException(404, "Project not found")
        # Shared projects are editable by any user; private only by the owner.
        if p.owner != ORG_OWNER and p.owner != user:
            raise HTTPException(404, "Project not found")
        return p

    # ---- CRUD ----
    @router.get("")
    def list_projects(request: Request, _user: str = Depends(require_user)):
        user = get_current_user(request)
        db = SessionLocal()
        try:
            q = _visible_filter(db.query(Project), user).filter(Project.archived == False)
            q = q.order_by(Project.sort_order.asc(), Project.updated_at.desc())
            return {"projects": [_project_dict(p) for p in q.all()]}
        finally:
            db.close()

    @router.post("")
    def create_project(body: ProjectBody, request: Request, _user: str = Depends(require_user)):
        user = get_current_user(request)
        name = (body.name or "").strip()
        if not name:
            raise HTTPException(400, "name is required")
        owner = ORG_OWNER if body.shared else user
        db = SessionLocal()
        try:
            p = Project(
                id=uuid.uuid4().hex[:12], owner=owner, name=name,
                description=(body.description or "").strip(),
                color=body.color, cover=body.cover,
            )
            db.add(p)
            db.commit()
            db.refresh(p)
            return {"ok": True, "project": _project_dict(p)}
        finally:
            db.close()

    @router.get("/{project_id}")
    def get_project(project_id: str, request: Request, _user: str = Depends(require_user)):
        user = get_current_user(request)
        db = SessionLocal()
        try:
            return _project_dict(_get_owned_project(db, project_id, user))
        finally:
            db.close()

    @router.put("/{project_id}")
    def update_project(project_id: str, body: ProjectUpdate, request: Request, _user: str = Depends(require_user)):
        user = get_current_user(request)
        db = SessionLocal()
        try:
            p = _get_owned_project(db, project_id, user)
            if body.name is not None:
                p.name = body.name.strip() or p.name
            if body.description is not None:
                p.description = body.description
            if body.color is not None:
                p.color = body.color
            if body.cover is not None:
                p.cover = body.cover
            if body.archived is not None:
                p.archived = body.archived
            if body.sort_order is not None:
                p.sort_order = body.sort_order
            db.commit()
            db.refresh(p)
            return _project_dict(p)
        finally:
            db.close()

    @router.delete("/{project_id}")
    def delete_project(project_id: str, request: Request, _user: str = Depends(require_user)):
        user = get_current_user(request)
        db = SessionLocal()
        try:
            p = _get_owned_project(db, project_id, user)
            db.query(ProjectLink).filter(ProjectLink.project_id == project_id).delete()
            db.delete(p)
            db.commit()
            return {"ok": True}
        finally:
            db.close()

    # ---- Links ----
    @router.post("/{project_id}/links")
    def add_link(project_id: str, body: LinkBody, request: Request, _user: str = Depends(require_user)):
        user = get_current_user(request)
        if body.kind not in VALID_KINDS:
            raise HTTPException(400, f"Invalid kind: {body.kind}")
        db = SessionLocal()
        try:
            _get_owned_project(db, project_id, user)
            # Dedup identical links.
            existing = db.query(ProjectLink).filter(
                ProjectLink.project_id == project_id,
                ProjectLink.kind == body.kind,
                ProjectLink.target_id == body.target_id,
            ).first()
            if existing:
                return {"ok": True, "id": existing.id}
            link = ProjectLink(
                id=uuid.uuid4().hex[:12], project_id=project_id,
                kind=body.kind, target_id=body.target_id,
            )
            db.add(link)
            db.commit()
            return {"ok": True, "id": link.id}
        finally:
            db.close()

    @router.delete("/{project_id}/links/{link_id}")
    def remove_link(project_id: str, link_id: str, request: Request, _user: str = Depends(require_user)):
        user = get_current_user(request)
        db = SessionLocal()
        try:
            _get_owned_project(db, project_id, user)
            link = db.query(ProjectLink).filter(
                ProjectLink.id == link_id, ProjectLink.project_id == project_id
            ).first()
            if not link:
                raise HTTPException(404, "Link not found")
            db.delete(link)
            db.commit()
            return {"ok": True}
        finally:
            db.close()

    # ---- Contents (resolve links → renderable payloads) ----
    @router.get("/{project_id}/contents")
    def project_contents(project_id: str, request: Request, _user: str = Depends(require_user)):
        user = get_current_user(request)
        db = SessionLocal()
        try:
            _get_owned_project(db, project_id, user)
            links = db.query(ProjectLink).filter(ProjectLink.project_id == project_id).all()
            out = {"notes": [], "documents": [], "albums": [], "sessions": [],
                   "knowledge_categories": [], "knowledge_entities": []}
            orphan_ids = []
            for ln in links:
                resolved = _resolve_link(db, ln)
                if resolved is None:
                    orphan_ids.append(ln.id)
                    continue
                bucket, payload = resolved
                payload["link_id"] = ln.id
                out[bucket].append(payload)
            # Cleanup pass: drop links whose target no longer exists.
            if orphan_ids:
                db.query(ProjectLink).filter(ProjectLink.id.in_(orphan_ids)).delete(synchronize_session=False)
                db.commit()
            return out
        finally:
            db.close()

    def _resolve_link(db, ln):
        kind, tid = ln.kind, ln.target_id
        if kind == "note":
            n = db.query(Note).filter(Note.id == tid).first()
            if not n:
                return None
            return "notes", {"id": n.id, "title": n.title or "(senza titolo)", "due_date": n.due_date}
        if kind == "document":
            d = db.query(Document).filter(Document.id == tid).first()
            if not d:
                return None
            return "documents", {"id": d.id, "title": d.title or "Untitled", "language": d.language}
        if kind == "album":
            a = db.query(GalleryAlbum).filter(GalleryAlbum.id == tid).first()
            if not a:
                return None
            imgs = db.query(GalleryImage).filter(
                GalleryImage.album_id == tid, GalleryImage.is_active == True
            ).limit(24).all()
            return "albums", {
                "id": a.id, "name": a.name,
                "images": [{"id": im.id, "url": f"/api/generated-image/{im.filename}"} for im in imgs],
            }
        if kind == "session":
            s = db.query(ChatSession).filter(ChatSession.id == tid).first()
            if not s:
                return None
            return "sessions", {"id": s.id, "name": s.name}
        if kind == "knowledge_category":
            c = db.query(KnowledgeCategory).filter(KnowledgeCategory.id == tid).first()
            if not c:
                return None
            return "knowledge_categories", {"id": c.id, "name": c.name}
        if kind == "knowledge_entity":
            e = db.query(KnowledgeEntity).filter(KnowledgeEntity.id == tid).first()
            if not e:
                return None
            return "knowledge_entities", {"id": e.id, "name": e.name, "type": e.type}
        return None

    return router
