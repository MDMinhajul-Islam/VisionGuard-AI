# Secure Storage

Uploads receive UUID storage names; original names are display metadata. Extensions, upload size, FFprobe decoding metadata, and bounded streaming writes are validated. Frame, thumbnail, source-video, and export responses use stored identifiers plus `safe_within` containment against the expected root.

Authorization runs before filesystem resolution. Tenant headers cannot select an existing object’s owner. Export paths are server-generated and source footage is never overwritten.

Research/commercial separation uses `Organization.workspace_type`. CLIP/search and research dataset registration work only in research workspaces. Media, datasets, checkpoints, databases, and exports remain Git-ignored.

Future requirements include per-tenant object-storage prefixes, encryption keys, short-lived signed downloads, malware/media-parser isolation, retention/deletion/legal-hold workflows, quotas, and crash-safe temporary cleanup.
