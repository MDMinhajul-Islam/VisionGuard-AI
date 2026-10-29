from __future__ import annotations

import os

import httpx


def authenticated_client(api: str, timeout: float) -> httpx.Client:
    token = os.environ.get("VISIONGUARD_API_TOKEN")
    headers = {"Authorization": f"Bearer {token}"} if token else None
    client = httpx.Client(base_url=api, timeout=timeout, headers=headers)
    if token:
        return client
    email = os.environ.get("VISIONGUARD_API_EMAIL")
    password = os.environ.get("VISIONGUARD_API_PASSWORD")
    if not email or not password:
        client.close()
        raise RuntimeError("Set VISIONGUARD_API_TOKEN or VISIONGUARD_API_EMAIL and VISIONGUARD_API_PASSWORD")
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    response.raise_for_status()
    return client
