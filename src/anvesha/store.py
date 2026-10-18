"""Transactional local storage for jobs, immutable results, feedback and documents.

Task ANV-003. Connections are deliberately short lived so the API and worker can
operate independently against the same local SQLite file.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

PIPELINE_VERSION = "m1-rrf-v1"


class IdempotencyConflict(ValueError):
    """An existing client key describes a different search request."""


class FeedbackError(ValueError):
    """Feedback does not reference an accessible published result snapshot."""


_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    owner TEXT NOT NULL,
    query TEXT NOT NULL,
    sources_json TEXT NOT NULL,
    result_limit INTEGER NOT NULL,
    request_hash TEXT NOT NULL,
    idempotency_key TEXT,
    state TEXT NOT NULL CHECK (state IN
        ('queued', 'running', 'completed', 'completed_partial', 'failed', 'cancelled')),
    phase TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    results_version INTEGER NOT NULL DEFAULT 0,
    warnings_json TEXT NOT NULL DEFAULT '[]',
    error_code TEXT,
    pipeline_version TEXT NOT NULL,
    ranking TEXT NOT NULL DEFAULT 'lexical',
    worker_id TEXT,
    lease_token TEXT,
    lease_until REAL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    UNIQUE (owner, idempotency_key)
);
CREATE INDEX IF NOT EXISTS jobs_claim ON jobs(state, lease_until, created_at);
CREATE TABLE IF NOT EXISTS snapshots (
    job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    results_json TEXT NOT NULL,
    total INTEGER NOT NULL,
    PRIMARY KEY (job_id, version)
);
CREATE TABLE IF NOT EXISTS feedback (
    id TEXT PRIMARY KEY,
    owner TEXT NOT NULL,
    job_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    result_key TEXT NOT NULL,
    rating INTEGER NOT NULL CHECK (rating IN (-1, 1)),
    reason TEXT,
    comment TEXT,
    learning_opt_in INTEGER NOT NULL CHECK (learning_opt_in IN (0, 1)),
    pipeline_version TEXT NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    FOREIGN KEY (job_id, version) REFERENCES snapshots(job_id, version)
        ON DELETE CASCADE,
    UNIQUE (owner, job_id, version, result_key)
);
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    license TEXT NOT NULL,
    attribution TEXT NOT NULL
);
CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
    title, content, content='documents', content_rowid='rowid'
);
CREATE TRIGGER IF NOT EXISTS documents_insert AFTER INSERT ON documents BEGIN
    INSERT INTO documents_fts(rowid, title, content)
    VALUES (new.rowid, new.title, new.content);
END;
CREATE TRIGGER IF NOT EXISTS documents_delete AFTER DELETE ON documents BEGIN
    INSERT INTO documents_fts(documents_fts, rowid, title, content)
    VALUES ('delete', old.rowid, old.title, old.content);
END;
CREATE TRIGGER IF NOT EXISTS documents_update AFTER UPDATE ON documents BEGIN
    INSERT INTO documents_fts(documents_fts, rowid, title, content)
    VALUES ('delete', old.rowid, old.title, old.content);
    INSERT INTO documents_fts(rowid, title, content)
    VALUES (new.rowid, new.title, new.content);
END;
"""


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def _positive_integer(value: int, name: str) -> None:
    if type(value) is not int or value < 1:
        raise ValueError(f"{name} must be a positive integer")


def _bounded_text(value: str, name: str, maximum: int) -> None:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f"{name} must be nonblank text up to {maximum} characters")


def _job(row: sqlite3.Row) -> dict:
    result = dict(row)
    result["sources"] = json.loads(result.pop("sources_json"))
    result["warnings"] = json.loads(result.pop("warnings_json"))
    result["limit"] = result.pop("result_limit")
    result.pop("request_hash")
    result.pop("idempotency_key")
    return result


def _feedback(row: sqlite3.Row) -> dict:
    result = dict(row)
    result["result_id"] = result.pop("result_key") or None
    result["learning_opt_in"] = bool(result["learning_opt_in"])
    return result


