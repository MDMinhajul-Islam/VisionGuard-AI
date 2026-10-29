# Minimal MLOps Foundation

Sprint 3 adds a validated JSON `ExperimentRecord`, atomic writes, logical `research`, `commercial_candidate` and `released` registries, and a human-approval gate for `released`. Benchmark registration records dataset/source/license, manifest version, architecture, checkpoint identity/SHA-256, model license, configuration, protocol, hardware, runtime versions, results and Git SHA.

MLflow and DVC were evaluated conceptually but not added. For one local workstation, they would add services/dependencies without improving the immediate release gate. The typed records are deliberately portable: migrate them to MLflow when concurrent experiments and artifact servers are required, and adopt DVC or an object-store manifest layer when legally usable commercial datasets become versioned team assets.

Research records may use non-commercial datasets or incompatible model licenses. Promotion is never automatic. A commercial candidate additionally requires license review, an approved commercial dataset, an annotated accuracy protocol and target-hardware performance. Release requires an explicit named approver plus every gate in `RELEASE_GATES.md`.
