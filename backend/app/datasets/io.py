from __future__ import annotations

import hashlib
import json
import os
import tarfile
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable, Iterable


ProgressCallback = Callable[[int, int | None], None]


def file_hash(path: Path, algorithm: str = "sha256", chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def verify_hash(path: Path, expected: str, algorithm: str = "sha256") -> bool:
    return path.is_file() and file_hash(path, algorithm).lower() == expected.lower()


def _content_range_total(header: str | None) -> int | None:
    if not header or "/" not in header:
        return None
    value = header.rsplit("/", 1)[-1]
    return int(value) if value.isdigit() else None


def resumable_download(
    url: str,
    destination: Path,
    *,
    expected_hash: str | None = None,
    hash_algorithm: str = "sha256",
    expected_size: int | None = None,
    retries: int = 3,
    timeout: int = 60,
    progress: ProgressCallback | None = None,
) -> dict:
    """Download using a .part file and HTTP Range when the server supports it."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        size_ok = expected_size is None or destination.stat().st_size == expected_size
        hash_ok = expected_hash is None or verify_hash(destination, expected_hash, hash_algorithm)
        if size_ok and hash_ok:
            return {"status": "already_verified", "bytes": destination.stat().st_size}
        raise ValueError(f"existing file failed verification: {destination}")

    partial = destination.with_name(destination.name + ".part")
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        offset = partial.stat().st_size if partial.exists() else 0
        headers = {"User-Agent": "VisionGuard-AI research dataset client/1.0"}
        if offset:
            headers["Range"] = f"bytes={offset}-"
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                status = getattr(response, "status", 200)
                if offset and status != 206:
                    partial.unlink(missing_ok=True)
                    offset = 0
                total = _content_range_total(response.headers.get("Content-Range"))
                if total is None:
                    length = response.headers.get("Content-Length")
                    total = offset + int(length) if length and length.isdigit() else expected_size
                mode = "ab" if offset and status == 206 else "wb"
                downloaded = offset
                with partial.open(mode) as handle:
                    while chunk := response.read(1024 * 1024):
                        handle.write(chunk)
                        downloaded += len(chunk)
                        if progress:
                            progress(downloaded, total)
            if expected_size is not None and partial.stat().st_size != expected_size:
                raise ValueError(
                    f"size mismatch for {destination.name}: {partial.stat().st_size} != {expected_size}"
                )
            if expected_hash and not verify_hash(partial, expected_hash, hash_algorithm):
                raise ValueError(f"{hash_algorithm} mismatch for {destination.name}")
            os.replace(partial, destination)
            return {"status": "downloaded", "bytes": destination.stat().st_size}
        except (OSError, urllib.error.URLError, ValueError) as error:
            last_error = error
            if attempt < retries:
                time.sleep(min(2 ** attempt, 8))
    raise RuntimeError(f"download failed after {retries} attempts: {url}: {last_error}")


def _safe_target(root: Path, member_name: str) -> Path:
    root = root.resolve()
    target = (root / member_name).resolve()
    if target != root and root not in target.parents:
        raise ValueError(f"archive member escapes extraction root: {member_name}")
    return target


def safe_extract_zip(archive: Path, destination: Path) -> list[Path]:
    destination.mkdir(parents=True, exist_ok=True)
    extracted: list[Path] = []
    with zipfile.ZipFile(archive) as handle:
        for member in handle.infolist():
            target = _safe_target(destination, member.filename)
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with handle.open(member) as source, target.open("wb") as output:
                while chunk := source.read(1024 * 1024):
                    output.write(chunk)
            extracted.append(target)
    return extracted


def safe_extract_tar(archive: Path, destination: Path) -> list[Path]:
    destination.mkdir(parents=True, exist_ok=True)
    extracted: list[Path] = []
    with tarfile.open(archive, "r:*") as handle:
        for member in handle.getmembers():
            target = _safe_target(destination, member.name)
            if member.issym() or member.islnk() or member.isdev():
                raise ValueError(f"unsupported archive member type: {member.name}")
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            if not member.isfile():
                continue
            source = handle.extractfile(member)
            if source is None:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with source, target.open("wb") as output:
                while chunk := source.read(1024 * 1024):
                    output.write(chunk)
            extracted.append(target)
    return extracted


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(temporary, path)


def summarize_files(paths: Iterable[Path]) -> dict:
    items = list(paths)
    return {"file_count": len(items), "total_bytes": sum(path.stat().st_size for path in items if path.is_file())}
