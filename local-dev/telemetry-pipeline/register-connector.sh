#!/usr/bin/env bash
# Registers (or updates) the Elasticsearch sink connector with the local
# Kafka Connect REST API. Run this AFTER `docker compose up -d` and after
# kafka-connect reports healthy (it can take ~30-60s the first time while
# it installs the connector plugin).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONNECT_URL="http://localhost:8083"
CONNECTOR_NAME="es-sink-registration-client-telemetry"

echo "Waiting for Kafka Connect REST API at ${CONNECT_URL} ..."
until curl -sf "${CONNECT_URL}/connectors" > /dev/null 2>&1; do
  printf "."
  sleep 3
done
echo -e "\nKafka Connect is up."

echo "Registering connector '${CONNECTOR_NAME}'..."
# If it already exists, delete it first so this script is safely re-runnable.
curl -s -X DELETE "${CONNECT_URL}/connectors/${CONNECTOR_NAME}" > /dev/null 2>&1 || true

curl -s -X POST \
  -H "Content-Type: application/json" \
  --data @"${SCRIPT_DIR}/sink-connector.json" \
  "${CONNECT_URL}/connectors" | python3 -m json.tool

echo -e "\nConnector status:"
curl -s "${CONNECT_URL}/connectors/${CONNECTOR_NAME}/status" | python3 -m json.tool