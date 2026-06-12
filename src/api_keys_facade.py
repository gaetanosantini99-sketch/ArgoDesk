"""api_keys_facade.py

A thin read-aggregate / write-dispatch facade over the secrets that today live
in three different stores:

  * provider keys      → `ModelEndpoint.api_key` rows (SQLite, via core.database)
  * the HuggingFace key → `data/cookbook_state.json` (via src.cookbook_secrets)
  * integration keys    → `data/integrations.json` (via src.integrations)

This is deliberately **not** a new unified store: a fourth table would duplicate
`secret_storage` and drift out of sync with the owning stores. Instead `list_keys()`
reads from each store and returns one masked, normalised list, and `set_key()`
dispatches a write back to whichever store owns the entry — each of which already
encrypts at rest through `secret_storage`. All crypto stays in those stores.

Callers must enforce admin-only access; this module never returns plaintext.
"""

import logging
from typing import Any, Dict, List

from core.database import SessionLocal, ModelEndpoint
from src.cookbook_secrets import load_hf_token, mask_hf_token, save_hf_token
from src.integrations import load_integrations, update_integration

log = logging.getLogger(__name__)

# The synthetic id for the single HuggingFace token row.
HF_KEY_ID = "hf"

# Integration auth types that actually carry a secret worth surfacing here.
_KEYED_AUTH_TYPES = {"header", "bearer", "query", "basic"}


def _mask(value: str) -> str:
    """Mask a plaintext secret for display. Mirrors integrations' 4-char prefix."""
    if not value:
        return ""
    if len(value) <= 8:
        return "****"
    return f"{value[:4]}****"


def list_keys() -> List[Dict[str, Any]]:
    """Return a flat, masked list of every configurable key across all stores.

    Each entry: {group, id, label, hint, configured, masked}. `group` is one of
    "models" | "huggingface" | "integrations" and maps back to the owning store
    in `set_key`.
    """
    entries: List[Dict[str, Any]] = []

    # ── Provider / model endpoint keys ──────────────────────────────────
    db = SessionLocal()
    try:
        rows = db.query(ModelEndpoint).order_by(ModelEndpoint.created_at).all()
        for r in rows:
            key = r.api_key or ""
            entries.append({
                "group": "models",
                "id": r.id,
                "label": r.name or r.base_url,
                "hint": r.base_url,
                "configured": bool(key),
                "masked": _mask(key),
            })
    finally:
        db.close()

    # ── HuggingFace token ───────────────────────────────────────────────
    hf = load_hf_token()
    entries.append({
        "group": "huggingface",
        "id": HF_KEY_ID,
        "label": "Hugging Face",
        "hint": "Download di modelli gated/privati (Cookbook)",
        "configured": bool(hf),
        "masked": mask_hf_token(hf),
    })

    # ── Integration keys ────────────────────────────────────────────────
    for integ in load_integrations():
        auth_type = integ.get("auth_type", "none")
        key = integ.get("api_key", "") or ""
        # Surface anything that either declares a keyed auth type or already
        # has a key stored (covers presets configured before this facade).
        if auth_type not in _KEYED_AUTH_TYPES and not key:
            continue
        entries.append({
            "group": "integrations",
            "id": integ.get("id", ""),
            "label": integ.get("name") or integ.get("id", ""),
            "hint": integ.get("base_url", ""),
            "configured": bool(key),
            "masked": _mask(key),
        })

    return entries


def set_key(group: str, key_id: str, value: str) -> Dict[str, Any]:
    """Dispatch a key write to the owning store. Returns {ok, ...} or raises ValueError.

    `value` is plaintext from the admin; the owning store handles encryption.
    An empty `value` clears the key where the store supports it.
    """
    value = value or ""

    if group == "huggingface":
        # Validate format the same way the cookbook serve/download path does.
        from routes.cookbook_helpers import _validate_token
        _validate_token(value or None)
        save_hf_token(value)
        return {"ok": True, "group": group, "id": key_id, "masked": mask_hf_token(load_hf_token())}

    if group == "models":
        db = SessionLocal()
        try:
            ep = db.query(ModelEndpoint).filter(ModelEndpoint.id == key_id).first()
            if not ep:
                raise ValueError(f"Model endpoint not found: {key_id}")
            ep.api_key = value or None
            db.commit()
            return {"ok": True, "group": group, "id": key_id, "masked": _mask(value)}
        finally:
            db.close()

    if group == "integrations":
        item = update_integration(key_id, {"api_key": value})
        if not item:
            raise ValueError(f"Integration not found: {key_id}")
        return {"ok": True, "group": group, "id": key_id, "masked": _mask(value)}

    raise ValueError(f"Unknown key group: {group}")
