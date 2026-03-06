# PlaqueTracker Sensor Firmware API & BLE Protocol

This document defines a minimal BLE/GATT and WiFi ingestion protocol for PlaqueTracker embedded sensors (ESP32/XIAO).

BLE GATT profile (recommended)

- Service: PlaqueTracker Service
  - UUID: 0000PT01-0000-1000-8000-00805f9b34fb
  - Characteristics:
    - Measurement Characteristic (notify)
      - UUID: 0000PT02-0000-1000-8000-00805f9b34fb
      - Properties: Notify
      - Payload (JSON UTF-8): {
          "device_id": "<uuid>",
          "ts": "2026-02-25T12:34:56Z",
          "pH": 6.54,
          "temperature_c": 36.2,
          "battery": 92,
          "seq": 123,
          "crc": "abcd1234"
        }

    - Control Characteristic (write)
      - UUID: 0000PT03-0000-1000-8000-00805f9b34fb
      - Properties: Write, WriteWithoutResponse
      - Accepts JSON commands: calibration, ping, firmware_update_url

WiFi / HTTP ingestion (optional)

- Endpoint: POST /v1/ingest
- Auth: device API key in header `X-Device-Key` (rotateable)
- Body (JSON): same as BLE payload, optionally base64-encoded binary packet in `raw_packet` field.

Packet verification and reliability

- Include monotonic sequence `seq` and CRC or HMAC for tamper detection.
- Server should ACK via BLE control or HTTP 200 with `ack_seq` to confirm.

Firmware & calibration

- Devices should support remote calibration via control write with payload `{ "cmd": "calibrate", "ref_pH": 7.0 }`.
- Calibration state should be reported as `calibration_state` JSON in device metadata uploads.

Security

- All server endpoints require TLS. Device keys stored hashed on server. Use short-lived keys for provisioning.

Battery and telemetry

- Devices should periodically send `battery` and `firmware_version` fields and support `low_battery` advisory notifications.

Notes

- This spec is intentionally minimal. Extend with OTA update flow, pairing via mobile app, and E2E encryption if required by deployment.
