"""ANV-027: offline build/CI runtime identity; no operational DB is opened."""

import argparse
import json

from anvesha.sqlite_runtime import inspect_runtime, require_runtime


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-sqlite")
    args = parser.parse_args()
    report = inspect_runtime()
    print(json.dumps(report, indent=2))
    require_runtime()
    if args.expected_sqlite and report["sqlite_version"] != args.expected_sqlite:
        raise SystemExit("SQLite differs from the reviewed build; review runtime provenance")


if __name__ == "__main__":
    main()
