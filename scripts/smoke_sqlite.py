"""ANV-027: synthetic multiprocess WAL/checkpoint and crash-recovery acceptance.

Application compatibility/integrity evidence, never proof of the upstream race fix.
No network, actual operational/review databases, model weights or paid APIs.
"""

import argparse
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
from contextlib import closing
from pathlib import Path

from anvesha.cli import DEMO_DOCUMENTS
from anvesha.sqlite_runtime import inspect_runtime, require_runtime
from anvesha.store import Store


def writer(path, index):
    store = Store(path)
    for number in range(24):
        key = f"synthetic-{index}-{number}"
        job, created = store.create_search(
            "synthetic-owner", "Anvesha", ["local"], idempotency_key=key
        )
        assert created
        replay, created = store.create_search(
            "synthetic-owner", "Anvesha", ["local"], idempotency_key=key
        )
        assert not created and replay["id"] == job["id"]
        claim = store.claim_job(f"synthetic-worker-{index}")
        assert claim is not None
        assert store.finish_job(claim["id"], claim["lease_token"], [])
        store.submit_feedback("synthetic-owner", claim["id"], 1, None, 1)


def checkpoint(path):
    with closing(sqlite3.connect(path, timeout=30, isolation_level=None)) as db:
        path.with_suffix(".ready").touch()
        deadline = time.monotonic() + 45
        while not path.with_suffix(".stop").exists():
            if time.monotonic() >= deadline:
                raise RuntimeError("Synthetic checkpoint process exceeded its deadline")
            db.execute("PRAGMA wal_checkpoint(PASSIVE)").fetchone()
            time.sleep(0.005)


def crash(path):
    db = sqlite3.connect(path, isolation_level=None)
    db.execute("PRAGMA synchronous=FULL")
    db.execute("INSERT INTO crash_probe VALUES ('committed')")
    db.execute("BEGIN IMMEDIATE")
    db.execute("INSERT INTO crash_probe VALUES ('uncommitted')")
    os._exit(19)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--child", choices=["writer", "checkpoint", "crash"])
    parser.add_argument("--path", type=Path)
    parser.add_argument("--index", type=int, default=0)
    args = parser.parse_args()
    require_runtime()
    if args.child:
        if args.child == "writer":
            writer(args.path, args.index)
        elif args.child == "checkpoint":
            checkpoint(args.path)
        else:
            crash(args.path)
        return
    with tempfile.TemporaryDirectory(prefix="anvesha-sqlite-synthetic-") as temporary:
        path = Path(temporary) / "synthetic.db"
        store = Store(path)
        store.initialize()
        for document in DEMO_DOCUMENTS:
            store.upsert_document(document)
        with closing(sqlite3.connect(path, isolation_level=None)) as db:
            db.execute("CREATE TABLE crash_probe(value TEXT)")
        children = []

        def launch(mode, index=0):
            child = subprocess.Popen(
                [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "--child",
                    mode,
                    "--path",
                    str(path),
                    "--index",
                    str(index),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            children.append(child)
            return child

        def finished(child, expected=0):
            _, errors = child.communicate(timeout=50)
            if child.returncode != expected:
                raise RuntimeError(f"Synthetic SQLite process failed: {errors[:2000]}")

        try:
            checkpointer = launch("checkpoint")
            ready_by = time.monotonic() + 10
            while not path.with_suffix(".ready").exists():
                if checkpointer.poll() is not None or time.monotonic() >= ready_by:
                    raise RuntimeError("Synthetic checkpointer did not become ready")
                time.sleep(0.01)
            writers = [launch("writer", index) for index in range(3)]
            for child in writers:
                finished(child)
            path.with_suffix(".stop").touch()
            finished(checkpointer)
            finished(launch("crash"), expected=19)
            # Fresh connection after abrupt process exit must recover correctly.
            with closing(sqlite3.connect(path, isolation_level=None)) as db:
                assert db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
                assert db.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
                assert db.execute("PRAGMA foreign_key_check").fetchall() == []
                assert db.execute("SELECT count(*) FROM jobs").fetchone()[0] == 72
                assert (
                    db.execute(
                        "SELECT count(*) FROM jobs WHERE state='completed' AND results_version=1"
                    ).fetchone()[0]
                    == 72
                )
                assert db.execute("SELECT count(*) FROM snapshots").fetchone()[0] == 72
                assert db.execute("SELECT count(*) FROM feedback").fetchone()[0] == 72
                assert db.execute("SELECT * FROM crash_probe").fetchall() == [("committed",)]
                db.execute(
                    "INSERT INTO documents_fts(documents_fts, rank) VALUES ('integrity-check', 1)"
                )
            assert len(Store(path).search_local("Anvesha")) == 3
        finally:
            for child in children:
                if child.poll() is None:
                    child.kill()
                child.communicate(timeout=10)
    print(
        f"SQLite {inspect_runtime()['sqlite_version']} acceptance passed: three writers, "
        "concurrent checkpoints, 72 durable jobs/snapshots/feedback, FTS/FK integrity, "
        "crash rollback, scoped process/data cleanup. This does not prove the upstream race fix."
    )


if __name__ == "__main__":
    main()
