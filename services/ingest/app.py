from flask import Flask, request, jsonify
from datetime import datetime
import hashlib

app = Flask(__name__)

# Simple in-memory store and EMA smoothing per device for prototype
device_state = {}

def ema(prev, value, alpha=0.2):
    if prev is None:
        return value
    return prev * (1 - alpha) + value * alpha


@app.route('/v1/ingest', methods=['POST'])
def ingest():
    data = request.get_json(force=True)
    device_id = data.get('device_id')
    pH = data.get('pH')
    temp = data.get('temperature_c')
    seq = data.get('seq')

    if not device_id or pH is None:
        return jsonify({'error': 'missing device_id or pH'}), 400

    state = device_state.setdefault(device_id, {'ema_pH': None, 'last_seq': None})
    smoothed = ema(state['ema_pH'], float(pH))
    state['ema_pH'] = smoothed
    state['last_seq'] = seq

    # naive packet verification: check crc if present
    crc_ok = True
    if 'crc' in data:
        # simple demo hash check
        s = f"{device_id}:{seq}:{pH}"
        crc_ok = hashlib.sha256(s.encode()).hexdigest().startswith(str(data['crc'])[:4])

    record = {
        'device_id': device_id,
        'received_at': datetime.utcnow().isoformat() + 'Z',
        'pH_raw': pH,
        'pH_smoothed': round(smoothed, 3),
        'temperature_c': temp,
        'seq': seq,
        'crc_ok': crc_ok
    }

    return jsonify({'status': 'ok', 'record': record}), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
