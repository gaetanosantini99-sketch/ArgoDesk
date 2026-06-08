"""Full-instance backup/restore (2026-06-08 session):

`core.backup_archive` snapshots a deployment's data/ into a ZIP (consistent
SQLite snapshot + config/skills/docs, media optional) and restores it, staging
the DB for a restart-time swap. Framework-free, so tested hermetically.

Guards under test:
  - round-trip preserves config/skills files,
  - the SQLite DB is staged to `app.db.restore` (never overwritten live),
  - vector/cache dirs are excluded; media excluded unless requested,
  - path-traversal members are rejected,
  - a foreign / non-ArgoDesk ZIP is rejected.
"""

import io
import os
import sqlite3
import zipfile

import pytest

from core.backup_archive import (
    create_archive, restore_archive, safe_extract_path,
    BadArchive, UnsafeMemberPath,
)


def _make_data_dir(tmp_path):
    data = tmp_path / "inst" / "data"
    (data / "skills" / "legale" / "demo").mkdir(parents=True)
    (data / "chroma").mkdir(parents=True)            # derived -> excluded
    (data / "uploads").mkdir(parents=True)           # media -> excluded by default
    (data / "settings.json").write_text('{"k": 1}', encoding="utf-8")
    (data / "skills" / "legale" / "demo" / "SKILL.md").write_text("# demo", encoding="utf-8")
    (data / "chroma" / "vec.bin").write_bytes(b"\x00\x01")
    (data / "uploads" / "big.bin").write_bytes(b"media")
    # a small sqlite db
    con = sqlite3.connect(str(data / "app.db"))
    con.execute("create table t(x)")
    con.execute("insert into t values (42)")
    con.commit()
    con.close()
    return data


def test_archive_contents_exclude_derived_and_media(tmp_path):
    data = _make_data_dir(tmp_path)
    blob = create_archive(str(data), include_media=False)
    names = set(zipfile.ZipFile(io.BytesIO(blob)).namelist())

    assert "argodesk_backup.json" in names
    assert "data/app.db" in names
    assert "data/settings.json" in names
    assert "data/skills/legale/demo/SKILL.md" in names
    # excluded
    assert not any(n.startswith("data/chroma/") for n in names)
    assert not any(n.startswith("data/uploads/") for n in names)


def test_archive_includes_media_when_requested(tmp_path):
    data = _make_data_dir(tmp_path)
    names = set(zipfile.ZipFile(io.BytesIO(create_archive(str(data), include_media=True))).namelist())
    assert "data/uploads/big.bin" in names
    # vector store still excluded even with media on
    assert not any(n.startswith("data/chroma/") for n in names)


def test_restore_round_trip_stages_db_and_writes_config(tmp_path):
    src = _make_data_dir(tmp_path)
    blob = create_archive(str(src), include_media=False)

    # Restore into a fresh empty instance.
    dst = tmp_path / "restored" / "data"
    dst.mkdir(parents=True)
    result = restore_archive(str(dst), blob)

    assert result["restart_required"] is True
    assert "database (staged)" in result["restored"]
    # Config + skills written live.
    assert (dst / "settings.json").read_text(encoding="utf-8") == '{"k": 1}'
    assert (dst / "skills" / "legale" / "demo" / "SKILL.md").exists()
    # DB staged, not applied live.
    assert (dst / "app.db.restore").exists()
    assert not (dst / "app.db").exists()
    # Staged DB is a valid snapshot with our row.
    con = sqlite3.connect(str(dst / "app.db.restore"))
    assert con.execute("select x from t").fetchone()[0] == 42
    con.close()


def test_restore_rejects_foreign_zip(tmp_path):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("data/settings.json", "{}")  # no argodesk manifest
    with pytest.raises(BadArchive):
        restore_archive(str(tmp_path), buf.getvalue())


def test_restore_rejects_bad_zip(tmp_path):
    with pytest.raises(BadArchive):
        restore_archive(str(tmp_path), b"not a zip")


def test_safe_extract_path_blocks_traversal(tmp_path):
    base = str(tmp_path)
    assert safe_extract_path(base, "data/ok.json").startswith(os.path.abspath(base))
    for evil in ("../escape", "data/../../escape", "/etc/passwd", "C:/win"):
        with pytest.raises(UnsafeMemberPath):
            safe_extract_path(base, evil)
