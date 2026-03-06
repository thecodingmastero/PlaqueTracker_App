# Ingest Service

Prototype ingestion service for PlaqueTracker sensor telemetry.

Endpoints

- `POST /v1/ingest` — accepts JSON payloads from devices or gateways.

Behavior

- Applies exponential moving average smoothing to incoming pH values per device.
- Performs a basic CRC-like check for demo purposes.

Run locally

```bash
pip install -r requirements.txt
python app.py
```
