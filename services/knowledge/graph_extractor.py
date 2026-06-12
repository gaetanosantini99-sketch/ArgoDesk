"""graph_extractor.py — GraphRAG-lite entity/relation extraction.

Modelled on services/memory/memory_extractor.py: an LLM reads a document's text
and returns JSON `{entities, relations}`, which we upsert into the
KnowledgeEntity / KnowledgeRelation tables. Designed to run as a background task
(asyncio.create_task) after RAG ingestion — errors are logged, never raised.

De-risking (per the roadmap):
- **Fingerprint gating**: a per-doc content hash is stored in a sidecar JSON;
  an unchanged document is skipped so re-uploads don't re-spend LLM tokens.
- **Per-doc caps**: at most MAX_ENTITIES / MAX_RELATIONS are kept.
- **norm_name dedup**: entities collapse on lowercased name within an owner.
"""

import hashlib
import json
import logging
import os
import re
import uuid
from typing import Optional

logger = logging.getLogger(__name__)

MAX_ENTITIES = 20
MAX_RELATIONS = 30
ENTITY_TYPES = {"person", "org", "concept", "doc", "project"}

EXTRACT_SYSTEM_PROMPT = (
    "You are a knowledge-graph extraction assistant. Read the document and extract the "
    "key entities and the relations between them. Be precise and conservative.\n\n"
    "Return ONLY valid JSON (no markdown fences) with this shape:\n"
    '{"entities": [{"name": "...", "type": "person|org|concept|doc|project"}], '
    '"relations": [{"src": "entity name", "dst": "entity name", "relation": "short verb phrase", "confidence": 0.0-1.0}]}\n\n'
    "Rules:\n"
    "- Max 20 entities, max 30 relations — only the most important.\n"
    "- Entity names must be concrete nouns (people, organisations, products, concepts, projects).\n"
    "- relation is a short lowercase phrase (e.g. 'works for', 'part of', 'depends on').\n"
    "- src and dst MUST be names present in entities.\n"
    "- If nothing meaningful is present, return {\"entities\": [], \"relations\": []}."
)


def _state_path() -> str:
    data_dir = os.environ.get("DATA_DIR", "data")
    return os.path.join(data_dir, "knowledge_graph_state.json")


