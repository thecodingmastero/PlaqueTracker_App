import argparse
import re
import time

import requests


LINE_RE = re.compile(
    r"t=(?P<t>\d+)\s+R=(?P<r>[0-9.]+)Hz\s+G=(?P<g>[0-9.]+)Hz\s+B=(?P<b>[0-9.]+)Hz\s+OUTstate=(?P<out>[01])\s+=>\s+(?P<label>.+)$"
)


def label_to_ph(label, r_hz=None, g_hz=None, b_hz=None, send_unclear=False):
    normalized = (label or "").strip().lower()
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
        }
    except Exception:
        return None


def send_reading(web_base, device_id, p_h):
    url = web_base.rstrip("/") + "/test-ingest"
    payload = {
        "device_id": device_id,
        "pH": f"{p_h:.2f}",
    }
    resp = requests.post(url, data=payload, timeout=6, allow_redirects=False)
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
    args = parser.parse_args()

    try:
        import serial
    except Exception as exc:
        raise SystemExit("Missing dependency: pyserial. Install with: pip install pyserial") from exc

    ser = serial.Serial(args.port, args.baud, timeout=1)
    print(f"Listening on {args.port} @ {args.baud}. Sending to {args.web_url}/test-ingest")

    last_sent_at = 0.0
    last_label = None

    while True:
        raw = ser.readline().decode("utf-8", errors="replace").strip()
        if not raw:
            continue

        print(raw)
        parsed = parse_line(raw)
        if not parsed:
            continue

        label = parsed["label"]
        p_h = label_to_ph(
            label=label,
            r_hz=parsed.get("r_hz"),
            g_hz=parsed.get("g_hz"),
            b_hz=parsed.get("b_hz"),
            send_unclear=args.send_unclear,
        )
        if p_h is None:
            continue

        now = time.time()
        if args.on_change_only and last_label == label:
            continue
        if (now - last_sent_at) < args.min_send_interval:
            continue

        try:
            status = send_reading(args.web_url, args.device_id, p_h)
            print(f"sent label='{label}' pH={p_h:.2f} status={status}")
            last_sent_at = now
            last_label = label
        except Exception as exc:
            print(f"send failed: {exc}")


if __name__ == "__main__":
    main()
