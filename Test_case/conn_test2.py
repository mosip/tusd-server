"""
send_test_telemetry.py

Stands in for the Flutter app: performs a real tus.io resumable-upload
handshake against mosip-tusd, uploading each sample event as its OWN file
(matches the architecture seen in /srv/tusd-data/data — one tus upload
per event, filename = the random hex ID tusd assigns).

Requires: pip install requests
"""

import base64
import json
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests

# Adjust if mosip-tusd uses a different base path than the tusd default.
# Quick sanity check before running this script:
#   curl -i -X OPTIONS http://localhost:8080/files/
TUSD_BASE_URL = "http://localhost:8080/files/"


def upload_event_to_tusd(event: dict, base_url: str = TUSD_BASE_URL) -> str:
    """Create + upload a single tus file containing exactly one JSON event."""
    # IMPORTANT: trailing newline required. tusd uploads are one-shot,
    # immutable files — they're never appended to afterward. Vector's file
    # source needs to see a *complete line* (terminated by \n) before it
    # will even start tracking/fingerprinting a file; without this, the
    # file sits forever as "too small to fingerprint" and is never read.
    body = json.dumps(event, separators=(",", ":")).encode("utf-8") + b"\n"

    metadata = {
        "filename": f"{event['name'].lower()}.json",
        "filetype": "application/json",
    }
    upload_metadata = ",".join(
        f"{k} {base64.b64encode(v.encode()).decode()}" for k, v in metadata.items()
    )

    # 1. CREATE — tell tusd the total size up front
    create_resp = requests.post(
        base_url,
        headers={
            "Tus-Resumable": "1.0.0",
            "Upload-Length": str(len(body)),
            "Upload-Metadata": upload_metadata,
            "Content-Length": "0",
        },
        timeout=10,
    )
    if not create_resp.ok:
        print(f"--- tusd CREATE failed ({create_resp.status_code}) ---")
        print(f"Response headers: {dict(create_resp.headers)}")
        print(f"Response body:    {create_resp.text!r}")
    create_resp.raise_for_status()
    location = create_resp.headers.get("Location")
    if not location:
        raise RuntimeError(f"No Location header returned: {dict(create_resp.headers)}")
    if location.startswith("/"):
        location = urljoin(base_url, location)

    # 2. PATCH — send the bytes (single chunk, files are tiny)
    patch_resp = requests.patch(
        location,
        data=body,
        headers={
            "Tus-Resumable": "1.0.0",
            "Upload-Offset": "0",
            "Content-Type": "application/offset+octet-stream",
        },
        timeout=10,
    )
    if not patch_resp.ok:
        print(f"--- tusd PATCH failed ({patch_resp.status_code}) ---")
        print(f"Response headers: {dict(patch_resp.headers)}")
        print(f"Response body:    {patch_resp.text!r}")
    patch_resp.raise_for_status()

    print(f"[OK]   {event['name']:<22} -> {location}")
    return location


DEVICE_METADATA = {
    "os": "Android",
    "os_version": "13",
    "device_model": "22031116AI",
    "app_version": "1.0",
    "app_build": "1",
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


SAMPLE_EVENTS = [
    {"name": "APP_STARTUP", "timestamp": now(),
     "data": {"duration_ms": 435, "status": "success", "environment": "development",
              "metadata": DEVICE_METADATA}},
    {"name": "screen_view", "timestamp": now(),
     "data": {"screen_name": "/"}},
    {"name": "LOGIN_ATTEMPT_STARTED", "timestamp": now(),
     "data": {"username_provided": True, "network_status": "offline",
              "metadata": DEVICE_METADATA}},
    {"name": "LOGIN_FAILURE", "timestamp": now(),
     "data": {"error_code": "REG_CRED_EXPIRED", "reason": "Invalid Credentials or Unauthorized",
              "is_online": False, "metadata": DEVICE_METADATA}},
]


if __name__ == "__main__":
    print(f"Uploading {len(SAMPLE_EVENTS)} test events to {TUSD_BASE_URL} ...\n")
    for evt in SAMPLE_EVENTS:
        try:
            upload_event_to_tusd(evt)
        except Exception as exc:
            print(f"[FAIL] {evt['name']}: {exc}")
    print("\nDone. Now check the container, Vector logs, and Kafka (see commands).")