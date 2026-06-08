"""Skill-bundle seeding (2026-06-08 session):

ArgoDesk ships pre-built domain skills under ``bundles/skills/`` and seeds them
into a deployment's ``data/skills/`` at setup. The seeder must:
  - copy bundles verbatim (preserving non-standard body headings like the
    mandatory ``## Disclaimer`` notice on the professional verticals),
  - be idempotent and never clobber an existing destination (client edits / a
    second setup run are preserved),
  - refresh when explicitly asked (overwrite=True).

Hermetic: builds its own bundles dir in tmp, doesn't touch the shipped bundles.
Imports the app package (needs deps installed).
"""

import os
from pathlib import Path

import pytest


_SKILL = """---
name: demo-skill
description: A demo bundle skill
version: 1.0.0
category: legale
status: published
source: imported
owner: __org__
created: 2026-06-08T00:00:00Z
---

## When to Use

Quando serve una demo.

## Disclaimer

Questo strumento NON sostituisce il professionista.
"""


def _make_bundle(bundles_dir: Path) -> Path:
    dst = bundles_dir / "legale" / "demo-skill" / "SKILL.md"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(_SKILL, encoding="utf-8")
    return dst


def test_seed_copies_bundle_verbatim(tmp_path):
    from services.memory.skill_seed import seed_skill_bundles

    bundles = tmp_path / "bundles" / "skills"
    _make_bundle(bundles)
    data_dir = tmp_path / "data"

    summary = seed_skill_bundles(str(data_dir), str(bundles))

    assert summary["seeded"] == [os.path.join("legale", "demo-skill", "SKILL.md")]
    assert summary["skipped"] == []
    dest = data_dir / "skills" / "legale" / "demo-skill" / "SKILL.md"
    assert dest.exists()
    # Verbatim: the non-standard "## Disclaimer" heading survives.
    text = dest.read_text(encoding="utf-8")
    assert "## Disclaimer" in text
    assert "NON sostituisce il professionista" in text
    assert "owner: __org__" in text


def test_seed_is_idempotent_and_never_clobbers(tmp_path):
    from services.memory.skill_seed import seed_skill_bundles

    bundles = tmp_path / "bundles" / "skills"
    _make_bundle(bundles)
    data_dir = tmp_path / "data"

    seed_skill_bundles(str(data_dir), str(bundles))
    dest = data_dir / "skills" / "legale" / "demo-skill" / "SKILL.md"
    # Simulate a client edit to the seeded skill.
    dest.write_text(dest.read_text(encoding="utf-8") + "\n<!-- client edit -->\n", encoding="utf-8")

    summary = seed_skill_bundles(str(data_dir), str(bundles))

    assert summary["seeded"] == []
    assert summary["skipped"] == [os.path.join("legale", "demo-skill", "SKILL.md")]
    # The client edit is preserved (not clobbered).
    assert "<!-- client edit -->" in dest.read_text(encoding="utf-8")


def test_overwrite_refreshes_shipped_skill(tmp_path):
    from services.memory.skill_seed import seed_skill_bundles

    bundles = tmp_path / "bundles" / "skills"
    _make_bundle(bundles)
    data_dir = tmp_path / "data"

    seed_skill_bundles(str(data_dir), str(bundles))
    dest = data_dir / "skills" / "legale" / "demo-skill" / "SKILL.md"
    dest.write_text("stale\n", encoding="utf-8")

    summary = seed_skill_bundles(str(data_dir), str(bundles), overwrite=True)

    assert summary["seeded"] == [os.path.join("legale", "demo-skill", "SKILL.md")]
    assert "## Disclaimer" in dest.read_text(encoding="utf-8")


def test_warns_on_non_org_owned_bundle(tmp_path):
    from services.memory.skill_seed import seed_skill_bundles

    bundles = tmp_path / "bundles" / "skills"
    dst = bundles / "legale" / "bad" / "SKILL.md"
    dst.parent.mkdir(parents=True, exist_ok=True)
    # owner is a real username, not __org__ -> should be flagged (but still seeded).
    dst.write_text(_SKILL.replace("owner: __org__", "owner: alice"), encoding="utf-8")
    data_dir = tmp_path / "data"

    summary = seed_skill_bundles(str(data_dir), str(bundles))

    assert summary["warnings"], "expected a warning for non-org-owned bundle"
    assert "owner" in summary["warnings"][0]
