# Web Dashboard (Prototype)

Simple Flask dashboard to preview `outputs/scan_result.json`, open the generated PDF report, and POST a test telemetry payload to the ingest endpoint.

Run locally (activate your `.venv`):

```powershell
pip install -r services/web/requirements.txt
python services/web/app.py
```

Open: http://localhost:8000

## Arduino sensor bridge (UNO R4 + TCS3200)

If your Arduino sketch prints lines like:

`t=... R=...Hz G=...Hz B=...Hz OUTstate=... => Low pH|Neutral pH|High pH|pH unclear`

you can stream those readings into PlaqueTracker with:

```powershell
pip install pyserial
python tools/arduino_serial_bridge.py --port COM5 --baud 115200 --web-url http://localhost:8000 --device-id uno-r4 --on-change-only
```

Notes:
- Replace `COM5` with your Arduino serial port.
- The bridge maps labels to pH for ingest:
	- `Low pH` -> `5.4`
	- `Neutral pH` -> `7.0`
	- `High pH` -> `7.6`
- By default, `pH unclear` is skipped. Add `--send-unclear` to send a neutral fallback.

## Arduino UNO R4 WiFi (wireless direct ingest)

You can send readings directly from UNO R4 WiFi to the web app over Wi-Fi (no USB serial bridge).

1. Use sketch: `tools/uno_r4_wifi_tcs3200_http.ino`
2. In the sketch, set:
	- `WIFI_SSID`, `WIFI_PASS`
	- `SERVER_HOST` = your computer's LAN IP (e.g., `192.168.1.100`)
	- `SERVER_PORT` = `8000`
3. Start web app so it listens on LAN:
	- `python services/web/app.py` (already runs with host `0.0.0.0`)
4. Optional auth:
	- Set env var `DEVICE_INGEST_KEY` on the web app
	- Put matching `DEVICE_KEY` in the sketch

Endpoint used by the sketch:
- `POST /api/device-ingest` JSON
