"""ANV-023: no live download; integrity and extraction boundary regressions."""

import importlib.util
import zipfile
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/prepare_local_llm.py"
SPEC = importlib.util.spec_from_file_location("prepare_local_llm", SCRIPT)
bootstrap = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bootstrap)


def test_corrupt_existing_download_is_preserved_without_contacting_network(tmp_path, monkeypatch):
    path = tmp_path / "artifact"
    path.write_bytes(b"existing")
    monkeypatch.setattr(bootstrap.httpx, "Client", lambda **kwargs: pytest.fail("No network"))
    with pytest.raises(ValueError, match="preserving"):
        bootstrap.download({"bytes": 2, "sha256": "a" * 64}, path)
    assert path.read_bytes() == b"existing"


@pytest.mark.parametrize("name", ["../escape", "/absolute", "C:/escape", "a\\escape"])
def test_unsafe_zip_member_never_writes_outside_destination(tmp_path, name):
    archive = tmp_path / "fixture.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr(name.replace("\\", "/"), b"untrusted")
    if "\\" in name:
        # ZipInfo normalizes Windows separators when writing; simulate a foreign ZIP.
        archive.write_bytes(
            archive.read_bytes().replace(name.replace("\\", "/").encode(), name.encode())
        )
    target = tmp_path / "runtime"
    with pytest.raises(ValueError):
        bootstrap.extract_runtime(archive, target)
    assert not target.exists()
    assert not (tmp_path / "escape").exists()


def test_existing_runtime_is_never_overwritten(tmp_path):
    target = tmp_path / "runtime"
    target.mkdir()
    with pytest.raises(ValueError, match="overwrite"):
        bootstrap.extract_runtime(tmp_path / "unused.zip", target)


def test_benign_extraction_preserves_bytes(tmp_path):
    archive = tmp_path / "fixture.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("lib/fixture.txt", b"synthetic")
    bootstrap.extract_runtime(archive, tmp_path / "runtime")
    assert (tmp_path / "runtime/lib/fixture.txt").read_bytes() == b"synthetic"
