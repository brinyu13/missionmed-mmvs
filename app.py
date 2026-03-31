from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

APP_VERSION = "1.0.0"
APP_ROOT = Path(__file__).resolve().parent
DATA_ROOT = Path(os.getenv("MMVS_DATA_ROOT", str(APP_ROOT))).expanduser()
REGISTRY_PATH = DATA_ROOT / "video_registry.json"
PATH_FIELDS = ("video_path", "source_video_path", "transcript_path", "cloud_video_path")

app = FastAPI(
    title="MissionMed Video System Registry API",
    description="Read-only MMVS service exposing the canonical video registry over HTTP.",
    version=APP_VERSION,
)


def is_http_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def load_registry_entries() -> list[dict[str, Any]]:
    if not REGISTRY_PATH.exists():
        raise HTTPException(
            status_code=503,
            detail=f"Canonical registry is missing at {REGISTRY_PATH.as_posix()}",
        )

    try:
        payload = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"Registry JSON is invalid: {exc}") from exc

    if not isinstance(payload, list):
        raise HTTPException(status_code=500, detail="Registry root must be a JSON array.")

    if not all(isinstance(item, dict) for item in payload):
        raise HTTPException(status_code=500, detail="Registry entries must all be JSON objects.")

    return payload


def inspect_registry(entries: list[dict[str, Any]]) -> dict[str, Any]:
    missing_cloud_video_path: list[str] = []
    invalid_cloud_video_path: list[str] = []
    absolute_local_paths: list[dict[str, str]] = []

    for entry in entries:
        asset_id = str(entry.get("id") or "<missing-id>")
        cloud_video_path = str(entry.get("cloud_video_path") or "").strip()

        if not cloud_video_path:
            missing_cloud_video_path.append(asset_id)
        elif not is_http_url(cloud_video_path):
            invalid_cloud_video_path.append(asset_id)

        for field in PATH_FIELDS:
            value = entry.get(field)
            if not isinstance(value, str):
                continue

            path_value = value.strip()
            if not path_value:
                continue

            if field == "cloud_video_path":
                if path_value.startswith("/") and not is_http_url(path_value):
                    absolute_local_paths.append({"id": asset_id, "field": field, "value": path_value})
                continue

            if path_value.startswith("/"):
                absolute_local_paths.append({"id": asset_id, "field": field, "value": path_value})

    registry_sha256 = hashlib.sha256(REGISTRY_PATH.read_bytes()).hexdigest()
    healthy = not missing_cloud_video_path and not invalid_cloud_video_path and not absolute_local_paths

    return {
        "healthy": healthy,
        "registry_entries": len(entries),
        "registry_sha256": registry_sha256,
        "missing_cloud_video_path_count": len(missing_cloud_video_path),
        "invalid_cloud_video_path_count": len(invalid_cloud_video_path),
        "absolute_local_path_count": len(absolute_local_paths),
        "missing_cloud_video_path_samples": missing_cloud_video_path[:10],
        "invalid_cloud_video_path_samples": invalid_cloud_video_path[:10],
        "absolute_local_path_samples": absolute_local_paths[:10],
    }


@app.get("/")
def root() -> dict[str, Any]:
    return {
        "service": "MissionMed Video System Registry API",
        "mode": "canonical_read_only",
        "version": APP_VERSION,
        "endpoints": ["/health", "/videos"],
    }


@app.get("/health")
def health() -> JSONResponse:
    entries = load_registry_entries()
    report = inspect_registry(entries)
    payload = {
        "status": "ok" if report["healthy"] else "error",
        "mode": "canonical_read_only",
        "version": APP_VERSION,
        "runtime_root": DATA_ROOT.as_posix(),
        "registry_path": REGISTRY_PATH.as_posix(),
        **report,
    }
    return JSONResponse(status_code=200 if report["healthy"] else 503, content=payload)


@app.get("/videos")
def videos() -> list[dict[str, Any]]:
    return load_registry_entries()
