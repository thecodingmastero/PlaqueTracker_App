from flask import Flask, render_template, render_template_string, request, redirect, url_for, send_file, jsonify, Response, stream_with_context
import requests
import json
import os
from datetime import datetime
import time
from urllib.parse import quote
import smtplib
from email.message import EmailMessage
from werkzeug.utils import secure_filename
import sys
from queue import Queue
# ensure repo root is on sys.path so sibling packages (hydrogel_cv) import when running this file directly
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from hydrogel_cv import scan as hydrogel_scan

app = Flask(__name__, static_url_path='/static', static_folder='static', template_folder='templates')

INGEST_URL = os.environ.get('INGEST_URL', 'http://localhost:8080/v1/ingest')
DATA_FILE = os.path.join(os.path.dirname(__file__), 'data.json')
OUTPUTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'outputs'))
UPLOADS_DIR = os.path.join(OUTPUTS_DIR, 'uploads')
MODEL_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'hydrogel_cv', 'model.pkl')
APPOINTMENTS_FILE = os.path.join(OUTPUTS_DIR, 'appointment_requests.jsonl')

OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY')
OPENROUTER_MODEL = os.environ.get('OPENROUTER_MODEL', 'arcee-ai/trinity-large-preview:free')
OPENROUTER_URL = os.environ.get('OPENROUTER_URL', 'https://openrouter.ai/api/v1/chat/completions')
OPENROUTER_TIMEOUT_SEC = int(os.environ.get('OPENROUTER_TIMEOUT_SEC', '20'))
DEVICE_INGEST_KEY = os.environ.get('DEVICE_INGEST_KEY')

_DENTIST_CACHE = {}
_DENTIST_CACHE_TTL_SEC = 300
MAX_UI_TREND_POINTS = 240
MAX_UI_TRENDS_PAGE_POINTS = 20
MAX_UI_TABLE_ROWS = 120
MAX_STORED_SCANS = 2000


def get_sensor_scans(scans):
    return [s for s in (scans or []) if s.get('source_type') in ('sensor', 'sensor_wifi')]


def get_hydrogel_scans(scans):
    return [s for s in (scans or []) if s.get('source_type') in ('image', 'hydrogel_image')]


def get_device_controls(data):
    controls = data.get('device_controls')
    if not isinstance(controls, dict):
        controls = {}
        data['device_controls'] = controls
    return controls


def get_device_scan_enabled(data, device_id):
    controls = get_device_controls(data)
    entry = controls.get(device_id)
    if isinstance(entry, dict) and 'scanning_enabled' in entry:
        return bool(entry.get('scanning_enabled'))
    return True


def set_device_scan_enabled(data, device_id, enabled):
    controls = get_device_controls(data)
    controls[device_id] = {
        'scanning_enabled': bool(enabled),
        'updated_at': datetime.utcnow().isoformat() + 'Z'
    }
    data['device_controls'] = controls


def build_plaque_location_feedback(hydrogel_result):
    meta = (hydrogel_result or {}).get('processing_metadata') or {}
    mean_rgb = meta.get('mean_rgb') or [128, 128, 128]

    try:
        red = float(mean_rgb[0])
        green = float(mean_rgb[1])
        blue = float(mean_rgb[2])
    except Exception:
        red, green, blue = 128.0, 128.0, 128.0

    ph_raw = (hydrogel_result or {}).get('estimated_pH')
    try:
        est_ph = float(ph_raw) if ph_raw is not None else 6.5
    except Exception:
        est_ph = 6.5

    def clamp(v):
        return max(0, min(100, int(round(v))))

    base = clamp(52 + (6.8 - est_ph) * 22)
    zones = [
        {'name': 'Upper Front', 'score': clamp(base + (red - green) * 0.55)},
        {'name': 'Left Gumline', 'score': clamp(base + (blue - red) * 0.45)},
        {'name': 'Right Molars', 'score': clamp(base + (green - blue) * 0.55)},
        {'name': 'Lower Front', 'score': clamp(base + (red - blue) * 0.35)}
    ]

    for z in zones:
        score = z['score']
        if score >= 70:
            z['level'] = 'High'
        elif score >= 45:
            z['level'] = 'Moderate'
        else:
            z['level'] = 'Low'

    ranked = sorted(zones, key=lambda x: x['score'], reverse=True)
    top = ranked[:2]
    summary = f"Possible plaque concentration near {top[0]['name']} and {top[1]['name']}."
    actions = [
        f"Focus brushing along the {top[0]['name'].lower()} for 20 to 30 seconds.",
        f"Use angled brushing + floss near the {top[1]['name'].lower()}.",
        'Retake a hydrogel scan after your next cleaning routine to compare improvements.'
    ]

    return {
        'ai_source': 'heuristic',
        'summary': summary,
        'zones': ranked,
        'actions': actions
    }


def process_hydrogel_upload_file(f):
    filename = secure_filename(getattr(f, 'filename', 'upload'))
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    path = os.path.join(UPLOADS_DIR, filename)
    try:
        f.save(path)
    except Exception:
        with open(path, 'wb') as out_f:
            out_f.write(f.read())

    model_path = MODEL_PATH if os.path.exists(MODEL_PATH) else 'model.pkl'
    try:
        result = hydrogel_scan.run(path, model_path)
    except Exception as e:
        result = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'source_type': 'hydrogel_image',
            'estimated_pH': 6.5,
            'confidence': 0.3,
            'error': str(e),
            'processing_metadata': {'mean_rgb': [128, 128, 128]}
        }

    plaque_ai = build_plaque_location_feedback(result)

    record = {
        'timestamp': result.get('timestamp') or (datetime.utcnow().isoformat() + 'Z'),
        'source_type': 'hydrogel_image',
        'device_id': 'uploaded-hydrogel-image',
        'pH': None,
        'estimated_pH': result.get('estimated_pH'),
        'plaque_ai': plaque_ai,
        'ingest_response': result
    }
    add_scan_record(record)
    return record


def get_market_items():
    return [
        {'id': 'sticker_01', 'name': 'Sparkly Tooth Sticker', 'cost': 50, 'category': 'Cosmetic', 'desc': 'A fun sticker for your profile!'},
        {'id': 'brush_up', 'name': 'Toothbrush Upgrade', 'cost': 120, 'category': 'Boost', 'desc': 'Animated toothbrush for your dashboard.'},
        {'id': 'confetti', 'name': 'Confetti Celebration', 'cost': 200, 'category': 'Cosmetic', 'desc': 'Play confetti when you save profile or hit a streak.'},
        {'id': 'theme_rainbow', 'name': 'Rainbow Theme Pack', 'cost': 300, 'category': 'Cosmetic', 'desc': 'Unlock a colorful premium look.'},
        {'id': 'avatar_pet', 'name': 'Tooth Fairy Pet Avatar', 'cost': 450, 'category': 'Cosmetic', 'desc': 'Cute companion for your profile.'},
        {'id': 'quiz_pass', 'name': 'Quiz Challenge Pass', 'cost': 180, 'category': 'Challenge', 'desc': 'Access bonus XP quiz challenges.'}
    ]


