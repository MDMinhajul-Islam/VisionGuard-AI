from __future__ import annotations

import argparse
import json
import random
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.datasets.io import file_hash, resumable_download, write_json


DATA_ROOT = PROJECT_ROOT / "data" / "external"
UR_BASE = "https://fenix.ur.edu.pl/~mkepski/ds/data"
UR_LICENSE = "CC BY-NC-SA 4.0; non-commercial academic use"
UR_PAGE = "https://fenix.ur.edu.pl/~mkepski/ds/uf.html"
IKAR_DOI = "doi:10.58032/AGH/A1NZPE"
IKAR_API = "https://agh.rodbuk.pl/api"
IKAR_MD5 = "2667661c258610c0c0aa4bc58a7fc7c2"
FALLVISION_DOI = "doi:10.7910/DVN/75QPKK"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def progress(name: str):
    last = -1
    def report(done: int, total: int | None):
        nonlocal last
        percent = int(done * 100 / total) if total else -1
        if percent < 0 or percent >= last + 5 or percent == 100:
            last = percent
            total_text = f"/{total / 1024 / 1024:.1f}" if total else ""
            print(f"{name}: {done / 1024 / 1024:.1f}{total_text} MiB" + (f" ({percent}%)" if percent >= 0 else ""), flush=True)
    return report


def fetch_json(url: str, timeout: int = 60) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "VisionGuard-AI research dataset client/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def selected_ur_ids(seed: int, falls: int, non_falls: int) -> tuple[list[int], list[int]]:
    rng = random.Random(seed)
    return sorted(rng.sample(range(1, 31), falls)), sorted(rng.sample(range(1, 41), non_falls))


def download_ur(seed: int, falls: int, non_falls: int) -> Path:
    root = DATA_ROOT / "ur_fall"
    archives = root / "archives"
    fall_ids, adl_ids = selected_ur_ids(seed, falls, non_falls)
    records = []
    annotation_files = []
    for filename in ("urfall-cam0-falls.csv", "urfall-cam0-adls.csv"):
        url = f"{UR_BASE}/{filename}"
        destination = archives / filename
        result = resumable_download(url, destination, retries=4, progress=progress(filename))
        annotation_files.append({
            "filename": filename, "source_url": url, "bytes": destination.stat().st_size,
            "sha256": file_hash(destination), "download_status": result["status"],
        })
    for kind, identifiers in (("fall", fall_ids), ("adl", adl_ids)):
        for number in identifiers:
            sequence = f"{kind}-{number:02d}"
            files = [f"{sequence}-cam0-rgb.zip", f"{sequence}-data.csv"]
            receipt = {"sequence_id": sequence, "evaluation_label": "fall" if kind == "fall" else "non_fall", "files": []}
            for filename in files:
                url = f"{UR_BASE}/{filename}"
                destination = archives / filename
                result = resumable_download(url, destination, retries=4, progress=progress(filename))
                receipt["files"].append({
                    "filename": filename, "source_url": url, "bytes": destination.stat().st_size,
                    "sha256": file_hash(destination), "download_status": result["status"],
                })
            records.append(receipt)
    manifest = {
        "schema_version": "1.0", "dataset": "UR Fall Detection", "dataset_page": UR_PAGE,
        "license": UR_LICENSE, "downloaded_at": utc_now(), "seed": seed,
        "selection": {"fall_ids": fall_ids, "adl_ids": adl_ids},
        "source_annotation_files": annotation_files, "records": records,
    }
    path = root / "download_manifest.json"
    write_json(path, manifest)
    print(f"Wrote {path}")
    return path


def download_ikar() -> Path:
    root = DATA_ROOT / "ikar"
    query = urllib.parse.urlencode({"persistentId": IKAR_DOI})
    metadata = fetch_json(f"{IKAR_API}/datasets/:persistentId/?{query}", timeout=90)
    version = metadata["data"]["latestVersion"]
    files = version.get("files", [])
    archive_file = next(item["dataFile"] for item in files if item["dataFile"]["filename"] == "IKAR_dataset.tar.gz")
    destination = root / "archives" / "IKAR_dataset.tar.gz"
    result = resumable_download(
        f"{IKAR_API}/access/datafile/{archive_file['id']}", destination,
        expected_hash=IKAR_MD5, hash_algorithm="md5", expected_size=archive_file.get("filesize"),
        retries=4, timeout=90, progress=progress(destination.name),
    )
    receipt = {
        "schema_version": "1.0", "dataset": "IKAR", "version": version.get("versionNumber"),
        "persistent_id": IKAR_DOI, "license": version.get("license", {}).get("name", "CC BY 4.0"),
        "downloaded_at": utc_now(), "filename": destination.name, "bytes": destination.stat().st_size,
        "md5": file_hash(destination, "md5"), "sha256": file_hash(destination),
        "source_url": f"{IKAR_API}/access/datafile/{archive_file['id']}", "download_status": result["status"],
    }
    path = root / "download_manifest.json"
    write_json(path, receipt)
    print(f"Wrote {path}")
    return path


def inspect_fallvision() -> Path:
    query = urllib.parse.urlencode({"persistentId": FALLVISION_DOI})
    payload = fetch_json(f"https://dataverse.harvard.edu/api/datasets/:persistentId/?{query}")
    version = payload["data"]["latestVersion"]
    inventory = [{
        "id": item["dataFile"]["id"], "filename": item["dataFile"]["filename"],
        "bytes": item["dataFile"].get("filesize"), "md5": item["dataFile"].get("md5"),
        "content_type": item["dataFile"].get("contentType"), "restricted": item.get("restricted", False),
    } for item in version.get("files", [])]
    report = {
        "dataset": "FallVision", "persistent_id": FALLVISION_DOI,
        "version": version.get("versionNumber"), "release_time": version.get("releaseTime"),
        "license": version.get("license", {}).get("name"), "inspected_at": utc_now(),
        "files": inventory,
    }
    path = DATA_ROOT / "fallvision" / "file_inventory.json"
    write_json(path, report)
    print(f"Wrote {path}; no large archives downloaded")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Download verified research datasets from official sources.")
    parser.add_argument("--dataset", choices=["ur", "ikar", "fallvision-inventory", "all"], default="ur")
    parser.add_argument("--falls", type=int, default=10)
    parser.add_argument("--non-falls", type=int, default=10)
    parser.add_argument("--seed", type=int, default=20261028)
    args = parser.parse_args()
    if not 1 <= args.falls <= 30 or not 1 <= args.non_falls <= 40:
        parser.error("UR sample counts are out of range")
    failures = []
    for name, action in (
        ("ikar", download_ikar),
        ("ur", lambda: download_ur(args.seed, args.falls, args.non_falls)),
        ("fallvision-inventory", inspect_fallvision),
    ):
        if args.dataset not in {name, "all"}:
            continue
        try:
            action()
        except Exception as error:
            failures.append({"dataset": name, "error": str(error)})
            print(f"ERROR {name}: {error}", file=sys.stderr)
    if failures:
        write_json(DATA_ROOT / "validation" / "reports" / "download_failures.json", {"created_at": utc_now(), "failures": failures})
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
