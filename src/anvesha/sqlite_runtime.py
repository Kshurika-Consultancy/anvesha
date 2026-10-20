"""ANV-027: offline SQLite runtime identity and conservative WAL eligibility.

This checks upstream release numbers, not binary authenticity or every vendor
backport. Older vendor builds need a reviewed policy change, never an env bypass.
"""

import platform
import sqlite3
from contextlib import closing
from functools import lru_cache

UPDATE_GUIDE = "docs/SQLITE_RUNTIME.md"


def upstream_wal_fix(version: str) -> bool:
    """SQLite's documented fixed branches; adjacent branches are not backports."""
    parts = version.split(".")
    if len(parts) != 3 or any(not p.isascii() or not p.isdecimal() for p in parts):
        return False
    release = tuple(map(int, parts))
    return (
        release >= (3, 51, 3)
        or (release[:2] == (3, 50) and release[2] >= 7)
        or (release[:2] == (3, 44) and release[2] >= 6)
    )


@lru_cache(maxsize=1)
def inspect_runtime() -> dict:
    """Probe only an in-memory DB; never open a user's data or use the network."""
    with closing(sqlite3.connect(":memory:")) as connection:
        version, source_id = connection.execute(
            "SELECT sqlite_version(), sqlite_source_id()"
        ).fetchone()
        try:
            connection.execute("CREATE VIRTUAL TABLE probe USING fts5(content)")
            fts5 = True
        except sqlite3.OperationalError:
            fts5 = False
    fixed = upstream_wal_fix(version)
    return {
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "sqlite_version": version,
        "sqlite_source_id": source_id,
        "fts5_available": fts5,
        "wal_reset_fix": "upstream_fixed_release" if fixed else "unverified",
        "supported": fixed and fts5,
        "evidence_basis": "upstream_release_policy; not_binary_attestation_or_race_test",
        "update_guide": UPDATE_GUIDE,
    }


def require_runtime() -> None:
    report = inspect_runtime()
    if not report["supported"]:
        raise ValueError(
            f"SQLite {report['sqlite_version']} is not supported for Anvesha WAL storage "
            f"(WAL-reset fix: {report['wal_reset_fix']}; "
            f"FTS5 available: {report['fts5_available']}). "
            f"Install the reviewed Python runtime; see {UPDATE_GUIDE}. "
            "Older vendor backports require explicit maintainer review."
        )