def get_earn_actions():
    return {
        'daily': {'xp': 5, 'label': 'Daily check-in', 'once_per_day': True},
        'scan': {'xp': 10, 'label': 'Upload a scan', 'once_per_day': False},
        'floss_log': {'xp': 8, 'label': 'Log flossing', 'once_per_day': False},
        'hydration': {'xp': 6, 'label': 'Hydration goal', 'once_per_day': False},
        'challenge': {'xp': 15, 'label': 'Complete mini challenge', 'once_per_day': False},
        'quiz': {'xp': 12, 'label': 'Complete quiz', 'once_per_day': False}
    }


def load_data():
    def _default_data():
        return {
            'profile': {'name': 'Test User', 'age': 30, 'brushing_frequency': 2, 'flossing_frequency': 3, 'baseline_pH_min': 6.2, 'baseline_pH_max': 7.2},
            'scans': [],
            'rewards': {'xp': 2000, 'badges': ['Starter']}
        }

    if not os.path.exists(DATA_FILE):
        data = _default_data()
        save_data(data)
        return data
    try:
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        try:
            broken_path = DATA_FILE + '.broken'
            if os.path.exists(broken_path):
                ts = str(int(time.time()))
                broken_path = DATA_FILE + f'.broken.{ts}'
            os.replace(DATA_FILE, broken_path)
        except Exception:
            pass
        data = _default_data()
        save_data(data)
        return data


def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def add_scan_record(record):
    data = load_data()
    data['scans'].append(record)
    if len(data['scans']) > MAX_STORED_SCANS:
        data['scans'] = data['scans'][-MAX_STORED_SCANS:]
    save_data(data)
    # also write latest scan to outputs for compatibility
    os.makedirs(OUTPUTS_DIR, exist_ok=True)
    with open(os.path.join(OUTPUTS_DIR, 'scan_result.json'), 'w') as f:
        json.dump(record, f, indent=2)


# Simple Server-Sent Events (SSE) broadcaster for live updates in the UI
_sse_clients = []

def broadcast_event(event, data):
    payload = {'event': event, 'data': data}
    # push to all connected client queues (non-blocking)
    for q in list(_sse_clients):
        try:
            q.put(payload)
        except Exception:
            try:
                _sse_clients.remove(q)
            except Exception:
                pass


@app.route('/events')
def events():
    def gen():
        q = Queue()
        _sse_clients.append(q)
        try:
            while True:
                item = q.get()
                yield f"event: {item.get('event')}\n"
                yield f"data: {json.dumps(item.get('data'))}\n\n"
        except GeneratorExit:
            try:
                _sse_clients.remove(q)
            except Exception:
                pass

    return Response(stream_with_context(gen()), mimetype='text/event-stream')


