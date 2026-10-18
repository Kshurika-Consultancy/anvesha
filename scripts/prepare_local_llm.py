"""ANV-023: explicit pinned CPU runtime/weight acquisition; never runs a model.

Windows bootstrap only. Other hosts may supply their own compatible local runtime.
No default test or search command calls this script. About 2.52 GB is downloaded.
"""

import argparse
import hashlib
import json
import shutil
import stat
import tempfile
import time
import zipfile
from pathlib import Path, PurePosixPath
from urllib.parse import urljoin, urlsplit

import httpx

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "policies/models/qwen3-4b-instruct2507.json"


def file_digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def download(item, path):
    if path.exists():
        if path.stat().st_size != item["bytes"] or file_digest(path) != item["sha256"]:
            raise ValueError("Existing artifact does not match its pin; preserving it")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        started = time.monotonic()
        with httpx.Client(trust_env=False, follow_redirects=False, timeout=30) as client:
            url = item["url"]
            for _ in range(6):
                host = urlsplit(url).hostname or ""
                if urlsplit(url).scheme != "https" or not (
                    host
                    in {"github.com", "release-assets.githubusercontent.com", "registry.ollama.ai"}
                    or host.endswith(".r2.cloudflarestorage.com")
                ):
                    raise ValueError("Unapproved artifact redirect")
                with client.stream("GET", url, headers={"Accept-Encoding": "identity"}) as response:
                    if response.status_code in {301, 302, 303, 307, 308}:
                        url = urljoin(url, response.headers.get("location", ""))
                        continue
                    if response.status_code != 200:
                        raise ValueError(f"Artifact download returned HTTP {response.status_code}")
                    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as output:
                        temporary = Path(output.name)
                        size, progress = 0, 0
                        for chunk in response.iter_raw(1024 * 1024):
                            size += len(chunk)
                            if size > item["bytes"] or time.monotonic() - started > 1800:
                                raise ValueError("Artifact exceeds byte/time budget")
                            output.write(chunk)
                            if size - progress >= 128 * 1024 * 1024:
                                progress = size
                                print(f"Downloaded {size}/{item['bytes']} bytes", flush=True)
                    if size != item["bytes"] or file_digest(temporary) != item["sha256"]:
                        raise ValueError("Artifact size/SHA-256 mismatch")
                    temporary.replace(path)
                    return
            raise ValueError("Too many artifact redirects")
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def extract_runtime(archive, destination):
    if destination.exists():
        raise ValueError("Runtime directory exists; refusing to overwrite it")
    destination = destination.resolve()
    with zipfile.ZipFile(archive) as source:
        members = source.infolist()
        if len(members) > 1000 or sum(item.file_size for item in members) > 200_000_000:
            raise ValueError("Runtime archive exceeds extraction budget")
        for item in members:
            name = PurePosixPath(item.filename)
            if (
                name.is_absolute()
                or ".." in name.parts
                or "\\" in item.orig_filename
                or ":" in item.filename
                or stat.S_ISLNK(item.external_attr >> 16)
            ):
                raise ValueError("Unsafe runtime archive member")
            if not (destination / item.filename).resolve().is_relative_to(destination):
                raise ValueError("Runtime archive escapes destination")
        destination.mkdir(parents=True)
        for item in members:
            target = destination / item.filename
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with source.open(item) as incoming, target.open("xb") as output:
                    shutil.copyfileobj(incoming, output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--download",
        action="store_true",
        required=True,
        help="Explicitly download about 2.52 GB; no inference or installation",
    )
    parser.add_argument("--workspace", type=Path, default=ROOT / ".anvesha/local-llm/anv023")
    args = parser.parse_args()
    manifest = json.loads(MANIFEST.read_bytes())
    workspace = args.workspace.resolve()
    download(manifest["runtime"], workspace / "runtime.zip")
    if not (workspace / "runtime").exists():
        extract_runtime(workspace / "runtime.zip", workspace / "runtime")
    download(manifest["model"], workspace / "model.gguf")
    print("Pinned runtime/model verified. Nothing was started; see docs/LOCAL_LLM_EVALUATION.md.")


if __name__ == "__main__":
    main()