class Store:
    """A single-host store. Call initialize before using a new database."""

    def __init__(self, path: str | Path):
        if str(path) == ":memory:":
            raise ValueError("Store requires a persistent database file")
        self.path = Path(path).expanduser().resolve()

    def _open(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        # FULL also preserves accepted WAL commits across an OS/power failure,
        # subject to the guarantees of the underlying local filesystem.
        connection.execute("PRAGMA synchronous = FULL")
        return connection

    @contextmanager
    def _connection(self, *, write: bool = False) -> Iterator[sqlite3.Connection]:
        connection = self._open()
        try:
            connection.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = self._open()
        try:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(_SCHEMA)
            # ANV-021: additive, serialized migration preserves accepted old jobs,
            # their request hashes, snapshots and feedback. Upgrade every worker
            # before enabling LLM requests on an existing instance.
            connection.execute("BEGIN IMMEDIATE")
            columns = {row["name"] for row in connection.execute("PRAGMA table_info(jobs)")}
            if "ranking" not in columns:
                connection.execute(
                    "ALTER TABLE jobs ADD COLUMN ranking TEXT NOT NULL DEFAULT 'lexical'"
                )
            connection.commit()
        finally:
            connection.close()

    def create_search(
        self,
        owner: str,
        query: str,
        sources: list[str],
        limit: int = 10,
        idempotency_key: str | None = None,
        *,
        ranking: str = "lexical",
        pipeline_version: str | None = None,
    ) -> tuple[dict, bool]:
        _bounded_text(owner, "owner", 256)
        _bounded_text(query, "query", 2000)
        if ranking not in {"lexical", "llm"}:
            raise ValueError("ranking must be lexical or llm")
        if ranking == "llm":
            if not isinstance(pipeline_version, str) or not re.fullmatch(
                r"m3-llm-rerank-v1-[a-f0-9]{16}", pipeline_version
            ):
                raise ValueError("LLM requests require a versioned configuration")
        else:
            pipeline_version = PIPELINE_VERSION
        _positive_integer(limit, "limit")
        if limit > 50:
            raise ValueError("limit cannot exceed 50")
        if not isinstance(sources, (list, tuple)) or not sources:
            raise ValueError("sources must contain at least one source")
        for source in sources:
            _bounded_text(source, "source", 100)
        canonical_sources = sorted(set(sources))
        if ranking == "llm" and canonical_sources != ["local"]:
            raise ValueError("LLM preview supports local documents only")
        if idempotency_key is not None:
            _bounded_text(idempotency_key, "idempotency_key", 200)
        request = [query, canonical_sources, limit]
        if ranking != "lexical":
            request.append(ranking)
        request_hash = hashlib.sha256(_json(request).encode("utf-8")).hexdigest()
        with self._connection(write=True) as connection:
            if idempotency_key is not None:
                existing = connection.execute(
                    "SELECT * FROM jobs WHERE owner = ? AND idempotency_key = ?",
                    (owner, idempotency_key),
                ).fetchone()
                if existing is not None:
                    if existing["request_hash"] != request_hash:
                        raise IdempotencyConflict("key already used for another request")
                    return _job(existing), False
            job_id = f"srch_{uuid.uuid4().hex}"
            now = time.time()
            connection.execute(
                """INSERT INTO jobs
                   (id, owner, query, sources_json, result_limit, request_hash,
                    idempotency_key, state, phase, pipeline_version, ranking, created_at,
                    updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'queued', 'queued', ?, ?, ?, ?)""",
                (
                    job_id,
                    owner,
                    query,
                    _json(canonical_sources),
                    limit,
                    request_hash,
                    idempotency_key,
                    pipeline_version,
                    ranking,
                    now,
                    now,
                ),
            )
            return _job(
                connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
            ), True

    def get_job(self, owner: str, job_id: str) -> dict | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM jobs WHERE id = ? AND owner = ?", (job_id, owner)
            ).fetchone()
            return _job(row) if row is not None else None

    def claim_job(
        self, worker_id: str, lease_seconds: int = 60, max_attempts: int = 3
    ) -> dict | None:
        _bounded_text(worker_id, "worker_id", 200)
        _positive_integer(lease_seconds, "lease_seconds")
        _positive_integer(max_attempts, "max_attempts")
        with self._connection(write=True) as connection:
            now = time.time()
            connection.execute(
                """UPDATE jobs SET state = 'failed', phase = 'failed',
                       error_code = 'worker_attempts_exhausted', updated_at = ?,
                       lease_token = NULL, lease_until = NULL, worker_id = NULL
                   WHERE state = 'running' AND lease_until <= ? AND attempts >= ?""",
                (now, now, max_attempts),
            )
            row = connection.execute(
                """SELECT id FROM jobs WHERE attempts < ? AND
                     (state = 'queued' OR (state = 'running' AND lease_until <= ?))
                   ORDER BY created_at, id LIMIT 1""",
                (max_attempts, now),
            ).fetchone()
            if row is None:
                return None
            connection.execute(
                """UPDATE jobs SET state = 'running', phase = 'retrieving',
                       attempts = attempts + 1, worker_id = ?, lease_token = ?,
                       lease_until = ?, updated_at = ? WHERE id = ?""",
                (
                    worker_id,
                    uuid.uuid4().hex,
                    now + lease_seconds,
                    now,
                    row["id"],
                ),
            )
            return _job(
                connection.execute("SELECT * FROM jobs WHERE id = ?", (row["id"],)).fetchone()
            )

    def heartbeat(
        self,
        job_id: str,
        lease_token: str,
        lease_seconds: int = 60,
        phase: str | None = None,
    ) -> bool:
        _positive_integer(lease_seconds, "lease_seconds")
        if phase is not None:
            _bounded_text(phase, "phase", 100)
        with self._connection(write=True) as connection:
            now = time.time()
            changed = connection.execute(
                """UPDATE jobs SET lease_until = ?, updated_at = ?,
                       phase = COALESCE(?, phase)
                   WHERE id = ? AND state = 'running' AND lease_token = ?
                     AND lease_until > ?""",
                (now + lease_seconds, now, phase, job_id, lease_token, now),
            )
            return changed.rowcount == 1

    def finish_job(
        self,
        job_id: str,
        lease_token: str,
        results: list[dict],
        warnings: list[str] | None = None,
        partial: bool = False,
        error_code: str | None = None,
    ) -> bool:
        if not isinstance(results, list):
            raise ValueError("results must be a list")
        result_ids = []
        for result in results:
            if not isinstance(result, dict):
                raise ValueError("each result must be an object")
            _bounded_text(result.get("id"), "result id", 200)
            result_ids.append(result["id"])
        if len(result_ids) != len(set(result_ids)):
            raise ValueError("result IDs must be unique")
        results_json = _json(results)
        if warnings is None:
            warnings = []
        if not isinstance(warnings, list) or any(
            not isinstance(warning, str) for warning in warnings
        ):
            raise ValueError("warnings must be a list of strings")
        warnings_json = _json(
            [re.sub(r"[\x00-\x1f\x7f]", "", warning)[:200] for warning in warnings[:20]]
        )
        if error_code is not None and (
            not isinstance(error_code, str)
            or re.fullmatch(r"[A-Za-z0-9_:-]{1,100}", error_code) is None
        ):
            raise ValueError("error_code must be a bounded machine-readable code")
        with self._connection(write=True) as connection:
            now = time.time()
            row = connection.execute(
                """SELECT id FROM jobs WHERE id = ? AND state = 'running'
                   AND lease_token = ? AND lease_until > ?""",
                (job_id, lease_token, now),
            ).fetchone()
            if row is None:
                return False
            if error_code is not None:
                state, version = "failed", 0
            else:
                state, version = "completed_partial" if partial else "completed", 1
                connection.execute(
                    "INSERT INTO snapshots VALUES (?, ?, ?, ?)",
                    (job_id, version, results_json, len(results)),
                )
            connection.execute(
                """UPDATE jobs SET state = ?, phase = ?, results_version = ?,
                       warnings_json = ?, error_code = ?, updated_at = ?,
                       lease_token = NULL, lease_until = NULL, worker_id = NULL
                   WHERE id = ?""",
                (state, state, version, warnings_json, error_code, now, job_id),
            )
            return True

    def cancel_job(self, owner: str, job_id: str) -> dict | None:
        with self._connection(write=True) as connection:
            connection.execute(
                """UPDATE jobs SET state = 'cancelled', phase = 'cancelled',
                       updated_at = ?, lease_token = NULL, lease_until = NULL,
                       worker_id = NULL
                   WHERE id = ? AND owner = ? AND state IN ('queued', 'running')""",
                (time.time(), job_id, owner),
            )
            row = connection.execute(
                "SELECT * FROM jobs WHERE id = ? AND owner = ?", (job_id, owner)
            ).fetchone()
            return _job(row) if row is not None else None

    def delete_job(self, owner: str, job_id: str) -> bool:
        with self._connection(write=True) as connection:
            changed = connection.execute(
                "DELETE FROM jobs WHERE id = ? AND owner = ?", (job_id, owner)
            )
            return changed.rowcount == 1

    def get_results(
        self,
        owner: str,
        job_id: str,
        version: int | None = None,
        offset: int = 0,
        limit: int = 10,
    ) -> dict | None:
        if type(offset) is not int or offset < 0:
            raise ValueError("offset must be a nonnegative integer")
        _positive_integer(limit, "limit")
        with self._connection() as connection:
            job = connection.execute(
                "SELECT results_version FROM jobs WHERE id = ? AND owner = ?",
                (job_id, owner),
            ).fetchone()
            if job is None:
                return None
            current = job["results_version"]
            if version is not None and (type(version) is not int or version != current):
                raise ValueError("requested result version does not exist")
            if current == 0:
                return {"version": 0, "results": [], "total": 0}
            row = connection.execute(
                "SELECT results_json, total FROM snapshots WHERE job_id = ? AND version = ?",
                (job_id, current),
            ).fetchone()
            return {
                "version": current,
                "results": json.loads(row["results_json"])[offset : offset + limit],
                "total": row["total"],
            }

    def submit_feedback(
        self,
        owner: str,
        job_id: str,
        version: int,
        result_id: str | None,
        rating: int,
        reason: str | None = None,
        comment: str | None = None,
        learning_opt_in: bool = False,
    ) -> dict:
        if type(rating) is not int or rating not in (-1, 1):
            raise FeedbackError("rating must be -1 or 1")
        if type(version) is not int or version < 1:
            raise FeedbackError("version must identify a published snapshot")
        if type(learning_opt_in) is not bool:
            raise FeedbackError("learning_opt_in must be a boolean")
        if result_id is not None and (
            not isinstance(result_id, str) or not result_id or len(result_id) > 200
        ):
            raise FeedbackError("result_id must identify a published result")
        for value, name, maximum in (
            (reason, "reason", 100),
            (comment, "comment", 2000),
        ):
            if value is not None and (not isinstance(value, str) or len(value) > maximum):
                raise FeedbackError(f"{name} exceeds its allowed length")
        with self._connection(write=True) as connection:
            row = connection.execute(
                """SELECT snapshots.results_json, jobs.pipeline_version
                   FROM snapshots JOIN jobs ON jobs.id = snapshots.job_id
                   WHERE jobs.id = ? AND jobs.owner = ? AND snapshots.version = ?""",
                (job_id, owner, version),
            ).fetchone()
            if row is None:
                raise FeedbackError("published snapshot not found")
            if result_id is not None and not any(
                result["id"] == result_id for result in json.loads(row["results_json"])
            ):
                raise FeedbackError("result is not part of the published snapshot")
            now = time.time()
            connection.execute(
                """INSERT INTO feedback
                   (id, owner, job_id, version, result_key, rating, reason, comment,
                    learning_opt_in, pipeline_version, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT (owner, job_id, version, result_key) DO UPDATE SET
                       rating = excluded.rating, reason = excluded.reason,
                       comment = excluded.comment,
                       learning_opt_in = excluded.learning_opt_in,
                       updated_at = excluded.updated_at""",
                (
                    f"fb_{uuid.uuid4().hex}",
                    owner,
                    job_id,
                    version,
                    result_id or "",
                    rating,
                    reason,
                    comment,
                    int(learning_opt_in),
                    row["pipeline_version"],
                    now,
                    now,
                ),
            )
            return _feedback(
                connection.execute(
                    """SELECT * FROM feedback
                       WHERE owner = ? AND job_id = ? AND version = ? AND result_key = ?""",
                    (owner, job_id, version, result_id or ""),
                ).fetchone()
            )

    def upsert_document(self, document: dict) -> None:
        fields = ("id", "url", "title", "content", "license", "attribution")
        for field in fields:
            if not isinstance(document.get(field), str) or not document[field].strip():
                raise ValueError(f"document {field} must be nonblank text")
        with self._connection(write=True) as connection:
            connection.execute(
                """INSERT INTO documents (id, url, title, content, license, attribution)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT (id) DO UPDATE SET url = excluded.url,
                       title = excluded.title, content = excluded.content,
                       license = excluded.license, attribution = excluded.attribution""",
                tuple(document[field] for field in fields),
            )

    def search_local(self, query: str, limit: int = 20) -> list[dict]:
        if not isinstance(query, str):
            raise ValueError("query must be text")
        _positive_integer(limit, "limit")
        # Do not expose the FTS query language to callers. Bounding query tokens
        # also prevents deeply nested/very large MATCH expressions.
        tokens = list(dict.fromkeys(re.findall(r"[^\W_]+", query[:2000])))[:64]
        if not tokens:
            return []
        expression = " OR ".join(f'"{token}"' for token in tokens)
        with self._connection() as connection:
            rows = connection.execute(
                """SELECT d.url, d.title, d.license, d.attribution,
                          snippet(documents_fts, 1, '', '', ' … ', 48) AS snippet
                   FROM documents_fts JOIN documents d ON d.rowid = documents_fts.rowid
                   WHERE documents_fts MATCH ?
                   ORDER BY bm25(documents_fts, 2.0, 1.0), d.id LIMIT ?""",
                (expression, limit),
            ).fetchall()
            return [
                {
                    **dict(row),
                    "source": "local",
                    "source_rank": rank,
                    "evidence_status": "local_document",
                }
                for rank, row in enumerate(rows, start=1)
            ]