def _load_state() -> dict:
    try:
        with open(_state_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_state(key: str, fingerprint: str) -> None:
    state = _load_state()
    state[key] = {"fingerprint": fingerprint}
    try:
        os.makedirs(os.path.dirname(_state_path()), exist_ok=True)
        with open(_state_path(), "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except OSError as e:
        logger.warning(f"Could not persist graph fingerprint: {e}")


def _norm(name: str) -> str:
    return re.sub(r"\s+", " ", (name or "").strip().lower())


def _parse_json_obj(raw: str) -> Optional[dict]:
    text = (raw or "").strip()
    text = re.sub(r'<think(?:ing)?>[\s\S]*?</think(?:ing)?>', '', text, flags=re.I).strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    for cand in (text, re.sub(r',(\s*[}\]])', r'\1', text)):
        try:
            v = json.loads(cand)
            if isinstance(v, dict):
                return v
        except Exception:
            continue
    a, b = text.find("{"), text.rfind("}")
    if a >= 0 and b > a:
        try:
            v = json.loads(text[a:b + 1])
            return v if isinstance(v, dict) else None
        except Exception:
            return None
    return None


def _upsert_entity(db, owner, name, etype, source_doc) -> Optional[str]:
    """Return the entity id, creating or reusing by (owner, norm_name)."""
    from core.database import KnowledgeEntity
    norm = _norm(name)
    if not norm:
        return None
    row = db.query(KnowledgeEntity).filter(
        KnowledgeEntity.owner == owner, KnowledgeEntity.norm_name == norm
    ).first()
    if row:
        return row.id
    etype = etype if etype in ENTITY_TYPES else "concept"
    row = KnowledgeEntity(
        id=uuid.uuid4().hex[:12], owner=owner, name=name.strip(),
        norm_name=norm, type=etype, source_doc=source_doc,
    )
    db.add(row)
    db.flush()
    return row.id


async def extract_graph_for_document(
    text: str,
    owner: Optional[str],
    source_doc: str,
    endpoint_url: str = "",
    model: str = "",
    headers: Optional[dict] = None,
):
    """Extract a knowledge subgraph from one document and upsert it.

    Resolves a utility LLM endpoint itself when one isn't passed. Safe to call
    as a fire-and-forget background task.
    """
    try:
        if not text or not text.strip():
            return
        text = text.strip()

        # Fingerprint gate: skip unchanged documents.
        key = f"{owner or ''}::{source_doc}"
        fp = hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()
        if _load_state().get(key, {}).get("fingerprint") == fp:
            logger.debug("graph extract: %s unchanged, skipping", source_doc)
            return

        if not endpoint_url or not model:
            from src.endpoint_resolver import resolve_endpoint
            endpoint_url, model, headers = resolve_endpoint("utility", owner=owner or None)
            if not endpoint_url or not model:
                endpoint_url, model, headers = resolve_endpoint("default", owner=owner or None)
        if not endpoint_url or not model:
            logger.debug("graph extract: no LLM endpoint available, skipping")
            return

        from src.llm_core import llm_call_async
        excerpt = text[:8000]
        raw = await llm_call_async(
            endpoint_url, model,
            [
                {"role": "system", "content": EXTRACT_SYSTEM_PROMPT},
                {"role": "user", "content": excerpt},
            ],
            temperature=0.1, max_tokens=2000, headers=headers, timeout=120,
        )
        obj = _parse_json_obj(raw)
        if not obj:
            logger.debug("graph extract: non-JSON response for %s", source_doc)
            return

        entities = obj.get("entities") or []
        relations = obj.get("relations") or []
        if not isinstance(entities, list):
            entities = []
        if not isinstance(relations, list):
            relations = []
        entities = entities[:MAX_ENTITIES]
        relations = relations[:MAX_RELATIONS]

        from core.database import SessionLocal, KnowledgeRelation
        db = SessionLocal()
        added_e = added_r = 0
        try:
            name_to_id = {}
            for ent in entities:
                if not isinstance(ent, dict):
                    continue
                name = (ent.get("name") or "").strip()
                if not name:
                    continue
                eid = _upsert_entity(db, owner, name, ent.get("type", "concept"), source_doc)
                if eid:
                    name_to_id[_norm(name)] = eid
                    added_e += 1

            for rel in relations:
                if not isinstance(rel, dict):
                    continue
                src_id = name_to_id.get(_norm(rel.get("src", "")))
                dst_id = name_to_id.get(_norm(rel.get("dst", "")))
                relation = (rel.get("relation") or "related_to").strip()[:60]
                if not src_id or not dst_id or src_id == dst_id:
                    continue
                # Skip if an identical edge already exists.
                exists = db.query(KnowledgeRelation).filter(
                    KnowledgeRelation.owner == owner,
                    KnowledgeRelation.src_entity_id == src_id,
                    KnowledgeRelation.dst_entity_id == dst_id,
                    KnowledgeRelation.relation == relation,
                ).first()
                if exists:
                    continue
                try:
                    conf = float(rel.get("confidence", 0.5))
                except (TypeError, ValueError):
                    conf = 0.5
                db.add(KnowledgeRelation(
                    id=uuid.uuid4().hex[:12], owner=owner,
                    src_entity_id=src_id, dst_entity_id=dst_id,
                    relation=relation, confidence=max(0.0, min(1.0, conf)),
                    source_chunk_ref=source_doc,
                ))
                added_r += 1

            db.commit()
        finally:
            db.close()

        _save_state(key, fp)
        logger.info("graph extract: %s → +%d entities, +%d relations", source_doc, added_e, added_r)
    except Exception as e:
        logger.error("graph extraction failed for %s: %s", source_doc, e)
