# Real research datasets

VisionGuard stores every archive, extracted frame, prepared video, diagnostic image, and local manifest under ignored `data/external/`. Dataset media must never be committed or redistributed from this repository.

## Sources and licensing

| Dataset | Official source | License | Local acquisition status |
|---|---|---|---|
| IKAR Fall Detection, V1 | AGH University of Krakow, DOI `10.58032/AGH/A1NZPE` | CC BY 4.0 | Metadata, version, archive name, size, and published MD5 verified. The official `agh.rodbuk.pl` host repeatedly timed out from this machine, so no archive was accepted. |
| UR Fall Detection | University of Rzeszów | CC BY-NC-SA 4.0; non-commercial research use | 20 RGB ZIPs, 20 synchronization CSVs, and the two official posture tables downloaded from the university host. |
| FallVision V2 | Harvard Dataverse, DOI `10.7910/DVN/75QPKK` | CC0 | Official inventory inspected. Multi-gigabyte RAR bundles were intentionally not downloaded for this initial subset. |

IKAR reports 278 controlled falls and publishes archive MD5 `2667661c258610c0c0aa4bc58a7fc7c2`. The downloader refuses to extract an archive until that MD5 matches. UR contains 30 fall and 40 ADL sequences; this project downloads RGB only plus the timing/label metadata needed for interpretation. UR's license restricts this use to the local non-commercial research workflow.

## Reproducible subset

Seed `20261028` selects fall IDs `02, 07, 18, 19, 20, 22, 23, 24, 25, 26` and ADL IDs `01, 03, 10, 14, 15, 17, 19, 30, 32, 35`. The selection is recorded in `validation/manifests/ur-balanced-20-selection.json`.

Downloads use `.part` files, retries, HTTP Range when supported, expected sizes, SHA-256 receipts, and ZIP CRC verification. Archive extraction rejects traversal and link/device members. Existing files are skipped only after verification.

UR RGB frames are converted without changing originals. The converter uses the official per-frame millisecond synchronization CSV to write a variable-frame-rate concat timeline, then FFmpeg encodes H.264/yuv420p MP4 with the original aspect ratio. It does not invent an FPS when synchronization data are missing. Every derivative is checked with FFprobe for codec, duration, dimensions, frame count, and frame rate.

## Commands

Run from the project root in PowerShell:

```powershell
.\.venv\Scripts\python .\scripts\download_research_datasets.py --dataset ur
.\.venv\Scripts\python .\scripts\prepare_research_videos.py --dataset ur
.\.venv\Scripts\python .\scripts\import_validation_videos.py .\data\external\validation\manifests\ur-balanced-20.json --api http://127.0.0.1:8000 --process
.\.venv\Scripts\python .\scripts\evaluate_real_falls.py --api http://127.0.0.1:8000
```

Use `--dataset ikar` to retry the official IKAR endpoint when it is reachable, and `--dataset fallvision-inventory` to refresh only the Harvard inventory. Source provenance is stored in `DatasetAsset`; ground truth remains separate from predictions and reviews.

## Annotation boundary

All 20 records have source video-level labels. For the ten fall sequences, the source's cam0 depth posture label `0` (temporary/falling posture) is mapped to RGB time through official synchronization metadata. These are useful source-aligned transition intervals but are not independent human RGB event-onset annotations. ADL posture values are never promoted to fall annotations. Video-level and temporal metrics are reported separately.
