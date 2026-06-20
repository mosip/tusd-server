"""
test_pipeline_full.py

End-to-end pipeline health check:
  1. Uploads a batch of varied telemetry events to tusd (real tus handshake).
  2. Waits briefly for Vector to pick them up.
  3. Shells out to `docker exec ... kafka-console-consumer` and checks that
     every event you sent actually shows up in the Kafka topic.
  4. Prints a clear PASS/FAIL summary — exits non-zero if anything's missing.

This batch is intentionally more varied than the first test (nested arrays,
unicode text, larger/edge-case fields) to exercise parse_json/remap more than
four flat objects did.

Requires: pip install requests
Requires: Docker CLI on PATH, and the docker-compose stack already running.
"""

import base64
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests

TUSD_BASE_URL = "http://localhost:8080/files/"
KAFKA_CONTAINER = "local_kafka"
KAFKA_TOPIC = "registration-client-telemetry"
SETTLE_SECONDS = 4  # time to let Vector notice + ship new files before we check Kafka


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


DEVICE_METADATA = {
    "os": "Android",
    "os_version": "13",
    "device_model": "22031116AI",
    "app_version": "1.0",
    "app_build": "1",
}

TEST_EVENTS = [
    {"name": "USER_LOGOUT", "timestamp": now(),
     "data": {"reason": "manual", "session_duration_ms": 184302}},

    {"name": "BIOMETRIC_CAPTURE_COMPLETED", "timestamp": now(),
     "data": {"modality": "fingerprint", "quality_score": 78.5, "attempts": 2,
              "fingers_captured": ["LeftIndex", "LeftMiddle"],
              "metadata": DEVICE_METADATA}},

    {"name": "REGISTRATION_SUBMITTED", "timestamp": now(),
     "data": {"registration_id": "10011100110000320250101103015", "center_id": "10011",
              "operator_name": "ರಮೇಶ್ ಕುಮಾರ್",  # unicode, to make sure encoding survives the pipeline
              "is_update": False, "documents_count": 3, "metadata": DEVICE_METADATA}},

    {"name": "SYNC_FAILED", "timestamp": now(),
     "data": {"error_code": "NETWORK_TIMEOUT", "retry_count": 3, "is_online": False,
              "queued_records": 12,
              "stack_trace_snippet": "java.net.SocketTimeoutException: timeout",
              "metadata": DEVICE_METADATA}},

    {"name": "screen_view", "timestamp": now(),
     "data": {"screen_name": "/registration/preview", "duration_ms": 9120}},
]


def upload_event_to_tusd(event: dict, base_url: str = TUSD_BASE_URL) -> str:
    body = json.dumps(event, separators=(",", ":")).encode("utf-8") + b"\n"

    metadata = {"filename": f"{event['name'].lower()}.json", "filetype": "application/json"}
    upload_metadata = ",".join(
        f"{k} {base64.b64encode(v.encode()).decode()}" for k, v in metadata.items()
    )

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
        print(f"--- tusd CREATE failed ({create_resp.status_code}) ---\n{create_resp.text!r}")
    create_resp.raise_for_status()

    location = create_resp.headers.get("Location")
    if location.startswith("/"):
        location = urljoin(base_url, location)

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
        print(f"--- tusd PATCH failed ({patch_resp.status_code}) ---\n{patch_resp.text!r}")
    patch_resp.raise_for_status()

    print(f"[uploaded] {event['name']:<28} -> {location}")
    return location


def fetch_kafka_messages() -> str:
    """Drain the topic from the beginning via the kafka-console-consumer CLI."""
    result = subprocess.run(
        ["docker", "exec", KAFKA_CONTAINER, "kafka-console-consumer",
         "--bootstrap-server", "localhost:9092",
         "--topic", KAFKA_TOPIC,
         "--from-beginning",
         "--timeout-ms", "8000"],
        capture_output=True,  # bytes, not text — avoids Windows cp1252 decode crashes on UTF-8 (e.g. unicode fields)
    )
    return result.stdout.decode("utf-8", errors="replace")


if __name__ == "__main__":
    print(f"Uploading {len(TEST_EVENTS)} varied test events...\n")
    for evt in TEST_EVENTS:
        try:
            upload_event_to_tusd(evt)
        except Exception as exc:
            print(f"[FAIL] {evt['name']}: {exc}")

    print(f"\nWaiting {SETTLE_SECONDS}s for Vector to process, then checking Kafka...\n")
    time.sleep(SETTLE_SECONDS)
    kafka_output = fetch_kafka_messages()

    print("--- Verifying each event reached Kafka ---")
    all_ok = True
    for evt in TEST_EVENTS:
        marker = f'"name":"{evt["name"]}"'
        found = marker in kafka_output
        print(f"  [{'PASS' if found else 'FAIL'}] {evt['name']}")
        all_ok = all_ok and found

    print()
    if all_ok:
        print("✅ All events confirmed end-to-end (tusd -> Vector -> Kafka).")
    else:
        print("❌ Some events did not reach Kafka. Re-run with:")
        print(f'   docker logs --tail 50 telemetry_vector_shipper')
        print("   to see why those specific files were skipped or failed to parse.")
        sys.exit(1)