@app.after_request
def add_cors_headers(response):
    # allow simple local dev cross-origin requests and preflight responses
    response.headers.setdefault('Access-Control-Allow-Origin', '*')
    response.headers.setdefault('Access-Control-Allow-Headers', 'Content-Type')
    response.headers.setdefault('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
    return response


@app.before_request
def handle_options_preflight():
    # Respond to CORS preflight requests with allowed methods/headers
    if request.method == 'OPTIONS':
        resp = app.make_default_options_response()
        h = resp.headers
        h['Access-Control-Allow-Origin'] = '*'
        h['Access-Control-Allow-Headers'] = 'Content-Type'
        h['Access-Control-Allow-Methods'] = 'GET,POST,OPTIONS'
        return resp


@app.route('/')
def index():
    data = load_data()
    sensor_scans = get_sensor_scans(data.get('scans', []))
    latest = sensor_scans[-1] if sensor_scans else None
    recommendations = []
    if latest:
        ph = latest.get('estimated_pH') or latest.get('pH')
        if ph < 5.5:
            recommendations.append('High acid exposure — rinse with water after meals')
            recommendations.append('Reduce acidic drinks (soda, citrus)')
        elif ph < 6.5:
            recommendations.append('Consider more saliva-stimulating foods (cheese, nuts)')
        else:
            recommendations.append('Keep up the good work!')
    # prepare series for inline chart
    series = [{'t': s.get('timestamp'), 'pH': s.get('estimated_pH') or s.get('pH')} for s in sensor_scans]
    return render_template('dashboard.html', profile=data['profile'], latest=latest, recommendations=recommendations, rewards=data['rewards'], series=series)


@app.route('/profile', methods=['GET','POST'])
def profile():
    data = load_data()
    if request.method == 'POST':
        form = request.form
        profile = data.get('profile', {})
        profile['name'] = form.get('name', profile.get('name'))
        try:
            profile['age'] = int(form.get('age', profile.get('age', 0)))
        except Exception:
            profile['age'] = profile.get('age', 0)
        try:
            profile['brushing_frequency'] = int(form.get('brushing_frequency', profile.get('brushing_frequency', 0)))
        except Exception:
            profile['brushing_frequency'] = profile.get('brushing_frequency', 0)
        try:
            profile['flossing_frequency'] = int(form.get('flossing_frequency', profile.get('flossing_frequency', 0)))
        except Exception:
            profile['flossing_frequency'] = profile.get('flossing_frequency', 0)
        try:
            profile['baseline_pH_min'] = float(form.get('baseline_pH_min', profile.get('baseline_pH_min', 6.5)))
            profile['baseline_pH_max'] = float(form.get('baseline_pH_max', profile.get('baseline_pH_max', 7.0)))
        except Exception:
            pass
        data['profile'] = profile
        save_data(data)
        try:
            broadcast_event('profile', profile)
        except Exception:
            pass
        return redirect(url_for('profile'))
    return render_template('profile.html', profile=data['profile'])


@app.route('/scans')
def scans():
    data = load_data()
    sensor_scans = get_sensor_scans(data.get('scans', []))
    recent_for_chart = sensor_scans[-MAX_UI_TREND_POINTS:]
    recent_for_table = list(reversed(sensor_scans[-MAX_UI_TABLE_ROWS:]))
    series = [{'t': s.get('timestamp'), 'pH': s.get('estimated_pH') or s.get('pH')} for s in recent_for_chart]
    return render_template('scans.html', scans=recent_for_table, series=series)


@app.route('/hydrogel')
def hydrogel_page():
    data = load_data()
    hydrogel_scans = list(reversed(get_hydrogel_scans(data.get('scans', []))[-MAX_UI_TABLE_ROWS:]))
    return render_template('hydrogel.html', scans=hydrogel_scans)


@app.route('/trends')
def trends():
    data = load_data()
    sensor_scans = get_sensor_scans(data.get('scans', []))
    recent_for_chart = sensor_scans[-MAX_UI_TRENDS_PAGE_POINTS:]
    # prepare time-series
    series = [{'t': s.get('timestamp'), 'pH': s.get('estimated_pH') or s.get('pH')} for s in recent_for_chart]
    return render_template('trends.html', series=series)


@app.route('/recommendations')
def recommendations_page():
    """Render the recommendations page UI which will fetch details from `/api/recommendations`."""
    data = load_data()
    return render_template('recommendations.html', profile=data.get('profile', {}))


def get_dentist_recommendations(city=None, state=None, country=None, lat=None, lon=None, zip_code=None):
    dentists = [
        {'name': 'Bright Smile Dental', 'distance_km': 1.2, 'lat': 40.7128, 'lon': -74.0060, 'phone': '+1-555-0101', 'notes': 'Accepts walk-ins; pediatric-friendly'},
        {'name': 'Lakeside Family Dentistry', 'distance_km': 3.4, 'lat': 40.7295, 'lon': -73.9965, 'phone': '+1-555-0123', 'notes': 'Good for routine cleanings and check-ups'},
        {'name': 'Downtown Dental Care', 'distance_km': 5.0, 'lat': 40.7060, 'lon': -74.0086, 'phone': '+1-555-0188', 'notes': 'Offers same-day emergency appointments'}
    ]

    def haversine_km(a_lat, a_lon, b_lat, b_lon):
        try:
            from math import radians, sin, cos, sqrt, atan2
            R = 6371.0
            dlat = radians(b_lat - a_lat)
            dlon = radians(b_lon - a_lon)
            a = sin(dlat / 2) ** 2 + cos(radians(a_lat)) * cos(radians(b_lat)) * sin(dlon / 2) ** 2
            c = 2 * atan2(sqrt(a), sqrt(1 - a))
            return R * c
        except Exception:
            return None

    def geocode_location(query):
        if not query:
            return None
        try:
            r = requests.get(
                'https://nominatim.openstreetmap.org/search',
                params={'q': query, 'format': 'jsonv2', 'limit': 1},
                headers={'User-Agent': 'PlaqueTracker/1.0'},
                timeout=10
            )
            if r.status_code >= 400:
                return None
            rows = r.json()
            if isinstance(rows, list) and rows:
                first = rows[0]
                return float(first.get('lat')), float(first.get('lon'))
        except Exception:
            return None
        return None

    def fetch_nearby_dentists(center_lat, center_lon):
        try:
            radius_m = 5000
            overpass_query = f"""
            [out:json][timeout:20];
            (
              node["amenity"="dentist"](around:{radius_m},{center_lat},{center_lon});
              way["amenity"="dentist"](around:{radius_m},{center_lat},{center_lon});
              relation["amenity"="dentist"](around:{radius_m},{center_lat},{center_lon});
            );
            out center tags;
            """
            elements = []
            for endpoint in [
                'https://overpass-api.de/api/interpreter',
                'https://overpass.kumi.systems/api/interpreter'
            ]:
                try:
                    rr = requests.post(
                        endpoint,
                        data=overpass_query,
                        headers={'User-Agent': 'PlaqueTracker/1.0'},
                        timeout=15
                    )
                    if rr.status_code >= 400:
                        continue
                    payload = rr.json() if rr.content else {}
                    rows = payload.get('elements', []) if isinstance(payload, dict) else []
                    if rows:
                        elements = rows
                        break
                except Exception:
                    continue
            if not elements:
                return []
            out = []
            seen = set()
            for el in elements:
                tags = el.get('tags') or {}
                name = (tags.get('name') or '').strip()
                if not name:
                    continue
                el_lat = el.get('lat')
                el_lon = el.get('lon')
                center = el.get('center') or {}
                if el_lat is None:
                    el_lat = center.get('lat')
                if el_lon is None:
                    el_lon = center.get('lon')
                if el_lat is None or el_lon is None:
                    continue
                key = (name.lower(), round(float(el_lat), 4), round(float(el_lon), 4))
                if key in seen:
                    continue
                seen.add(key)

                dist = haversine_km(float(center_lat), float(center_lon), float(el_lat), float(el_lon))
                phone = tags.get('phone') or tags.get('contact:phone') or 'N/A'
                street = tags.get('addr:street') or ''
                house = tags.get('addr:housenumber') or ''
                locality = tags.get('addr:city') or tags.get('addr:town') or tags.get('addr:village') or ''
                addr = ' '.join(part for part in [house, street] if part).strip()
                notes = addr if addr else (locality if locality else 'Dental clinic nearby')

                out.append({
                    'name': name,
                    'distance_km': round(dist, 2) if dist is not None else None,
                    'lat': float(el_lat),
                    'lon': float(el_lon),
                    'phone': phone,
                    'notes': notes
                })

            out = sorted(out, key=lambda x: x.get('distance_km') if x.get('distance_km') is not None else 9999)
            return out[:15]
        except Exception:
            return []

    resolved_lat = None
    resolved_lon = None

    if lat is not None and lon is not None:
        try:
            resolved_lat = float(lat)
            resolved_lon = float(lon)
        except Exception:
            pass

    if resolved_lat is None or resolved_lon is None:
        location_query = ', '.join([x for x in [str(city or '').strip(), str(state or '').strip(), str(country or '').strip()] if x])
        if not location_query and zip_code:
            location_query = str(zip_code).strip()
        if location_query:
            geo = geocode_location(location_query)
            if geo:
                resolved_lat, resolved_lon = geo

    if resolved_lat is not None and resolved_lon is not None:
        cache_key = f"{round(float(resolved_lat), 3)}:{round(float(resolved_lon), 3)}"
        cached = _DENTIST_CACHE.get(cache_key)
        now_ts = time.time()
        if cached and (now_ts - cached.get('ts', 0) <= _DENTIST_CACHE_TTL_SEC):
            return list(cached.get('rows', []))

        live = fetch_nearby_dentists(resolved_lat, resolved_lon)
        if not live:
            try:
                time.sleep(0.4)
            except Exception:
                pass
            live = fetch_nearby_dentists(resolved_lat, resolved_lon)
        if live:
            _DENTIST_CACHE[cache_key] = {'ts': now_ts, 'rows': live}
            return live

        try:
            for d in dentists:
                if 'lat' in d and 'lon' in d:
                    dist = haversine_km(resolved_lat, resolved_lon, float(d['lat']), float(d['lon']))
                    d['distance_km'] = round(dist, 2) if dist is not None else d.get('distance_km', 0)
            dentists = sorted(dentists, key=lambda x: x.get('distance_km', 9999))
        except Exception:
            pass
    else:
        try:
            location_key = ' '.join([str(city or '').strip(), str(state or '').strip(), str(country or '').strip()]).strip()
            if not location_key and zip_code:
                location_key = str(zip_code).strip()
            if location_key:
                seed = sum(ord(c) for c in location_key.lower()) % 7
                for i, d in enumerate(dentists):
                    offset = (seed - i) * 0.25
                    d['distance_km'] = round(max(0.1, d.get('distance_km', 1.0) + offset), 1)
                dentists = sorted(dentists, key=lambda x: x['distance_km'])
        except Exception:
            pass

    return dentists


def build_google_maps_dentist_url(city=None, state=None, country=None, zip_code=None, lat=None, lon=None):
    try:
        if lat is not None and lon is not None:
            a_lat = float(lat)
            a_lon = float(lon)
            query = f'dentist near {a_lat},{a_lon}'
        else:
            parts = [str(city or '').strip(), str(state or '').strip(), str(country or '').strip()]
            location = ', '.join([p for p in parts if p])
            if not location and zip_code:
                location = str(zip_code).strip()
            query = f'dentist near {location}' if location else 'dentist near me'
        return 'https://www.google.com/maps/search/?api=1&query=' + quote(query)
    except Exception:
        return 'https://www.google.com/maps/search/?api=1&query=dentist%20near%20me'


def get_ai_recommendations_from_scans(scans):
    recent = list(reversed(scans or []))[:6]
    ph_values = [s.get('estimated_pH') or s.get('pH') for s in recent if (s.get('estimated_pH') or s.get('pH')) is not None]
    avg_ph = round(sum(ph_values) / len(ph_values), 2) if ph_values else None
    last_ph = ph_values[0] if ph_values else None
    prev_ph = ph_values[1] if len(ph_values) > 1 else None

    suggestions = []
    dietary_recommendations = []
    if last_ph is None:
        suggestions.append('No recent pH scans found — take a photo scan to get started.')
        dietary_recommendations.append('Build a balanced meal pattern with fewer sugary/acidic snacks between meals.')
        dietary_recommendations.append('Drink plain water regularly to support saliva and oral pH balance.')
    else:
        if last_ph < 5.5:
            suggestions.append('Low pH detected — avoid acidic drinks and rinse with water after meals.')
            suggestions.append('Use fluoride toothpaste and avoid brushing immediately after acidic meals.')
            dietary_recommendations.append('Limit soda, sports drinks, citrus juices, and frequent sour candies.')
            dietary_recommendations.append('Choose neutral snacks like cheese, nuts, yogurt, or whole grains.')
            dietary_recommendations.append('Pair acidic foods with meals instead of sipping/snacking over long periods.')
        elif last_ph < 6.2:
            suggestions.append('Slight acid exposure — increase saliva-friendly snacks (cheese, nuts) and stay hydrated.')
            dietary_recommendations.append('Reduce between-meal sugar frequency and choose high-fiber snacks.')
            dietary_recommendations.append('Increase water intake after coffee, tea, or flavored drinks.')
        else:
            suggestions.append('pH looks healthy — maintain your current oral care routine.')
            dietary_recommendations.append('Maintain a low-added-sugar diet and keep hydration consistent.')
            dietary_recommendations.append('Continue balanced meals with calcium/protein-rich foods for enamel support.')

        if prev_ph is not None:
            if last_ph < prev_ph - 0.2:
                suggestions.append('Trend note: pH decreased vs previous reading — schedule a dentist check if this continues.')
            elif last_ph > prev_ph + 0.2:
                suggestions.append('Trend note: pH improved since last reading — great progress!')

    # simple trend-based risk estimation (prototype heuristic)
    def compute_risks(values):
        values = [float(v) for v in (values or [])]

        def clamp(v, lo=0, hi=100):
            return max(lo, min(hi, int(round(v))))

        def risk_band(score):
            if score < 35:
                return 'Low'
            if score < 65:
                return 'Moderate'
            return 'High'

        _last = values[0] if values else None
        _avg = (sum(values) / len(values)) if values else None

        _trend_delta = 0.0
        if len(values) >= 2:
            _trend_delta = float(values[0]) - float(values[-1])

        variability = float(max(values) - min(values)) if values else 0.0

        acid_load = 0.0
        if _last is not None:
            if _last < 5.5:
                acid_load += 40
            elif _last < 6.0:
                acid_load += 28
            elif _last < 6.5:
                acid_load += 12
        if _avg is not None:
            if _avg < 5.8:
                acid_load += 30
            elif _avg < 6.2:
                acid_load += 18
            elif _avg < 6.6:
                acid_load += 8
        if _trend_delta < -0.3:
            acid_load += 16
        if values and min(values) < 5.3:
            acid_load += 12

        cavity_score = clamp(12 + acid_load * 0.95)
        plaque_score = clamp(20 + acid_load * 0.65 + (10 if len(values) < 3 else 0))
        gum_score = clamp(16 + acid_load * 0.55 + variability * 18)

        return {
            'trend_delta': round(_trend_delta, 2),
            'cavity': {'score': cavity_score, 'band': risk_band(cavity_score)},
            'plaque': {'score': plaque_score, 'band': risk_band(plaque_score)},
            'gum_disease': {'score': gum_score, 'band': risk_band(gum_score)}
        }

    risk_calc = compute_risks(ph_values)
    trend_delta = risk_calc.get('trend_delta', 0.0)
    risks = {
        'cavity': risk_calc['cavity'],
        'plaque': risk_calc['plaque'],
        'gum_disease': risk_calc['gum_disease']
    }

    # history for charting (up to last 12 scans)
    history_scans = list(reversed(scans or []))[:12]
    timeline = []
    ph_timeline = []
    for item in history_scans:
        val = item.get('estimated_pH') or item.get('pH')
        if val is None:
            continue
        ph_timeline.append(float(val))
        timeline.append(item.get('timestamp'))

    cavity_hist = []
    plaque_hist = []
    gum_hist = []
    for i in range(len(ph_timeline)):
        # rolling window up to this point (max 6)
        window = list(reversed(ph_timeline[max(0, i - 5): i + 1]))
        rc = compute_risks(window)
        cavity_hist.append(rc['cavity']['score'])
        plaque_hist.append(rc['plaque']['score'])
        gum_hist.append(rc['gum_disease']['score'])

    risk_history = {
        'labels': timeline,
        'cavity': cavity_hist,
        'plaque': plaque_hist,
        'gum_disease': gum_hist
    }

    # Add concise action message if any risk is elevated
    highest = max(risks.items(), key=lambda kv: kv[1]['score']) if risks else None
    if highest and highest[1]['score'] >= 65:
        suggestions.append(f"Risk outlook: {highest[0].replace('_', ' ')} risk is {highest[1]['band'].lower()} ({highest[1]['score']}%). Prioritize preventive care this week.")

    # de-duplicate while preserving order
    dietary_recommendations = list(dict.fromkeys([str(x).strip() for x in dietary_recommendations if str(x).strip()]))

    return {
        'ai_suggestions': suggestions,
        'dietary_recommendations': dietary_recommendations,
        'avg_ph': avg_ph,
        'last_ph': last_ph,
        'trend_delta': round(trend_delta, 2),
        'risks': risks,
        'risk_history': risk_history,
        'ai_source': 'heuristic'
    }


def _risk_band(score):
    if score < 35:
        return 'Low'
    if score < 65:
        return 'Moderate'
    return 'High'


def _parse_json_from_text(content):
    text = str(content or '').strip()
    if not text:
        return None
    if text.startswith('```'):
        text = text.strip('`')
        if text.lower().startswith('json'):
            text = text[4:].strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    # try to salvage by extracting first JSON object
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except Exception:
            return None
    return None


def maybe_apply_openrouter_ai(scans, profile, base_payload):
    """Augment heuristic recommendations with OpenRouter if API key is configured.

    Returns base payload unchanged when API key is missing or call fails.
    """
    if not OPENROUTER_API_KEY:
        out = dict(base_payload)
        out['ai_source'] = 'heuristic'
        out['ai_error'] = 'OPENROUTER_API_KEY is not set'
        return out

    recent = list(reversed(scans or []))[:12]
    scan_rows = []
    for s in recent:
        ph = s.get('estimated_pH') if s.get('estimated_pH') is not None else s.get('pH')
        scan_rows.append({'timestamp': s.get('timestamp'), 'pH': ph, 'source': s.get('source_type')})

    prompt_payload = {
        'profile': {
            'age': (profile or {}).get('age'),
            'brushing_frequency': (profile or {}).get('brushing_frequency'),
            'flossing_frequency': (profile or {}).get('flossing_frequency'),
            'baseline_pH_min': (profile or {}).get('baseline_pH_min'),
            'baseline_pH_max': (profile or {}).get('baseline_pH_max')
        },
        'scan_rows': scan_rows,
        'heuristic': {
            'avg_ph': base_payload.get('avg_ph'),
            'last_ph': base_payload.get('last_ph'),
            'trend_delta': base_payload.get('trend_delta'),
            'risks': base_payload.get('risks')
        }
    }

    system_msg = (
    "You are a backend API. "
    "You MUST output ONLY valid JSON. "
    "Do NOT include explanations, markdown, comments, or extra text. "
    "The response MUST start with '{' and end with '}'. "
    "Return exactly this JSON schema:\n"
    "{"
    "  ai_suggestions: string[],"
    "  dietary_recommendations: string[],"
    "  risk_overrides: { cavity?: number, plaque?: number, gum_disease?: number }"
    "}\n"
    "If unsure, return empty arrays/objects but still valid JSON."
    )

    body = {
    'model': OPENROUTER_MODEL,
    'messages': [
        {'role': 'system', 'content': system_msg},
        {'role': 'user', 'content': json.dumps(prompt_payload)}
    ],
    'temperature': 0.0,
    'max_tokens': 300
}

    headers = {
        'Authorization': f'Bearer {OPENROUTER_API_KEY}',
        'Content-Type': 'application/json'
    }
    # Optional identifiers (useful for OpenRouter analytics/rate control)
    site_url = os.environ.get('OPENROUTER_SITE_URL')
    site_name = os.environ.get('OPENROUTER_SITE_NAME')
    if site_url:
        headers['HTTP-Referer'] = site_url
    if site_name:
        headers['X-Title'] = site_name

    try:
        resp = requests.post(OPENROUTER_URL, headers=headers, json=body, timeout=OPENROUTER_TIMEOUT_SEC)
        if resp.status_code >= 400:
            out = dict(base_payload)
            out['ai_source'] = 'heuristic'
            msg = ''
            try:
                err = resp.json()
                if isinstance(err, dict):
                    msg = ((err.get('error') or {}).get('message') if isinstance(err.get('error'), dict) else '') or ''
            except Exception:
                msg = ''
            out['ai_error'] = f'OpenRouter HTTP {resp.status_code}' + (f': {msg}' if msg else '')
            return out
        raw = resp.json()
        content = raw.get('choices', [{}])[0].get('message', {}).get('content', '')
        parsed = _parse_json_from_text(content)
        if not isinstance(parsed, dict):
            out = dict(base_payload)
            out['ai_source'] = 'heuristic'
            out['ai_error'] = 'OpenRouter returned non-JSON or unexpected response format'
            return out

        out = dict(base_payload)
        suggestions = parsed.get('ai_suggestions')
        if isinstance(suggestions, list) and suggestions:
            out['ai_suggestions'] = [str(x) for x in suggestions[:6]]

        dietary = parsed.get('dietary_recommendations')
        if isinstance(dietary, list) and dietary:
            out['dietary_recommendations'] = [str(x) for x in dietary[:6]]

        overrides = parsed.get('risk_overrides')
        if isinstance(overrides, dict):
            risks = dict(out.get('risks') or {})
            for key in ('cavity', 'plaque', 'gum_disease'):
                if key in overrides:
                    try:
                        score = int(round(float(overrides[key])))
                        score = max(0, min(100, score))
                        risks[key] = {'score': score, 'band': _risk_band(score)}
                    except Exception:
                        pass
            out['risks'] = risks

        out['ai_source'] = 'openrouter'
        out['ai_error'] = None
        return out
    except Exception as e:
        out = dict(base_payload)
        out['ai_source'] = 'heuristic'
        out['ai_error'] = f'OpenRouter request failed: {str(e)}'
        return out


@app.route('/ai-recommendations')
def ai_recommendations_page():
    data = load_data()
    return render_template('ai_recommendations.html', profile=data.get('profile', {}))


@app.route('/api/ai-recommendations', methods=['GET'])
def api_ai_recommendations():
    data = load_data()
    sensor_scans = get_sensor_scans(data.get('scans', []))
    payload = get_ai_recommendations_from_scans(sensor_scans)
    payload = maybe_apply_openrouter_ai(sensor_scans, data.get('profile', {}), payload)
    if 'ai_error' not in payload:
        payload['ai_error'] = None
    payload['status'] = 'ok'
    return jsonify(payload)


@app.route('/dentists')
def dentists_page():
    data = load_data()
    return render_template('dentists.html', profile=data.get('profile', {}))


@app.route('/api/dentists', methods=['GET'])
def api_dentists():
    city = request.args.get('city')
    state = request.args.get('state')
    country = request.args.get('country')
    zip_code = request.args.get('zip')
    lat = request.args.get('lat')
    lon = request.args.get('lon')
    dentists = get_dentist_recommendations(city=city, state=state, country=country, lat=lat, lon=lon, zip_code=zip_code)
    maps_url = build_google_maps_dentist_url(city=city, state=state, country=country, zip_code=zip_code, lat=lat, lon=lon)
    return jsonify({'status': 'ok', 'dentists': dentists, 'city': city, 'state': state, 'country': country, 'zip': zip_code, 'lat': lat, 'lon': lon, 'google_maps_url': maps_url})


@app.route('/api/latest-scan', methods=['GET'])
def api_latest_scan():
    data = load_data()
    sensor_scans = get_sensor_scans(data.get('scans', []))
    latest = sensor_scans[-1] if sensor_scans else None
    return jsonify({'status': 'ok', 'latest': latest})


@app.route('/api/recommendations', methods=['GET'])
def api_recommendations():
    """Return AI-generated suggestions and a small list of local dentist recommendations.

    This is a lightweight mock: it inspects recent scans and returns simple advice.
    """
    data = load_data()
    sensor_scans = get_sensor_scans(data.get('scans', []))
    ai_payload = get_ai_recommendations_from_scans(sensor_scans)
    ai_payload = maybe_apply_openrouter_ai(sensor_scans, data.get('profile', {}), ai_payload)

    lat = request.args.get('lat')
    lon = request.args.get('lon')
    city = request.args.get('city')
    state = request.args.get('state')
    country = request.args.get('country')
    zip_code = request.args.get('zip')
    dentists = get_dentist_recommendations(city=city, state=state, country=country, lat=lat, lon=lon, zip_code=zip_code)
    maps_url = build_google_maps_dentist_url(city=city, state=state, country=country, zip_code=zip_code, lat=lat, lon=lon)

    resp = {
        'status': 'ok',
        'ai_suggestions': ai_payload.get('ai_suggestions', []),
        'dietary_recommendations': ai_payload.get('dietary_recommendations', []),
        'avg_ph': ai_payload.get('avg_ph'),
        'last_ph': ai_payload.get('last_ph'),
        'ai_source': ai_payload.get('ai_source', 'heuristic'),
        'ai_error': ai_payload.get('ai_error'),
        'dentists': dentists,
        'city': city,
        'state': state,
        'country': country,
        'zip': zip_code,
        'lat': lat,
        'lon': lon,
        'google_maps_url': maps_url
    }
    return jsonify(resp)


@app.route('/api/appointment-request', methods=['POST'])
def api_appointment_request():
    """Create an appointment request for a dentist.

    Persists every request locally, and optionally sends email if SMTP env vars are configured.
    """
    try:
        payload = request.get_json(force=True) or {}
    except Exception:
        return jsonify({'status': 'error', 'message': 'invalid json'}), 400

    dentist_name = str(payload.get('dentist_name', '')).strip()
    patient_name = str(payload.get('patient_name', '')).strip() or 'Patient'
    contact = str(payload.get('contact', '')).strip()
    preferred_date = str(payload.get('preferred_date', '')).strip()
    notes = str(payload.get('notes', '')).strip()

    if not dentist_name:
        return jsonify({'status': 'error', 'message': 'dentist_name is required'}), 400

    record = {
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'dentist_name': dentist_name,
        'patient_name': patient_name,
        'contact': contact,
        'preferred_date': preferred_date,
        'notes': notes
    }

    os.makedirs(OUTPUTS_DIR, exist_ok=True)
    try:
        with open(APPOINTMENTS_FILE, 'a', encoding='utf-8') as f:
            f.write(json.dumps(record) + '\n')
    except Exception as e:
        return jsonify({'status': 'error', 'message': 'failed to save request', 'error': str(e)}), 500

    # Optional SMTP send if configured.
    # Required env vars: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, APPOINTMENT_TO_EMAIL
    smtp_host = os.environ.get('SMTP_HOST')
    smtp_port = os.environ.get('SMTP_PORT')
    smtp_user = os.environ.get('SMTP_USER')
    smtp_pass = os.environ.get('SMTP_PASS')
    to_email = os.environ.get('APPOINTMENT_TO_EMAIL')

    delivery = 'saved'
    if smtp_host and smtp_port and smtp_user and smtp_pass and to_email:
        try:
            msg = EmailMessage()
            msg['Subject'] = f'PlaqueTracker appointment request - {dentist_name}'
            msg['From'] = smtp_user
            msg['To'] = to_email
            msg.set_content(
                f"Appointment request\n\n"
                f"Dentist: {dentist_name}\n"
                f"Patient: {patient_name}\n"
                f"Contact: {contact}\n"
                f"Preferred Date: {preferred_date}\n"
                f"Notes: {notes}\n"
            )

            with smtplib.SMTP(smtp_host, int(smtp_port), timeout=10) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.send_message(msg)
            delivery = 'email_sent'
        except Exception:
            delivery = 'saved_email_failed'

    return jsonify({'status': 'ok', 'delivery': delivery, 'record': record})


@app.route('/rewards', methods=['GET','POST'])
def rewards():
    data = load_data()
    # simple badge catalog for descriptions
    badge_catalog = {
        'Starter': 'Joined PlaqueTracker',
        'acidd_defender': 'Completed acid-reduction challenge',
        'consistency_pro': '7-day brushing streak',
        'photo_master': 'Submitted 5 scans with photos'
    }
    # marketplace items (spend XP)
    market_items = get_market_items()
    earn_actions = get_earn_actions()

    # compute streaks (consecutive days with at least one scan)
    def compute_streak(scans):
        if not scans:
            return 0
        # extract dates (UTC) from timestamps, sort descending
        import datetime as _dt
        dates = sorted({_dt.datetime.fromisoformat(s['timestamp'].replace('Z','')) .date() for s in scans})
        # count consecutive days ending at most recent date
        today = dates[-1]
        streak = 0
        cur = today
        while cur in dates:
            streak += 1
            cur = cur - _dt.timedelta(days=1)
        return streak

    streak = compute_streak(data.get('scans', []))
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'redeem':
            badge = request.form.get('badge')
            if badge:
                # give XP and add badge if not present
                rewards = data.get('rewards', {'xp':0,'badges':[]})
                if badge not in rewards.get('badges', []):
                    rewards['badges'].append(badge)
                    rewards['xp'] = rewards.get('xp',0) + 20
                    data['rewards'] = rewards
                    save_data(data)
                    try:
                        broadcast_event('rewards', rewards)
                    except Exception:
                        pass
        return redirect(url_for('rewards'))
    return render_template('rewards.html', rewards=data['rewards'], badge_catalog=badge_catalog, market_items=market_items, earn_actions=earn_actions, streak=streak)


@app.route('/devices')
def devices():
    data = load_data()
    sensor_scans = get_sensor_scans(data.get('scans', []))
    latest_by_device = {}
    for rec in sensor_scans:
        did = str(rec.get('device_id') or '').strip()
        if not did:
            continue
        prev = latest_by_device.get(did)
        if not prev or str(rec.get('timestamp', '')) > str(prev.get('timestamp', '')):
            latest_by_device[did] = rec

    devices = []
    for did, rec in latest_by_device.items():
        devices.append({
            'id': did,
            'last_seen': rec.get('timestamp'),
            'battery': rec.get('battery') if rec.get('battery') is not None else '—',
            'scanning_enabled': get_device_scan_enabled(data, did)
        })

    controls = get_device_controls(data)
    for did, conf in controls.items():
        if did not in latest_by_device:
            devices.append({
                'id': did,
                'last_seen': conf.get('updated_at') or '—',
                'battery': '—',
                'scanning_enabled': bool(conf.get('scanning_enabled', True))
            })

    devices = sorted(devices, key=lambda d: str(d.get('last_seen') or ''), reverse=True)
    return render_template('devices.html', devices=devices)


@app.route('/api/device-control/<device_id>', methods=['GET', 'POST'])
def api_device_control(device_id):
    device_id = str(device_id or '').strip()
    if not device_id:
        return jsonify({'status': 'error', 'message': 'device_id is required'}), 400

    data = load_data()
    if request.method == 'GET':
        return jsonify({
            'status': 'ok',
            'device_id': device_id,
            'scanning_enabled': get_device_scan_enabled(data, device_id)
        })

    try:
        payload = request.get_json(force=True) or {}
    except Exception:
        return jsonify({'status': 'error', 'message': 'invalid json'}), 400

    if 'scanning_enabled' not in payload:
        return jsonify({'status': 'error', 'message': 'scanning_enabled is required'}), 400

    enabled = bool(payload.get('scanning_enabled'))
    set_device_scan_enabled(data, device_id, enabled)
    save_data(data)

    return jsonify({
        'status': 'ok',
        'device_id': device_id,
        'scanning_enabled': enabled
    })


@app.route('/reports')
def reports():
    reports = [{'name': 'Demo Report', 'path': '/report', 'generated_at': '2026-02-26T04:36:00Z'}]
    return render_template('reports.html', reports=reports)


@app.route('/upload-scan', methods=['POST'])
def upload_scan():
    # accept hydrogel image upload, run hydrogel_cv scan + plaque feedback, save record
    f = request.files.get('image')
    if not f or getattr(f, 'filename', '') == '':
        return redirect(url_for('hydrogel_page'))
    try:
        process_hydrogel_upload_file(f)
    except Exception as e:
        return jsonify({'status': 'error', 'message': 'failed to process hydrogel image', 'error': str(e)}), 500
    return redirect(url_for('hydrogel_page'))


@app.route('/api/upload-scan', methods=['POST'])
def api_upload_scan():
    # same as upload_scan but returns JSON for AJAX clients
    f = request.files.get('image')
    if not f or getattr(f, 'filename', '') == '':
        return jsonify({'status': 'error', 'message': 'no image provided'}), 400
    try:
        record = process_hydrogel_upload_file(f)
    except Exception:
        return jsonify({'status': 'error', 'message': 'failed to process image'}), 500
    # Award XP for submitting a photo scan
    try:
        data = load_data()
        rewards = data.get('rewards', {'xp': 0, 'badges': []})
        # award 10 XP for a photo submission
        rewards['xp'] = rewards.get('xp', 0) + 10
        # count photo submissions and award badge if milestone
        photo_count = sum(1 for s in data.get('scans', []) if s.get('source_type') in ('image', 'hydrogel_image'))
        if photo_count >= 5 and 'photo_master' not in rewards.get('badges', []):
            rewards.setdefault('badges', []).append('photo_master')
        data['rewards'] = rewards
        save_data(data)
        try:
            broadcast_event('rewards', rewards)
        except Exception:
            pass
    except Exception:
        pass

    return jsonify({'status': 'ok', 'record': record, 'earned_xp': 10})


@app.route('/api/profile', methods=['GET', 'POST'])
def api_profile():
    data = load_data()
    if request.method == 'GET':
        return jsonify({'status': 'ok', 'profile': data.get('profile', {})})
    # POST: accept JSON payload to update profile
    try:
        payload = request.get_json(force=True)
    except Exception:
        return jsonify({'status': 'error', 'message': 'invalid json'}), 400
    profile = data.get('profile', {})
    profile.update(payload or {})
    data['profile'] = profile
    save_data(data)
    try:
        broadcast_event('profile', profile)
    except Exception:
        pass
    return jsonify({'status': 'ok', 'profile': profile})


@app.route('/api/rewards', methods=['GET', 'POST'])
def api_rewards():
    data = load_data()
    if request.method == 'GET':
        # include computed streak and market items in API response
        scans = data.get('scans', [])
        import datetime as _dt
        dates = sorted({_dt.datetime.fromisoformat(s['timestamp'].replace('Z','')).date() for s in scans}) if scans else []
        streak = 0
        if dates:
            cur = dates[-1]
            while cur in dates:
                streak += 1
                cur = cur - _dt.timedelta(days=1)
        market_items = get_market_items()
        earn_actions = get_earn_actions()
        resp = {'status': 'ok', 'rewards': data.get('rewards', {}), 'streak': streak, 'market_items': market_items, 'earn_actions': earn_actions}
        return jsonify(resp)
    try:
        payload = request.get_json(force=True) or {}
    except Exception:
        return jsonify({'status': 'error', 'message': 'invalid json'}), 400
    action = payload.get('action')
    action_result = {'ok': True}
    rewards = data.get('rewards', {'xp': 0, 'badges': [], 'purchases': []})
    if action == 'redeem':
        badge = payload.get('badge')
        if badge:
            if badge not in rewards.get('badges', []):
                rewards.setdefault('badges', []).append(badge)
                rewards['xp'] = rewards.get('xp', 0) + int(payload.get('xp_delta', 20))
                data['rewards'] = rewards
                save_data(data)
                try:
                    broadcast_event('rewards', rewards)
                except Exception:
                    pass
    elif action == 'earn':
        etype = payload.get('type')
        earn_actions = get_earn_actions()
        config = earn_actions.get(str(etype) if etype is not None else '')
        if not config:
            action_result = {'ok': False, 'message': 'invalid earn action'}
        else:
            xp = int(config.get('xp', 0))
            once_per_day = bool(config.get('once_per_day'))
            if once_per_day:
                from datetime import datetime
                today = datetime.utcnow().date().isoformat()
                daily_log = rewards.setdefault('daily_earn_log', {})
                last_date = daily_log.get(etype)
                if last_date == today:
                    action_result = {'ok': False, 'message': f'{etype} already claimed today'}
                else:
                    rewards['xp'] = rewards.get('xp', 0) + xp
                    daily_log[etype] = today
                    data['rewards'] = rewards
                    save_data(data)
                    try:
                        broadcast_event('rewards', rewards)
                    except Exception:
                        pass
                    action_result = {'ok': True, 'message': f'earned {xp} xp', 'xp': xp, 'type': etype}
            else:
                rewards['xp'] = rewards.get('xp', 0) + xp
                data['rewards'] = rewards
                save_data(data)
                try:
                    broadcast_event('rewards', rewards)
                except Exception:
                    pass
                action_result = {'ok': True, 'message': f'earned {xp} xp', 'xp': xp, 'type': etype}
    elif action == 'purchase':
        raw_item = payload.get('item_id')
        item_id = str(raw_item) if raw_item is not None else None
        market = {item['id']: item['cost'] for item in get_market_items()}
        if item_id is not None:
            cost = market.get(item_id)
            if not cost:
                action_result = {'ok': False, 'message': 'invalid item'}
            elif item_id in rewards.get('purchases', []):
                action_result = {'ok': False, 'message': 'item already owned', 'item_id': item_id}
            elif rewards.get('xp', 0) < cost:
                action_result = {'ok': False, 'message': 'not enough xp', 'required_xp': cost, 'current_xp': rewards.get('xp', 0)}
            else:
                rewards['xp'] = rewards.get('xp',0) - cost
                rewards.setdefault('purchases', []).append(item_id)
                data['rewards'] = rewards
                save_data(data)
                try:
                    broadcast_event('rewards', rewards)
                except Exception:
                    pass
                action_result = {'ok': True, 'message': 'purchase successful', 'item_id': item_id, 'cost': cost}
        else:
            action_result = {'ok': False, 'message': 'item_id is required'}
    return jsonify({'status': 'ok', 'rewards': data.get('rewards', {}), 'result': action_result})


@app.route('/test-ingest', methods=['POST'])
def test_ingest():
    device_id = request.form.get('device_id')
    # parse pH safely (may be missing or non-numeric)
    pH_raw = request.form.get('pH')
    try:
        pH = float(pH_raw) if pH_raw is not None and pH_raw != '' else None
    except Exception:
        pH = None
    payload = {
        'device_id': device_id,
        'ts': datetime.utcnow().isoformat() + 'Z',
        'pH': pH,
        'temperature_c': 36.5,
        'battery': 90,
        'seq': 999,
        'crc': 'test'
    }
    try:
        resp = requests.post(INGEST_URL, json=payload, timeout=5)
        ingest_resp = resp.json()
    except Exception as e:
        ingest_resp = {'error': str(e)}

    # determine estimated pH (prefer ingest response, fall back to submitted pH)
    estimated_pH = None
    if isinstance(ingest_resp, dict):
        # ingest may return {'record': {...}} or {'data': {...}} or a flat dict
        rec = ingest_resp.get('record') or ingest_resp.get('data') or ingest_resp
        if isinstance(rec, dict):
            # prefer these keys in order
            for key in ('pH_smoothed', 'estimated_pH', 'pH'):
                if key in rec and rec[key] is not None:
                    try:
                        estimated_pH = float(rec[key])
                        break
                    except Exception:
                        continue
    if estimated_pH is None:
        estimated_pH = pH if pH is not None else 6.5

    # convert ingest response to a local scan record and save
    record = {
        'timestamp': payload['ts'],
        'source_type': 'sensor',
        'device_id': device_id,
        'pH': pH,
        'estimated_pH': estimated_pH,
        'ingest_response': ingest_resp
    }
    add_scan_record(record)
    return redirect(url_for('index'))


def _ph_from_label(label):
    value = str(label or '').strip().lower()
    if value == 'low ph':
        return 5.4
    if value == 'neutral ph':
        return 7.0
    if value == 'high ph':
        return 7.6
    return None


@app.route('/api/device-ingest', methods=['POST'])
def api_device_ingest():
    if DEVICE_INGEST_KEY:
        client_key = request.headers.get('X-Device-Key', '')
        if client_key != DEVICE_INGEST_KEY:
            return jsonify({'status': 'error', 'message': 'unauthorized'}), 401

    try:
        payload = request.get_json(force=True) or {}
    except Exception:
        return jsonify({'status': 'error', 'message': 'invalid json'}), 400

    device_id = str(payload.get('device_id') or 'uno-r4-wifi').strip()
    data = load_data()
    if not get_device_scan_enabled(data, device_id):
        return jsonify({'status': 'paused', 'message': 'scanning is paused for this device'}), 409

    label = str(payload.get('classification') or payload.get('label') or '').strip()

    p_h_raw = payload.get('pH', payload.get('ph'))
    p_h = None
    try:
        if p_h_raw is not None:
            p_h = float(p_h_raw)
    except Exception:
        p_h = None
    if p_h is None:
        p_h = _ph_from_label(label)
    if p_h is None:
        return jsonify({'status': 'error', 'message': 'missing pH (or unrecognized classification label)'}), 400

    ts = payload.get('ts') or (datetime.utcnow().isoformat() + 'Z')
    r_raw = payload.get('r_hz')
    g_raw = payload.get('g_hz')
    b_raw = payload.get('b_hz')
    try:
        r_hz = float(r_raw) if r_raw is not None else None
    except Exception:
        r_hz = None
    try:
        g_hz = float(g_raw) if g_raw is not None else None
    except Exception:
        g_hz = None
    try:
        b_hz = float(b_raw) if b_raw is not None else None
    except Exception:
        b_hz = None

    record = {
        'timestamp': ts,
        'source_type': 'sensor_wifi',
        'device_id': device_id,
        'pH': p_h,
        'estimated_pH': p_h,
        'classification': label or None,
        'r_hz': r_hz,
        'g_hz': g_hz,
        'b_hz': b_hz,
        'out_state': payload.get('out_state'),
        'seq': payload.get('seq'),
        'battery': payload.get('battery')
    }
    add_scan_record(record)
    try:
        broadcast_event('scan', record)
    except Exception:
        pass

    return jsonify({'status': 'ok', 'record': record})


@app.route('/report')
def report():
    pdf = os.path.join(OUTPUTS_DIR, 'report_demo.pdf')
    if os.path.exists(pdf):
        return send_file(pdf)
    return 'No report generated yet', 404


@app.route('/add-scan', methods=['POST'])
def add_scan():
    data = load_data()
    payload = request.get_json(force=True)
    record = payload
    if 'timestamp' not in record:
        record['timestamp'] = datetime.utcnow().isoformat() + 'Z'
    add_scan_record(record)
    return {'status': 'ok'}


if __name__ == '__main__':
    port = int(os.environ.get('PORT', '8000'))
    app.run(host='0.0.0.0', port=port)
