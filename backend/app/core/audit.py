from __future__ import annotations

import json

from fastapi import Request

from app.database.models import AuditEvent, User


def record_audit(
    db,
    request: Request,
    action: str,
    outcome: str,
    *,
    actor: User | None = None,
    organization_id: str | None = None,
    object_type: str | None = None,
    object_id: str | None = None,
    metadata: dict | None = None,
) -> AuditEvent:
    event = AuditEvent(
        actor_id=actor.id if actor else None,
        organization_id=organization_id,
        action=action,
        object_type=object_type,
        object_id=object_id,
        outcome=outcome,
        request_id=getattr(request.state, "request_id", "unknown"),
        metadata_json=json.dumps(metadata or {}, sort_keys=True),
    )
    db.add(event)
    return event
