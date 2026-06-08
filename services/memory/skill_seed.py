# services/memory/skill_seed.py
"""Seed shipped skill bundles into a deployment's live skills store.

ArgoDesk ships pre-built, domain-specific skills (legal / tax / notarial, plus
any future vertical) so a fresh client install is useful on first boot instead
of starting with an empty skills store. The bundles live in a **version-
controlled** directory at the repo root:

    bundles/skills/<category>/<name>/SKILL.md

`data/` is gitignored (per-client local data), so shipped skills cannot live
there — they would never be committed. Instead they live under `bundles/` and
are *seeded* (copied) into `data/skills/<category>/<name>/SKILL.md` at setup /
first boot, marked org-owned (``owner: __org__``) so every user on the instance
sees them (see ORG_OWNER / org_scope_owners — one install == one organization).

Design choices:
  - **Verbatim copy**, not parse→re-emit. Round-tripping a SKILL.md through the
    ``Skill`` dataclass drops non-standard body headings (e.g. ``## Disclaimer``),
    which matters for the mandatory "non sostituisce il professionista" notice on
    the professional verticals. Copying the file byte-for-byte preserves it.
  - **Idempotent, never clobbers**: if the destination SKILL.md already exists it
    is skipped, so re-running setup or a client's local edits are preserved.
    Pass ``overwrite=True`` to refresh shipped skills to a newer bundle version.

Run standalone to (re)seed an existing install:

    python -m services.memory.skill_seed            # seed missing bundles
    python -m services.memory.skill_seed --overwrite  # refresh all bundles
"""

from __future__ import annotations

import logging
import os
import shutil
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Repo root = three levels up from this file (services/memory/skill_seed.py).
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_BUNDLES_DIR = os.path.join(_REPO_ROOT, "bundles", "skills")


def _iter_bundle_files(bundles_dir: str) -> List[str]:
    out: List[str] = []
    if not os.path.isdir(bundles_dir):
        return out
    for root, _dirs, files in os.walk(bundles_dir, followlinks=False):
        if "SKILL.md" in files:
            out.append(os.path.join(root, "SKILL.md"))
    return out


def _validate_bundle(path: str) -> Optional[str]:
    """Return a warning string if the bundle looks misconfigured, else None.

    Non-fatal: a malformed shipped skill should be flagged but must not abort
    seeding of the rest. Checks that it parses and is org-owned + published, so
    every user on the instance actually sees it.
    """
    try:
        from .skill_format import Skill  # lazy: avoid import cost when unused
        from src.constants import ORG_OWNER
    except Exception:  # pragma: no cover - import wiring
        return None
    try:
        with open(path, encoding="utf-8") as f:
            sk = Skill.from_markdown(f.read(), path=path)
    except Exception as e:
        return f"unparseable ({e})"
    issues = []
    if (sk.owner or "") != ORG_OWNER:
        issues.append(f"owner={sk.owner!r} (expected {ORG_OWNER!r})")
    if sk.status != "published":
        issues.append(f"status={sk.status!r} (expected 'published')")
    return "; ".join(issues) or None


def seed_skill_bundles(
    data_dir: str,
    bundles_dir: Optional[str] = None,
    overwrite: bool = False,
) -> Dict[str, object]:
    """Copy shipped skill bundles into ``<data_dir>/skills/`` (idempotent).

    Returns a summary dict: ``{"seeded": [...], "skipped": [...], "warnings": [...]}``
    with destination-relative paths. Existing destinations are skipped unless
    ``overwrite`` is True.
    """
    bundles_dir = bundles_dir or DEFAULT_BUNDLES_DIR
    skills_root = os.path.join(data_dir, "skills")
    seeded: List[str] = []
    skipped: List[str] = []
    warnings: List[str] = []

    files = _iter_bundle_files(bundles_dir)
    if not files:
        logger.info("[skill-seed] no bundles found under %s", bundles_dir)
        return {"seeded": seeded, "skipped": skipped, "warnings": warnings}

    for src in files:
        rel = os.path.relpath(src, bundles_dir)  # e.g. legale/<name>/SKILL.md
        dest = os.path.join(skills_root, rel)
        warn = _validate_bundle(src)
        if warn:
            warnings.append(f"{rel}: {warn}")
        if os.path.exists(dest) and not overwrite:
            skipped.append(rel)
            continue
        try:
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy2(src, dest)
            seeded.append(rel)
        except Exception as e:
            warnings.append(f"{rel}: copy failed ({e})")

    logger.info(
        "[skill-seed] seeded=%d skipped=%d warnings=%d (from %s)",
        len(seeded), len(skipped), len(warnings), bundles_dir,
    )
    return {"seeded": seeded, "skipped": skipped, "warnings": warnings}


def _main(argv: Optional[List[str]] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Seed shipped ArgoDesk skill bundles into data/skills/.")
    parser.add_argument("--overwrite", action="store_true",
                        help="Refresh shipped skills even if the destination already exists.")
    parser.add_argument("--data-dir", default=os.path.join(_REPO_ROOT, "data"),
                        help="Target data directory (default: <repo>/data).")
    parser.add_argument("--bundles-dir", default=DEFAULT_BUNDLES_DIR,
                        help="Source bundles directory.")
    args = parser.parse_args(argv)

    summary = seed_skill_bundles(args.data_dir, args.bundles_dir, overwrite=args.overwrite)
    print(f"  seeded:   {len(summary['seeded'])}")
    for r in summary["seeded"]:
        print(f"    + {r}")
    print(f"  skipped:  {len(summary['skipped'])} (already present)")
    for w in summary["warnings"]:
        print(f"  [warn] {w}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
