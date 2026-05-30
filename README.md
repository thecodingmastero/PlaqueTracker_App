# PlaqueTracker — Prototype Monorepo

This repository contains prototype components for the PlaqueTracker oral health platform: device ingestion, hydrogel CV, analytics, reporting, and rewards.

Quickstart (run ingest service locally):

```powershell
docker-compose up --build
# then POST sample JSON to http://localhost:8080/v1/ingest
```

Hydrogel CV (train and run demo):

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r hydrogel_cv/requirements.txt
python hydrogel_cv/model_train.py --out hydrogel_cv/model.pkl
python hydrogel_cv/scan.py --image path/to/scan.jpg --model hydrogel_cv/model.pkl
```

Analytics: see `services/analytics` for examples of feature extraction, model training, and plaque risk scoring.

Auth & Security: prototype auth service in `services/auth` (JWT), and security notes in `security/README.md`.

## Local Web App + USB Sensor Testing

Use this flow for the kid-friendly Scans page and the XIAO ESP32-C3 + TCS3200 color sensor over USB-C. The ESP32 does **not** talk directly to the browser over USB. A Python bridge reads USB Serial and sends the readings to the Flask app.

More detail is also in `services/web/README.md`.

### 1. Check the wiring

Expected TCS3200 wiring for the Seeed XIAO ESP32-C3:

| TCS3200 pin | XIAO ESP32-C3 pin |
|---|---|
| `S0` | `D0 / GPIO2` |
| `S1` | `D1 / GPIO3` |
| `S2` | `D2 / GPIO4` |
| `S3` | `D3 / GPIO5` |
| `OUT` | `D4 / GPIO6` |
| `LED` | `D5 / GPIO7` |
| `VCC` | `3.3V` or `5V`, depending on your sensor module |
| `GND` | `GND` |

If the bridge prints `NO SIGNAL`, check `OUT -> D4/GPIO6`, `VCC`, and `GND` first.

### 2. Upload the USB-only Arduino sketch

In Arduino IDE:

1. Open:
   ```text
   tools/xiao_esp32c3_tcs3200_usb_serial/xiao_esp32c3_tcs3200_usb_serial.ino
   ```
2. Select board:
   ```text
   XIAO ESP32C3
   ```
3. Select the current USB port, for example:
   ```text
   /dev/cu.usbmodem14301
   ```
4. Click **Verify**.
5. Click **Upload**.
6. Wait for:
   ```text
   Done uploading
   ```
7. Close Arduino Serial Monitor before running the bridge.

### 3. Find the current USB port

On macOS, the port may change after upload/reset:

```bash
ls /dev/cu.*
```

Use the `usbmodem` port, for example:

```text
/dev/cu.usbmodem14301
```

### 4. Start the Flask app

From the repo root:

```bash
pip install -r services/web/requirements.txt
.venv/bin/python services/web/app.py
```

Open:

```text
http://127.0.0.1:8000/scans
```

### 5. Start the USB bridge

In a second terminal:

```bash
.venv/bin/python tools/arduino_serial_bridge.py \
  --port /dev/cu.usbmodem14301 \
  --baud 115200 \
  --web-url http://127.0.0.1:8000 \
  --device-id xiao-esp32-c3
```

Replace `/dev/cu.usbmodem14301` with your current port if it changed.

Good output looks like:

```text
heartbeat OK scanning_enabled=False
READY: USB serial sensor output
t=... R=...Hz G=...Hz B=...Hz R/B=... raw_pH=... => Neutral pH est_pH=7.00
```

### 6. Use the Scans page

1. Keep Flask running.
2. Keep the USB bridge running.
3. Open `http://127.0.0.1:8000/scans`.
4. The app should show **Idle** after the bridge heartbeat connects.
5. Click **Start Scan**.
6. The bridge should print:
   ```text
   heartbeat OK scanning_enabled=True
   sent label='...' pH=... status=200
   ```
7. The chart and table should update.
8. Click **Stop Scan** to stop sending real sensor readings.

### Demo buttons

- **Demo Scan** adds one fake reading for practice.
- Demo readings follow this order: red, orange, light green, blue, then repeat.
- **Reset Demo** removes the most recent 10 demo readings and resets the demo back to red.
- Demo readings do not require the ESP32.

### USB troubleshooting

| Problem | What it means | Fix |
|---|---|---|
| `Resource busy` | Arduino Serial Monitor or another bridge is using the port | Close Serial Monitor, stop old bridge, rerun |
| `No such file or directory` for `/dev/cu.usbmodem...` | The port changed | Run `ls /dev/cu.*` and use the new `usbmodem` port |
| `Connection refused` from `127.0.0.1:8000` | Flask is not running | Run `.venv/bin/python services/web/app.py` |
| `NO SIGNAL` / `R=0 G=0 B=0` | ESP32 sees no pulses from TCS3200 `OUT` | Check `OUT -> D4/GPIO6`, `VCC`, `GND`, `S0`, `S1` |
| Wi-Fi prompts appear in bridge output | Wrong sketch is uploaded | Upload the USB-only sketch above |
| Always reads one color | Sensor works, but calibration/lighting needs work | Use fixed distance, block ambient light, collect pH 3/5/7/9 samples |

## Deploy (single public link on Render)

This repo now includes `render.yaml` for one-click deployment of the web app.

1. Push this repo to GitHub.
2. In Render, click **New +** → **Blueprint**.
3. Select your repo and deploy.
4. In Render service settings, set secret env vars:
	- `OPENROUTER_API_KEY`
	- `DEVICE_INGEST_KEY` (optional)

Render will provide one public URL for the full web UI (dashboard, trends, recommendations, etc.).

## Hydrogel AI Scan — Required Env Vars

The hydrogel scan page uses a vision-capable AI model (Option B) to analyse uploaded images and return real pH estimates, plaque zone scores, and brushing recommendations.

| Variable | Required | Default | Description |
|---|---|---|---|
| `OPENAI_API_KEY` | Yes (for AI) | — | OpenAI or OpenRouter API key. Falls back to `OPENROUTER_API_KEY` if not set. |
| `OPENAI_MODEL` | No | `openai/gpt-4o-mini` | Vision-capable model name (OpenRouter or OpenAI model ID). |
| `OPENAI_BASE_URL` | No | `https://openrouter.ai/api/v1/chat/completions` | OpenAI-compatible endpoint. Change to `https://api.openai.com/v1/chat/completions` for direct OpenAI. |
| `OPENAI_TIMEOUT_SEC` | No | `30` | Request timeout in seconds for the AI vision call. |

**Quick setup on Render:**
- If you already have `OPENROUTER_API_KEY` set in Render, the hydrogel AI scan will automatically use it — no extra configuration needed.
- To use OpenAI directly, set `OPENAI_API_KEY` to your OpenAI key and `OPENAI_BASE_URL` to `https://api.openai.com/v1/chat/completions`.
- Never commit API keys to source code. Always use Render's secret env var panel.
