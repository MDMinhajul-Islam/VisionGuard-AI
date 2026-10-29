# Access Control

| Capability | Organization admin | Site admin | Safety reviewer | Read-only auditor |
|---|---:|---:|---:|---:|
| Read authorized media/evidence | yes | yes | yes | yes |
| Review and export incidents | yes | yes | yes | no |
| Upload/process/configure zones | yes | yes | no | no |
| Manage organization membership | platform administration endpoint | no | no | no |

The legacy global `admin`/`reviewer` field remains as a platform function gate during migration. It does not grant media access: organization membership and site access are also required. Sensitive collections are filtered at query time. Nested object routes resolve job, frame, event, export, annotation, or dataset asset to its video before the endpoint runs.

Negative tests cover cross-organization metadata, media, frames, evidence, jobs, reviews, exports, semantic search, and research dataset results.
