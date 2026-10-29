import io
import tarfile
import zipfile
from pathlib import Path

import pytest

from app.datasets.io import file_hash, resumable_download, safe_extract_tar, safe_extract_zip, verify_hash
from app.datasets.manifest import PreparedManifest


def test_hash_verification(tmp_path: Path):
    fixture = tmp_path / "fixture.bin"
    fixture.write_bytes(b"visionguard")
    assert file_hash(fixture) == "0490840f53ff7189a621fe1876ddf817076c8e92cbac76a333ab433e73bf18aa"
    assert verify_hash(fixture, file_hash(fixture))
    assert not verify_hash(fixture, "0" * 64)


def test_verified_download_is_reused_without_network_access(tmp_path: Path):
    fixture = tmp_path / "fixture.bin"
    fixture.write_bytes(b"already downloaded")
    result = resumable_download(
        "https://invalid.example/should-not-be-requested",
        fixture,
        expected_hash=file_hash(fixture),
        expected_size=fixture.stat().st_size,
    )
    assert result == {"status": "already_verified", "bytes": fixture.stat().st_size}


def test_safe_zip_rejects_path_traversal(tmp_path: Path):
    archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("../escape.txt", "unsafe")
    with pytest.raises(ValueError, match="escapes"):
        safe_extract_zip(archive, tmp_path / "out")


def test_safe_tar_rejects_links(tmp_path: Path):
    archive = tmp_path / "unsafe.tar.gz"
    with tarfile.open(archive, "w:gz") as handle:
        member = tarfile.TarInfo("shortcut")
        member.type = tarfile.SYMTYPE
        member.linkname = "outside"
        handle.addfile(member)
    with pytest.raises(ValueError, match="unsupported"):
        safe_extract_tar(archive, tmp_path / "out")


def test_prepared_manifest_rejects_duplicate_records():
    record = {
        "record_id": "ur-fall-01", "source_dataset": "UR Fall Detection",
        "original_recording_id": "fall-01", "prepared_video_path": "data/fall-01.mp4",
        "original_label": "fall sequence", "evaluation_label": "fall",
        "duration_seconds": 2, "width": 640, "height": 480, "fps": 30, "frame_count": 60,
        "conversion_status": "converted", "annotation_status": "video_level_only",
        "source_url": "https://example.invalid", "source_license": "research",
        "source_archive_sha256": "a", "prepared_sha256": "b", "timing_source": "source CSV",
    }
    with pytest.raises(ValueError, match="unique"):
        PreparedManifest(dataset_name="UR", seed=1, created_at="now", records=[record, record])
