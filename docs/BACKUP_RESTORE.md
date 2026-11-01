# Backup and Restore

`backup_postgres.ps1` creates a PostgreSQL custom-format archive under ignored `runtime/backups`, validates it with `pg_restore -l`, and writes a SHA-256 manifest. `restore_postgres.ps1` refuses an existing target and restores only into a newly named isolated database.

The 2026-10-31 drill created a 2,541,876-byte archive in 1.64 seconds with SHA-256 `54128aafd9d18564d1b075a729676ae68a3d2ee06e084ede02e7735a659a14ee`. Restore to `visionguard_restore_20261031` completed in 4.54 seconds. Verification found 31 videos, 34 jobs, 8 events, 18 annotations, 30 datasets, 29 audits, 16 FORCE-RLS tables, and zero orphan jobs.

```powershell
.\scripts\backup_postgres.ps1
.\scripts\restore_postgres.ps1 -Archive runtime\backups\visionguard-visionguard-YYYYMMDD-HHMMSS.dump -TargetDatabase visionguard_restore_drill_new
python scripts\create_media_manifest.py --output runtime\backups\media-manifest.json
```

Logical dumps are not PITR, do not contain server configuration, and do not include media. The verified media manifest referenced 462 files; all existed. Full recovery also requires protected media, configuration/secrets, keys, and recurring restore drills.
