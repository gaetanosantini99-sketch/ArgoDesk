"""cookbook_secrets.py

Shared accessors for the HuggingFace token used by Cookbook (local model
download/serve). The token has always lived in `data/cookbook_state.json`
under `env.hfToken`, encrypted at rest via `secret_storage`, and is read by
`routes/cookbook_routes.py` at serve/download time through `_load_stored_hf_token`.

The logic used to be trapped inside the `setup_cookbook_routes()` closure, so
nothing else could reach it. The API-keys facade (`src/api_keys_facade.py`)
needs to *read* the masked token and *write* a replacement without going through
the Cookbook UI, so the read/write/mask trio is hoisted here. Storage stays in
`cookbook_state.json` so cookbook_routes' resolution path is unchanged — both
modules now share one implementation instead of duplicating the format.
"""

import json
import os
from pathlib import Path
from typing import Optional

from core.atomic_io import atomic_write_json
from src.secret_storage import decrypt, encrypt


def cookbook_state_path() -> Path:
    """Location of the cookbook state file (honours DATA_DIR like cookbook_routes)."""
    return Path(os.environ.get("DATA_DIR", "data")) / "cookbook_state.json"


def mask_hf_token(value: Optional[str]) -> str:
    """Mask a decrypted token for display. Matches cookbook_routes' `_mask_secret`."""
    if not value:
        return ""
    if len(value) <= 8:
        return "stored"
    return f"{value[:4]}...{value[-4:]}"


def load_hf_token() -> str:
    """Return the decrypted HF token, or "" if none is stored."""
    path = cookbook_state_path()
    if not path.exists():
        return ""
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
        env = state.get("env") if isinstance(state, dict) else {}
        raw = env.get("hfToken") if isinstance(env, dict) else ""
    except Exception:
        return ""
    if not raw:
        return ""
    return decrypt(raw)


def save_hf_token(value: str) -> None:
    """Persist a new HF token (encrypted) into cookbook_state.json's `env.hfToken`.

    An empty string clears the stored token. Only the `env.hfToken` field is
    touched; the rest of the state (tasks, server config) is preserved as-is —
    on-disk tasks are already secret-stripped by the normal save path.
    """
    path = cookbook_state_path()
    state = {}
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                state = loaded
        except Exception:
            state = {}

    env = state.get("env")
    if not isinstance(env, dict):
        env = {}
        state["env"] = env

    if value:
        env["hfToken"] = encrypt(value)
    else:
        env.pop("hfToken", None)
    # These are client-only projections; never persist them.
    env.pop("hfTokenMasked", None)
    env.pop("hfTokenConfigured", None)

    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(str(path), state, indent=2)
