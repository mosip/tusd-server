# MOSIP Telemetry Ingestion Backend

This repository contains the complete, containerized backend architecture for ingesting telemetry data from the MOSIP Android Registration Client. It is designed as a decoupled, cloud-native service stack that is resilient, scalable, and requires no modification to the core `tusd-server` application.

This implementation is part of the work for issue mosip/android-registration-client#719.

## Architecture

The data pipeline follows a "Sidecar" pattern:

```text
[Flutter Client] --(TUS)--> [TUSD Server] --> [Shared Volume] --> [Vector Sidecar] --(TCP)--> [Apache Kafka]
```

1.  **TUSD Server**: The official `mosip/tusd-server` receives resumable, chunked file uploads from the client and saves the completed telemetry files to a local volume.
2.  **Vector Sidecar**: A lightweight, high-performance `timberio/vector` container runs alongside `tusd`. It watches the shared volume for new files.
3.  **Processing**: The instant a file is completed, Vector reads it, parses the content as JSON, and adds a processing timestamp.
4.  **Kafka Sink**: Vector forwards the structured JSON event directly to a specified Apache Kafka topic.

This design ensures true separation of concerns and guarantees data delivery even if the downstream message queue is temporarily unavailable.

## Prerequisites

- Docker
- Docker Compose

## How to Run

The entire service stack can be launched with a single command:

```bash
docker compose up -d
```

This will start the following containers:
- `mosip_tusd_server`
- `telemetry_vector_shipper`
- `local_kafka`
- `local_zookeeper`

## How to Test the Pipeline

We have included a Python test script to simulate a file upload and verify the end-to-end data flow.

1.  **Start a Kafka Consumer:**
    Open a terminal and run the following command to listen to the telemetry topic. The terminal will hang, waiting for messages.
    ```bash
    docker exec -it local_kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic registration-client-telemetry --from-beginning
    ```

2.  **Trigger an Upload:**
    Open a second terminal and run the Python test script.
    ```bash
    python Test_case/conn_test.py
    ```

3.  **Verify the Result:**
    Switch back to your first terminal. The JSON payload from the Python script will appear on the screen, confirming it has been successfully processed by TUSD, collected by Vector, and published to Kafka.