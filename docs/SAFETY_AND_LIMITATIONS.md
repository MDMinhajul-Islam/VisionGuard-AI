# Safety, privacy, and limitations

VisionGuard AI is an offline portfolio/research prototype for synthetic, staged, user-owned, or otherwise authorized recorded footage. It is not certified, safety-critical, or appropriate for public deployment.

## Prohibited scope

- no live CCTV, RTSP, webcam, or background surveillance integration;
- no facial recognition, face identification, biometric inference, or cross-video identity tracking;
- no protected/sensitive attribute inference;
- no criminality, negligence, guilt, dangerousness, or suspicious-person classification;
- no automated law-enforcement, employment, disciplinary, or emergency decisions.

CLIP similarities are ranking scores, not calibrated event probabilities. Its original model card explicitly treats deployed surveillance and facial recognition as out of scope. Object-detector confidence is likewise not proof of a safety condition.

## Human control

All machine-created events start `pending`. Only a person can select `confirmed by reviewer`; reviewer notes and timestamps remain stored. A positive candidate must be checked against the source clip, context, zone definition, occlusion, camera position, and applicable procedure. A missing event does not imply a safe scene.

Ground-truth annotations are stored independently from predictions. Reprocessing is blocked by default when reviewed model evidence exists. Zone re-analysis preserves reviewed candidates. Synthetic fixtures carry explicit database provenance and prominent UI labels.

## Error modes

Fall heuristics can confuse sitting, bending, crouching, intentional lying, abrupt camera motion, occlusion, and truncation. The explicit `unknown` state avoids forcing a conclusion when landmarks are weak but cannot eliminate errors. Exit obstruction uses box/polygon overlap and cannot reason about depth, navigable clearance, door function, or accessibility. COCO classes omit many industrial hazards. Synthetic fixtures test code paths, not the physical world.

Metrics from zero positive events are undefined. A no-alert synthetic interval must never be described as evidence of fall recall. Tiny development/calibration sets must not be reused as unbiased held-out performance claims.

## Privacy and handling

Obtain authorization, minimize collection, restrict access, define retention, and remove runtime artifacts when no longer required. Uploads and derived frames may contain personal information even though the software does not identify people. Never commit footage, embeddings, frames, exports, logs, or model weights. The local API has no authentication and must remain bound to loopback.

## Validation gate

Before any operational consideration, use a consented, representative, labeled dataset; define camera/site scope; perform event-level precision/recall and subgroup/environmental error analysis; calibrate thresholds; evaluate false negatives and alert fatigue; document incident-response procedures; complete legal/privacy/security review; and retain an accountable human decision maker.
