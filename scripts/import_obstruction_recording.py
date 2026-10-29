from __future__ import annotations

import argparse
import time
from pathlib import Path

import httpx


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import an authorized doorway recording and analyze a normalized keep-clear rectangle."
    )
    parser.add_argument("video", type=Path)
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument(
        "--zone", nargs=4, type=float, metavar=("X", "Y", "WIDTH", "HEIGHT"), required=True
    )
    parser.add_argument("--min-duration", type=float, default=2.0)
    args = parser.parse_args()
    if not args.video.is_file():
        parser.error("video does not exist")
    x, y, width, height = args.zone
    if width <= 0 or height <= 0 or any(
        value < 0 or value > 1 for value in (x, y, x + width, y + height)
    ):
        parser.error("zone must fit normalized [0,1] coordinates")
    with httpx.Client(base_url=args.api, timeout=300) as client:
        with args.video.open("rb") as handle:
            response = client.post(
                "/api/videos/upload", files={"file": (args.video.name, handle, "video/mp4")}
            )
        response.raise_for_status()
        video_id = response.json()["id"]
        job = client.post(
            f"/api/videos/{video_id}/process",
            json={"analysis_fps": 4, "pose_fps": 5, "profile_name": "authorized-obstruction-validation"},
        )
        job.raise_for_status()
        job_id = job.json()["id"]
        while True:
            status = client.get(f"/api/jobs/{job_id}")
            status.raise_for_status()
            payload = status.json()
            print(f"{payload['stage']}: {payload['progress']:.0f}%")
            if payload["status"] in {"completed", "failed", "cancelled"}:
                break
            time.sleep(1)
        if payload["status"] != "completed":
            raise RuntimeError(payload.get("error") or payload["status"])
        polygon = [[x, y], [x + width, y], [x + width, y + height], [x, y + height]]
        zone = client.post(
            f"/api/videos/{video_id}/zones",
            json={"name": "Staged keep-clear zone", "zone_type": "emergency_exit", "polygon": polygon},
        )
        zone.raise_for_status()
        result = client.post(
            f"/api/videos/{video_id}/zones/analyze",
            json={"min_duration": args.min_duration, "profile_name": "authorized-obstruction-validation"},
        )
        result.raise_for_status()
        print({"video_id": video_id, "zone_id": zone.json()["id"], "analysis": result.json()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
