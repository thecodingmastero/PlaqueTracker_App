import argparse
import re
import time
from datetime import datetime

import requests


LINE_RE = re.compile(
    r"t=(?P<t>\d+)\s+R=(?P<r>[0-9.]+)Hz\s+G=(?P<g>[0-9.]+)Hz\s+B=(?P<b>[0-9.]+)Hz.*OUTstate=(?P<out>[01])\s+=>\s+(?P<label>.*?)(?:\s+est_pH=(?P<est>[0-9.-]+))?$"
)


def label_to_ph(label, r_hz=None, g_hz=None, b_hz=None, send_unclear=False):
    normalized = (label or "").strip().lower()
    if normalized == "no signal":
        return None
    if normalized == "low ph":
        return 5.4
    if normalized == "neutral ph":
        return 7.0
    if normalized == "high ph":
        return 7.6
    if normalized == "ph unclear":
        if not send_unclear:
            return None
        values = [v for v in [r_hz, g_hz, b_hz] if isinstance(v, (int, float))]
        if values:
            return 6.5
        return None
    return None


def color_from_ph(p_h):
    try:
        value = float(p_h)
    except Exception:
        return None
    if value < 6.3:
        return "Orange", "#F39C12", 0.86
    if value < 6.9:
        return "Yellow", "#F7DC6F", 0.78
    if value <= 7.2:
        return "Green", "#2ECC71", 0.9
    if value <= 8.0:
        return "Blue", "#3366FF", 0.84
    return "Purple", "#8E44AD", 0.82


def color_from_label(label):
    normalized = (label or "").strip().lower()
    if normalized == "low ph":
        return "Orange", "#F39C12", 0.88
    if normalized == "neutral ph":
        return "Green", "#2ECC71", 0.9
    if normalized == "high ph":
        return "Blue", "#3366FF", 0.88
    if normalized == "ph unclear":
        return "Yellow", "#F7DC6F", 0.35
    return "Unknown", "#94A3B8", 0.3


def parse_line(line):
    m = LINE_RE.search((line or "").strip())
    if not m:
        return None
    try:
        return {
            "millis": int(m.group("t")),
            "r_hz": float(m.group("r")),
            "g_hz": float(m.group("g")),
            "b_hz": float(m.group("b")),
            "out_state": int(m.group("out")),
            "label": m.group("label").strip(),
            "estimated_ph": float(m.group("est")) if m.group("est") else None,
        }
    except Exception:
        return None


def fetch_scanning_enabled(web_base, device_id):
    url = web_base.rstrip("/") + f"/api/device-control/{device_id}"
    resp = requests.get(url, timeout=6)
    resp.raise_for_status()
    payload = resp.json()
    return bool(payload.get("scanning_enabled", False))


def send_reading(web_base, device_id, parsed, p_h):
    url = web_base.rstrip("/") + "/api/device-ingest"
    color_name, rgb_value, confidence = color_from_ph(p_h) or color_from_label(parsed.get("label"))
    payload = {
        "device_id": device_id,
        "ts": datetime.utcnow().isoformat() + "Z",
        "classification": parsed.get("label"),
        "colorName": color_name,
        "rgbValue": rgb_value,
        "pH": round(float(p_h), 2),
        "estimatedPH": round(float(p_h), 2),
        "confidence": confidence,
        "r_hz": parsed.get("r_hz"),
        "g_hz": parsed.get("g_hz"),
        "b_hz": parsed.get("b_hz"),
        "out_state": parsed.get("out_state"),
        "seq": parsed.get("millis"),
    }
    resp = requests.post(url, json=payload, timeout=6)
    return resp.status_code


def main():
    parser = argparse.ArgumentParser(description="Bridge Arduino serial pH classification output into PlaqueTracker.")
    parser.add_argument("--port", required=True, help="Serial port (e.g., COM5)")
    parser.add_argument("--baud", type=int, default=115200, help="Serial baud rate")
    parser.add_argument("--web-url", default="http://localhost:8000", help="Base URL of PlaqueTracker web app")
    parser.add_argument("--device-id", default="uno-r4-tcs3200", help="Device ID to send")
    parser.add_argument("--send-unclear", action="store_true", help="Send a neutral fallback pH for 'pH unclear' lines")
    parser.add_argument("--min-send-interval", type=float, default=2.0, help="Minimum seconds between sends")
    parser.add_argument("--on-change-only", action="store_true", help="Send only when the classification label changes")
    parser.add_argument("--heartbeat-interval", type=float, default=3.0, help="Seconds between app control/heartbeat checks")
    args = parser.parse_args()

    try:
        import serial
    except Exception as exc:
        raise SystemExit("Missing dependency: pyserial. Install with: pip install pyserial") from exc

    ser = serial.Serial(args.port, args.baud, timeout=1)
    print(f"Listening on {args.port} @ {args.baud}. Sending to {args.web_url}/api/device-ingest")
    print("USB-C mode: this bridge is the app connection. Keep it running while testing.")

    last_sent_at = 0.0
    last_label = None
    last_heartbeat_at = 0.0
    scanning_enabled = False
    warned_wrong_sketch = False

    while True:
        now = time.time()
        if (now - last_heartbeat_at) >= args.heartbeat_interval:
            try:
                scanning_enabled = fetch_scanning_enabled(args.web_url, args.device_id)
                print(f"heartbeat OK scanning_enabled={scanning_enabled}")
            except Exception as exc:
                print(f"heartbeat failed: {exc}")
            last_heartbeat_at = now

        raw = ser.readline().decode("utf-8", errors="replace").strip()
        if not raw:
            continue

        print(raw)
        if not warned_wrong_sketch and (
            "Enter WiFi SSID" in raw
            or "Connecting to SSID" in raw
            or "WiFi connect failed" in raw
        ):
            print(
                "WARNING: The board is running a Wi-Fi sketch. "
                "Upload tools/xiao_esp32c3_tcs3200_usb_serial/"
                "xiao_esp32c3_tcs3200_usb_serial.ino and wait for 'Done uploading'."
            )
            warned_wrong_sketch = True

        parsed = parse_line(raw)
        if not parsed:
            continue

        label = parsed["label"]
        p_h = parsed.get("estimated_ph")
        if label.strip().lower() == "no signal":
            print("not sent: no TCS3200 output signal detected")
            continue
        if p_h is None:
            p_h = label_to_ph(
                label=label,
                r_hz=parsed.get("r_hz"),
                g_hz=parsed.get("g_hz"),
                b_hz=parsed.get("b_hz"),
                send_unclear=args.send_unclear,
            )
        if p_h is None:
            continue
        if p_h < 0:
            print(f"not sent: invalid pH {p_h:.2f}")
            continue
        if not scanning_enabled:
            print("not sent: app scanning is stopped")
            continue

        now = time.time()
        if args.on_change_only and last_label == label:
            continue
        if (now - last_sent_at) < args.min_send_interval:
            continue

        try:
            status = send_reading(args.web_url, args.device_id, parsed, p_h)
            print(f"sent label='{label}' pH={p_h:.2f} status={status}")
            last_sent_at = now
            last_label = label
        except Exception as exc:
            print(f"send failed: {exc}")


if __name__ == "__main__":
    main()
