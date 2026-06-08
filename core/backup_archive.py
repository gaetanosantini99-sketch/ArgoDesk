"""Framework-free full-instance backup/restore (ZIP snapshot of data/).

Kept independent of FastAPI so it is unit-testable without booting the app.
`routes/backup_routes.py` wraps these with auth and HTTP error mapping.

Snapshot contents:
  - `argodesk_backup.json` manifest (app/version/created_at/instance_mode/...)
  - `data/app.db` — a *consistent* SQLite snapshot via the online backup API
    (not a copy of a possibly mid-write file)
  - every other small file under data/ (config JSON, skills/, personal docs)

Excluded: vector stores + caches (rebuildable), and user media unless asked.
"""

from __future__ import annotations

import io
import json
import os
import sqlite3
import tempfile
import zipfile
from datetime import datetime
from typing import Dict, Iterator, List, Optional, Tuple

# Derived / rebuildable or large dirs under data/ — never in the snapshot.
EXCLUDE_DIRS = {"chroma", "rag", "memory_vectors", "tts_cache", "__pycache__"}
# User-generated media — heavy; only included when include_media=True.
MEDIA_DIRS = {"uploads", "personal_uploads", "generated_images", "deep_research"}
# Top-level SQLite DBs are snapshotted via the sqlite backup API, not walked.
DB_FILENAMES = {"app.db"}
MANIFEST_NAME = "argodesk_backup.json"


class BadArchive(ValueError):
    """Raised when an uploaded archive is not a valid ArgoDesk backup."""


class UnsafeMemberPath(ValueError):
    """Raised when a ZIP member would extract outside the target tree."""


def snapshot_sqlite(src_path: str) -> bytes:
    """Return a consistent byte snapshot of a SQLite DB using the online backup
    API, so a concurrently-written DB can't land half-flushed in the ZIP."""
    fd, tmp = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        src = sqlite3.connect(src_path)
        try:
            dst = sqlite3.connect(tmp)
            try:
                src.backup(dst)
            finally:
                dst.close()
        finally:
            src.close()
        with open(tmp, "rb") as f:
            return f.read()
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass


def iter_backup_members(data_dir: str, include_media: bool) -> Iterator[Tuple[str, str]]:
    """Yield (abs_path, arcname) for files to snapshot, skipping derived/large
    dirs (and media unless requested). DB files are handled separately."""
    root = os.path.abspath(data_dir)
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = os.path.relpath(dirpath, root)
        top = (rel_dir.split(os.sep)[0] if rel_dir != "." else "")
        dirnames[:] = [
            d for d in dirnames
            if not (rel_dir == "." and (d in EXCLUDE_DIRS
                                        or (not include_media and d in MEDIA_DIRS)))
        ]
        if top in EXCLUDE_DIRS or (not include_media and top in MEDIA_DIRS):
            continue
        for fn in filenames:
            if rel_dir == "." and fn in DB_FILENAMES:
                continue
            if fn.endswith((".tmp", ".lock", "-wal", "-shm")):
                continue
            abs_path = os.path.join(dirpath, fn)
            arcname = os.path.join("data", os.path.relpath(abs_path, root))
            yield abs_path, arcname.replace(os.sep, "/")


def safe_extract_path(base: str, member: str) -> str:
    """Resolve a ZIP member to an absolute path inside `base`, or raise
    UnsafeMemberPath. Guards against `../`, absolute paths, and drive letters."""
    member = member.replace("\\", "/")
    if member.startswith("/") or (len(member) > 1 and member[1] == ":"):
        raise UnsafeMemberPath(member)
    base_abs = os.path.abspath(base)
    dest = os.path.abspath(os.path.normpath(os.path.join(base_abs, member)))
    if dest != base_abs and not dest.startswith(base_abs + os.sep):
        raise UnsafeMemberPath(member)
    return dest


def create_archive(data_dir: str, include_media: bool = False,
                   manifest_fields: Optional[Dict] = None) -> bytes:
    """Build a full-instance ZIP snapshot of `data_dir` and return its bytes."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        manifest = {
            "app": "argodesk",
            "kind": "full_archive",
            "version": 1,
            "created_at": datetime.now().isoformat(),
            "include_media": bool(include_media),
        }
        manifest.update(manifest_fields or {})
        zf.writestr(MANIFEST_NAME, json.dumps(manifest, indent=2, ensure_ascii=False))

        db_path = os.path.join(os.path.abspath(data_dir), "app.db")
        if os.path.exists(db_path):
            zf.writestr("data/app.db", snapshot_sqlite(db_path))

        for abs_path, arcname in iter_backup_members(data_dir, include_media):
            try:
                zf.write(abs_path, arcname)
            except OSError:
                continue
    return buf.getvalue()


def restore_archive(data_dir: str, raw_zip: bytes) -> Dict:
    """Restore a ZIP produced by `create_archive` into `data_dir`'s tree.

    Config/skills/docs are written live; the SQLite DB is STAGED to
    `app.db.restore` (a live DB file can't be safely overwritten) and applied
    on the next start by `core.database._apply_staged_db_restore`. Returns
    ``{"restored": [...], "restart_required": bool}``. Raises BadArchive /
    UnsafeMemberPath on bad input.
    """
    try:
        zf = zipfile.ZipFile(io.BytesIO(raw_zip))
    except zipfile.BadZipFile as e:
        raise BadArchive("not a valid ZIP archive") from e

    if MANIFEST_NAME not in set(zf.namelist()):
        raise BadArchive("manifest missing")
    try:
        manifest = json.loads(zf.read(MANIFEST_NAME))
    except Exception as e:
        raise BadArchive("invalid manifest") from e
    if manifest.get("app") != "argodesk":
        raise BadArchive("foreign archive")

    repo_root = os.path.dirname(os.path.abspath(data_dir))
    db_path = os.path.join(os.path.abspath(data_dir), "app.db")
    restored: List[str] = []
    restart_required = False

    for member in zf.namelist():
        if member == MANIFEST_NAME or member.endswith("/"):
            continue
        if not member.startswith("data/"):
            continue
        payload = zf.read(member)
        if member == "data/app.db":
            with open(db_path + ".restore", "wb") as f:
                f.write(payload)
            restart_required = True
            restored.append("database (staged)")
            continue
        dest = safe_extract_path(repo_root, member)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as f:
            f.write(payload)
        restored.append(os.path.relpath(dest, repo_root).replace(os.sep, "/"))

    return {"restored": restored, "restart_required": restart_required}
