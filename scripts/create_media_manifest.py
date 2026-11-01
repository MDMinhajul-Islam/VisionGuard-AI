from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path

from sqlalchemy import create_engine, text


QUERIES = {
    "video": "SELECT id, path FROM videos",
    "thumbnail": "SELECT id, thumbnail_path AS path FROM videos WHERE thumbnail_path IS NOT NULL",
    "frame": "SELECT id, path FROM video_frames",
    "embedding": "SELECT id, path FROM embedding_caches",
    "export": "SELECT id, path FROM exported_clips",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a database-to-media recovery manifest without copying media.")
    parser.add_argument("--database-url", default=os.environ.get("VISIONGUARD_MIGRATION_DATABASE_URL"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.database_url:
        parser.error("--database-url or VISIONGUARD_MIGRATION_DATABASE_URL is required")
    records = []
    engine = create_engine(args.database_url)
    with engine.connect() as connection:
        for kind, query in QUERIES.items():
            for identifier, raw_path in connection.execute(text(query)):
                path = Path(raw_path)
                records.append({
                    "kind": kind, "record_id": identifier, "path": str(path),
                    "exists": path.is_file(), "size_bytes": path.stat().st_size if path.is_file() else None,
                })
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "records": records, "record_count": len(records),
        "existing_files": sum(item["exists"] for item in records),
        "missing_files": sum(not item["exists"] for item in records),
        "warning": "This manifest references media; database backup does not contain video, evidence, embeddings, or exports.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in payload.items() if key != "records"}, indent=2))


if __name__ == "__main__":
    main()
