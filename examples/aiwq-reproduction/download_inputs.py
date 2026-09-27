#!/usr/bin/env python3
"""Fetch the 93 pinned public forecasts from ECMWF, then build a local archive.

No auxiliary data or credentials are requested. Existing archives are preserved.
"""
from concurrent.futures import ThreadPoolExecutor
import gzip
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import ssl
import tarfile
import tempfile
import urllib.parse
import urllib.request

import certifi

HERE = Path(__file__).resolve().parent
SOURCE_PREFIX = "https://data.ecmwf.int/ai-weatherquest/by_fc_date/"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        raise ValueError("Unexpected redirect from the pinned ECMWF data origin")


def validate_entry(entry):
    path = PurePosixPath(entry["path"])
    if path.is_absolute() or ".." in path.parts or str(path) != entry["path"]:
        raise ValueError("Unsafe input path")
    if len(path.parts) != 5 or path.parts[0] != "forecasts":
        raise ValueError("Unexpected forecast layout")
    expected_url = SOURCE_PREFIX + path.relative_to("forecasts").as_posix()
    url = urllib.parse.urlsplit(entry["source_url"])
    if (entry["source_url"] != expected_url or url.scheme != "https"
            or url.netloc != "data.ecmwf.int" or url.query or url.fragment):
        raise ValueError("Input URL is outside the declared ECMWF source")
    if not 0 < entry["bytes"] <= 4_000_000 or not re.fullmatch(r"[0-9a-f]{64}", entry["sha256"]):
        raise ValueError("Invalid size or SHA-256")


def fetch_file(entry, root):
    validate_entry(entry)
    context = ssl.create_default_context(cafile=certifi.where())
    opener = urllib.request.build_opener(NoRedirect(), urllib.request.HTTPSHandler(context=context))
    request = urllib.request.Request(entry["source_url"], headers={"User-Agent": "Omytea-scoring-reproduction/1"})
    with opener.open(request, timeout=90) as response:
        payload = response.read(entry["bytes"] + 1)
    if len(payload) != entry["bytes"] or hashlib.sha256(payload).hexdigest() != entry["sha256"]:
        raise ValueError("Changed or incomplete official input: " + entry["path"])
    path = root / entry["path"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def download():
    destination = HERE / "inputs.tar.gz"
    if destination.exists():
        raise ValueError("inputs.tar.gz already exists; kept unchanged. Run reproduce.py to verify it, or move it aside before downloading again.")
    manifest = json.loads((HERE / "input-manifest.json").read_text())
    entries = [entry for entry in manifest["files"] if entry["role"] == "forecast"]
    if len(entries) != 93 or len({entry["path"] for entry in entries}) != 93:
        raise ValueError("Expected exactly 93 unique forecasts")
    for entry in entries:
        validate_entry(entry)
    with tempfile.TemporaryDirectory(prefix="aiwq-download-", dir=HERE) as temporary:
        root = Path(temporary)
        with ThreadPoolExecutor(max_workers=4) as pool:
            for number, _ in enumerate(pool.map(lambda entry: fetch_file(entry, root), entries), 1):
                if number % 10 == 0 or number == len(entries):
                    print(f"Verified {number}/{len(entries)} public forecasts", flush=True)
        archive_path = root / "inputs.tar.gz"
        with archive_path.open("wb") as output, gzip.GzipFile(filename="", mode="wb", fileobj=output, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w") as archive:
                for entry in entries:
                    member = tarfile.TarInfo(entry["path"])
                    member.size, member.mtime, member.mode = entry["bytes"], 0, 0o644
                    with (root / entry["path"]).open("rb") as source:
                        archive.addfile(member, source)
        # Exclusive creation preserves an archive another process may have created.
        with destination.open("xb") as output, archive_path.open("rb") as source:
            shutil.copyfileobj(source, output)
    print("Created inputs.tar.gz; the three hash-pinned auxiliary files are bundled in auxiliary/.")


if __name__ == "__main__":
    try:
        download()
    except (OSError, ValueError, KeyError) as error:
        raise SystemExit(f"Download failed: {error}") from error
