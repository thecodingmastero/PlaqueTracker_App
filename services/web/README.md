# Web Dashboard (Prototype)

Simple Flask dashboard to preview `outputs/scan_result.json`, open the generated PDF report, and POST a test telemetry payload to the ingest endpoint.

Run locally from the repo root.

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pip install -r services\web\requirements.txt
.\.venv\Scripts\python.exe services\web\app.py
```

macOS/Linux:

```bash
pip install -r services/web/requirements.txt
.venv/bin/python services/web/app.py
```

Open: http://127.0.0.1:8000

## USB-C Sensor Testing (XIAO ESP32-C3 + TCS3200)

Use this flow when the sensor is plugged into your computer with USB-C. The ESP32 does **not** talk to the browser by itself over USB. A small Python bridge reads the USB Serial output and sends it to the Flask app.

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

If the bridge prints `NO SIGNAL`, first check `OUT -> D4/GPIO6`, `VCC`, and `GND`.

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
   COM5
   ```
   On macOS, the port may look like:
   ```text
   /dev/cu.usbmodem14301
   ```
4. Click **Verify**.
5. Click **Upload**.
6. Wait until Arduino IDE says:
   ```text
   Done uploading
   ```
7. Close Arduino Serial Monitor before running the bridge. Only one app can use the USB port at a time.

### 3. Find the current USB port

On Windows, check Device Manager under **Ports (COM & LPT)** or run:

```powershell
Get-CimInstance Win32_SerialPort | Select-Object DeviceID,Name,Description
```

Use the `COM` port shown for the board, for example:

```text
COM5
```

On macOS, the port may change after upload or reset. Run:

```bash
ls /dev/cu.*
```

Use the `usbmodem` port, for example:

```text
/dev/cu.usbmodem14301
```

### 4. Start the Flask app

Back in VS Code or Terminal, from the repo root:

```powershell
.\.venv\Scripts\python.exe services\web\app.py
```

Open the Scans page:

```text
http://127.0.0.1:8000/scans
```

### 5. Start the USB bridge

Open a second terminal and run:

```powershell
.\.venv\Scripts\python.exe tools\arduino_serial_bridge.py `
  --port COM5 `
  --baud 115200 `
  --web-url http://127.0.0.1:8000 `
  --device-id xiao-esp32-c3
```

Replace `COM5` with your current Windows port if it changed. On macOS, use the `/dev/cu.usbmodem...` port instead.

Good bridge output looks like:

```text
Listening on /dev/cu.usbmodem14301 @ 115200
heartbeat OK scanning_enabled=False
PlaqueTracker USB serial sensor starting
READY: USB serial sensor output
t=... R=...Hz G=...Hz B=...Hz R/B=... raw_pH=... => Neutral pH est_pH=7.00
```

### 6. Use Start Scan and Stop Scan

1. Keep Flask running.
2. Keep the USB bridge running.
3. Open `http://127.0.0.1:8000/scans`.
4. The app should show **Idle** after the bridge heartbeat connects.
5. Click **Start Scan**.
6. The bridge should show:
   ```text
   heartbeat OK scanning_enabled=True
   sent label='...' pH=... status=200
   ```
7. The chart and scan table should update.
8. Click **Stop Scan** to stop sending real sensor readings.

### 7. Demo buttons

- **Demo Scan** adds one fake reading for practice.
- Demo readings follow this color order: red, orange, light green, blue, then repeat.
- **Reset Demo** removes the most recent 10 demo readings and resets the demo back to red.
- Demo readings do not require the ESP32.

### Troubleshooting USB-C mode

| Problem | What it means | Fix |
|---|---|---|
| `Resource busy` | Arduino Serial Monitor or another bridge is using the port | Close Serial Monitor, stop old bridge, then rerun |
| `Access is denied` for `COMx` on Windows | Another app has the serial port open | Close Arduino Serial Monitor and stop any old bridge process, then rerun |
| `No such file or directory` for `/dev/cu.usbmodem...` | The port changed after upload/reset | Run `ls /dev/cu.*` and use the new `usbmodem` port |
| `Connection refused` from `127.0.0.1:8000` | Flask is not running | Run `.venv/bin/python services/web/app.py` |
| `NO SIGNAL` / `R=0 G=0 B=0` | ESP32 sees no pulses from TCS3200 `OUT` | Check `OUT -> D4/GPIO6`, `VCC`, `GND`, `S0`, `S1` |
| Wi-Fi prompts appear in bridge output | Wrong sketch is uploaded | Upload the USB-only sketch listed above |
| Always reads one color | Sensor works, but calibration/lighting needs work | Use fixed distance, block ambient light, collect pH 3/5/7/9 samples |

## Arduino UNO R4 WiFi (wireless direct ingest)

Use this only if the board sends data over Wi-Fi. For USB-C testing, use the bridge steps above instead.

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
