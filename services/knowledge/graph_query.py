"""graph_query.py — read-side of the GraphRAG-lite knowledge graph.

`neighbors(entity_id)` expands one hop; `subgraph_for_query(text)` resolves the
query's terms to entities and expands 1 hop, returning nodes + edges plus a
compact textual summary that `chat_processor` injects alongside the RAG chunks.
All queries are owner-scoped.
"""

import logging
import re
from typing import List, Optional

logger = logging.getLogger(__name__)


def _norm(name: str) -> str:
    return re.sub(r"\s+", " ", (name or "").strip().lower())


def _entity_dict(e) -> dict:
    return {"id": e.id, "name": e.name, "type": e.type, "source_doc": e.source_doc}


def neighbors(entity_id: str, owner: Optional[str], depth: int = 1) -> dict:
    """Return {nodes, edges} reachable within `depth` hops of entity_id."""
    from core.database import SessionLocal, KnowledgeEntity, KnowledgeRelation
    db = SessionLocal()
    try:
        seen_ids = set()
        frontier = {entity_id}
        edges = []
        for _ in range(max(1, depth)):
            if not frontier:
                break
            rels = db.query(KnowledgeRelation).filter(
                KnowledgeRelation.owner == owner,
                (KnowledgeRelation.src_entity_id.in_(frontier))
                | (KnowledgeRelation.dst_entity_id.in_(frontier)),
            ).all()
            next_frontier = set()
            for r in rels:
                edges.append({
                    "src": r.src_entity_id, "dst": r.dst_entity_id,
                    "relation": r.relation, "confidence": r.confidence,
                })
                for nid in (r.src_entity_id, r.dst_entity_id):
                    if nid not in seen_ids:
                        next_frontier.add(nid)
            seen_ids |= frontier
            frontier = next_frontier - seen_ids
        seen_ids |= frontier
        nodes = []
        if seen_ids:
            for e in db.query(KnowledgeEntity).filter(
                KnowledgeEntity.owner == owner, KnowledgeEntity.id.in_(seen_ids)
            ).all():
                nodes.append(_entity_dict(e))
        # Dedup edges
        uniq = {(e["src"], e["dst"], e["relation"]): e for e in edges}
        return {"nodes": nodes, "edges": list(uniq.values())}
    finally:
        db.close()


def _resolve_entities(text: str, owner: Optional[str], limit: int = 5) -> list:
    """Match query tokens to entity norm_names (substring, conservative)."""
    from core.database import SessionLocal, KnowledgeEntity
    db = SessionLocal()
    try:
        all_ents = db.query(KnowledgeEntity).filter(KnowledgeEntity.owner == owner).all()
        if not all_ents:
            return []
        q = _norm(text)
        tokens = {t for t in re.split(r"[^a-z0-9àèéìòù]+", q) if len(t) >= 4}
        matched = []
        for e in all_ents:
            nn = e.norm_name
            if nn and (nn in q or any(tok in nn for tok in tokens)):
                matched.append(e)
        return matched[:limit]
    finally:
        db.close()


def subgraph_for_query(text: str, owner: Optional[str], max_nodes: int = 25) -> dict:
    """Resolve query → entities, expand 1 hop, return {nodes, edges, summary}."""
    seeds = _resolve_entities(text, owner)
    if not seeds:
        return {"nodes": [], "edges": [], "summary": ""}
    nodes_by_id = {}
    edges = {}
    for s in seeds:
        sub = neighbors(s.id, owner, depth=1)
        for n in sub["nodes"]:
            nodes_by_id[n["id"]] = n
        for e in sub["edges"]:
            edges[(e["src"], e["dst"], e["relation"])] = e
        if len(nodes_by_id) >= max_nodes:
            break
    nodes = list(nodes_by_id.values())[:max_nodes]
    edge_list = list(edges.values())
    return {
        "nodes": nodes,
        "edges": edge_list,
        "summary": _summarize(nodes, edge_list, nodes_by_id),
    }


def _summarize(nodes: list, edges: list, nodes_by_id: dict) -> str:
    """Compact textual summary of the subgraph for LLM context injection."""
    if not nodes:
        return ""
    name_of = {n["id"]: n["name"] for n in nodes}
    lines = []
    for e in edges[:30]:
        s = name_of.get(e["src"]) or nodes_by_id.get(e["src"], {}).get("name")
        d = name_of.get(e["dst"]) or nodes_by_id.get(e["dst"], {}).get("name")
        if s and d:
            lines.append(f"- {s} → {e['relation']} → {d}")
    if not lines:
        # No edges among matched nodes — at least list the entities.
        lines = [f"- {n['name']} ({n['type']})" for n in nodes[:15]]
    return "Knowledge graph (entities and relations relevant to the query):\n" + "\n".join(lines)


def full_graph(owner: Optional[str], focus: Optional[str] = None, limit: int = 200) -> dict:
    """Return the whole owner graph, or the 1-hop subgraph around `focus` entity."""
    if focus:
        return neighbors(focus, owner, depth=1)
    from core.database import SessionLocal, KnowledgeEntity, KnowledgeRelation
    db = SessionLocal()
    try:
        ents = db.query(KnowledgeEntity).filter(KnowledgeEntity.owner == owner).limit(limit).all()
        ids = {e.id for e in ents}
        nodes = [_entity_dict(e) for e in ents]
        edges = []
        if ids:
            for r in db.query(KnowledgeRelation).filter(
                KnowledgeRelation.owner == owner,
                KnowledgeRelation.src_entity_id.in_(ids),
                KnowledgeRelation.dst_entity_id.in_(ids),
            ).all():
                edges.append({
                    "src": r.src_entity_id, "dst": r.dst_entity_id,
                    "relation": r.relation, "confidence": r.confidence,
                })
        return {"nodes": nodes, "edges": edges}
    finally:
        db.close()
