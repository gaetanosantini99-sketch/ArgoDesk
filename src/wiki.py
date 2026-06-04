"""ArgoDesk company wiki.

Curated, authoritative knowledge pages the agent consults *before* free-form
RAG. Pages live in the ``wiki_pages`` table (owned at the company level via
ORG_OWNER) and are mirrored into the shared RAG ChromaDB collection with
``type="wiki"`` metadata so they can be retrieved with a high-confidence,
wiki-only filter.

Indexing reuses the existing VectorRAG collection: each page's chunks are
stored under a synthetic ``source`` of ``wiki://<page_id>`` so a re-save can
cleanly delete-then-re-add just that page's chunks.
"""

import uuid
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.constants import ORG_OWNER

logger = logging.getLogger(__name__)

WIKI_SOURCE_PREFIX = "wiki://"


def _wiki_source(page_id: str) -> str:
    return f"{WIKI_SOURCE_PREFIX}{page_id}"


def _page_to_dict(p) -> Dict[str, Any]:
    return {
        "id": p.id,
        "title": p.title,
        "content": p.content or "",
        "tags": [t.strip() for t in (p.tags or "").split(",") if t.strip()],
        "valid_from": p.valid_from.isoformat() if p.valid_from else None,
        "valid_to": p.valid_to.isoformat() if p.valid_to else None,
        "owner": p.owner,
        "updated_by": p.updated_by,
        "updated_at": p.updated_at.isoformat() if getattr(p, "updated_at", None) else None,
    }


def _parse_dt(value) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


# ──────────────────────────────────────────────────────────────────────────
# CRUD
# ──────────────────────────────────────────────────────────────────────────

def list_pages() -> List[Dict[str, Any]]:
    """All company wiki pages, newest first."""
    from core.database import get_db_session, WikiPage
    with get_db_session() as db:
        rows = (
            db.query(WikiPage)
            .filter(WikiPage.owner == ORG_OWNER)
            .order_by(WikiPage.updated_at.desc())
            .all()
        )
        return [_page_to_dict(p) for p in rows]


def get_page(page_id: str) -> Optional[Dict[str, Any]]:
    from core.database import get_db_session, WikiPage
    with get_db_session() as db:
        p = db.query(WikiPage).filter(WikiPage.id == page_id).first()
        return _page_to_dict(p) if p else None


def save_page(
    *,
    page_id: Optional[str],
    title: str,
    content: str,
    tags: Optional[List[str]] = None,
    valid_from=None,
    valid_to=None,
    updated_by: str = "",
) -> Dict[str, Any]:
    """Create or update a company wiki page, then (re)index it into Chroma."""
    from core.database import get_db_session, WikiPage

    title = (title or "").strip()
    if not title:
        raise ValueError("title is required")
    tags_str = ",".join(t.strip() for t in (tags or []) if t and t.strip())

    with get_db_session() as db:
        if page_id:
            p = db.query(WikiPage).filter(WikiPage.id == page_id).first()
            if not p:
                raise ValueError("page not found")
        else:
            p = WikiPage(id=uuid.uuid4().hex, owner=ORG_OWNER)
            db.add(p)
        p.title = title
        p.content = content or ""
        p.tags = tags_str
        p.valid_from = _parse_dt(valid_from)
        p.valid_to = _parse_dt(valid_to)
        p.owner = ORG_OWNER
        p.updated_by = updated_by or p.updated_by
        db.flush()
        result = _page_to_dict(p)

    # Index outside the DB transaction (best-effort; never blocks the save).
    try:
        _reindex_page(result)
    except Exception as e:
        logger.warning("Wiki index failed for %s: %s", result.get("id"), e)
    return result


def delete_page(page_id: str) -> bool:
    from core.database import get_db_session, WikiPage
    with get_db_session() as db:
        p = db.query(WikiPage).filter(WikiPage.id == page_id).first()
        if not p:
            return False
        db.delete(p)
    try:
        _deindex_page(page_id)
    except Exception as e:
        logger.warning("Wiki de-index failed for %s: %s", page_id, e)
    return True


# ──────────────────────────────────────────────────────────────────────────
# ChromaDB indexing (reuses the shared RAG collection)
# ──────────────────────────────────────────────────────────────────────────

def _deindex_page(page_id: str) -> None:
    from src.rag_singleton import get_rag_manager
    rag = get_rag_manager()
    if rag and getattr(rag, "healthy", False):
        rag.delete_by_source(_wiki_source(page_id))


def _reindex_page(page: Dict[str, Any]) -> None:
    from src.rag_singleton import get_rag_manager
    rag = get_rag_manager()
    if not rag or not getattr(rag, "healthy", False):
        return
    page_id = page["id"]
    _deindex_page(page_id)
    body = f"{page['title']}\n\n{page['content']}".strip()
    if not body:
        return
    source = _wiki_source(page_id)
    for i, chunk in enumerate(rag._split_into_chunks(body)):
        rag.add_document(chunk, {
            "source": source,
            "filename": page["title"],
            "title": page["title"],
            "type": "wiki",
            "page_id": page_id,
            "owner": ORG_OWNER,
            "chunk_id": i,
        })


def search_wiki(query: str, k: int = 3) -> List[Dict[str, Any]]:
    """Wiki-only semantic search over the shared collection. Returns the best
    matching pages (deduplicated by page_id) with a similarity score."""
    from src.rag_singleton import get_rag_manager
    rag = get_rag_manager()
    if not rag or not getattr(rag, "healthy", False):
        return []
    coll = getattr(rag, "collection", None)
    if coll is None:
        return []
    try:
        if coll.count() == 0:
            return []
        emb = rag._embed([query])
        res = coll.query(
            query_embeddings=emb,
            n_results=min(k * 4, 20, coll.count()),
            where={"type": "wiki"},
            include=["documents", "metadatas", "distances"],
        )
    except Exception as e:
        logger.warning("Wiki search failed: %s", e)
        return []

    best: Dict[str, Dict[str, Any]] = {}
    ids = res.get("ids", [[]])[0]
    for idx in range(len(ids)):
        meta = res["metadatas"][0][idx] or {}
        dist = res["distances"][0][idx]
        sim = 1.0 - dist
        pid = meta.get("page_id") or ids[idx]
        if pid not in best or sim > best[pid]["similarity"]:
            best[pid] = {
                "page_id": pid,
                "title": meta.get("title", "Untitled"),
                "snippet": res["documents"][0][idx][:500],
                "document": res["documents"][0][idx],
                "similarity": round(sim, 4),
            }
    out = sorted(best.values(), key=lambda r: r["similarity"], reverse=True)
    return out[:k]
