# MOSIP Telemetry Analytics Backend – Local Development

This directory contains the **local development environment** for the MOSIP Telemetry Analytics Backend. It provides a complete, containerized setup for developing, testing, and validating the end-to-end telemetry pipeline locally.

The local development environment simulates the production telemetry flow, enabling developers to verify telemetry ingestion, event streaming, indexing, and visualization using Docker Compose.

## Architecture

```text
Android Registration Client (TUS Client)
                │
                ▼
          MOSIP TUSD Server
                │
                ▼
          Vector Shipper
                │
                ▼
           Apache Kafka
                │
                ▼
          Kafka Connect
                │
                ▼
          Elasticsearch
                │
                ▼
              Kibana
```

## Components

* **Android Registration Client** – Generates telemetry events.
* **MOSIP TUSD Server** – Receives telemetry uploads using the TUS resumable upload protocol.
* **Vector** – Watches uploaded telemetry files, parses them, and publishes events to Kafka.
* **Apache Kafka** – Streams telemetry events.
* **Kafka Connect** – Transfers telemetry data from Kafka to Elasticsearch.
* **Elasticsearch** – Stores and indexes telemetry events.
* **Kibana** – Visualizes telemetry data through dashboards and search.

## Prerequisites

Before starting, ensure the following are installed:

* Git
* Docker Desktop (or Docker Engine + Docker Compose)
* Docker Compose v2

## Getting Started

### 1. Clone the Repository

```bash
git clone <repository-url>
cd <repository-folder>
```

### 2. Start the Local Development Environment

```bash
docker compose up -d
```

This command starts all required services, including:

* MOSIP TUSD Server
* Vector
* Apache Kafka
* Kafka Connect
* Elasticsearch
* Kibana

### 3. Configure TUSD Data Directory Permissions

After all containers are running, execute:

```bash
docker exec -u 0 mosip_tusd_server chmod -R 777 /srv/tusd-data/data
```

This grants the required permissions so that Vector can access uploaded telemetry files.

### 4. Verify the Data Directory

Verify that the telemetry data directory is accessible:

```bash
docker exec mosip_tusd_server ls -la /srv/tusd-data/data
```

The directory should be accessible and writable.

### 5. Verify Running Containers

```bash
docker ps
```

Ensure the following containers are running:

* mosip_tusd_server
* vector
* kafka
* kafka-connect
* elasticsearch
* kibana

## Data Flow

1. The Android Registration Client generates telemetry events.
2. Telemetry files are uploaded to the MOSIP TUSD Server using the TUS protocol.
3. Vector monitors uploaded files and converts them into structured telemetry events.
4. Vector publishes telemetry events to Apache Kafka.
5. Kafka Connect consumes Kafka topics and indexes telemetry data into Elasticsearch.
6. Elasticsearch stores and indexes telemetry records.
7. Kibana enables searching, monitoring, and visualization of telemetry data.

## Stopping the Environment

```bash
docker compose down
```

To remove all associated volumes:

```bash
docker compose down -v
```
