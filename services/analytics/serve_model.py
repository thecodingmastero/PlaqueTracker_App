from flask import Flask, request, jsonify
from joblib import load
import os

app = Flask(__name__)

PH_MODEL = os.environ.get('PH_MODEL', 'ph_model.joblib')
PRI_MODEL = os.environ.get('PRI_MODEL', 'plaque_model.joblib')

ph_model = None
pri_model = None

def ensure_models():
    global ph_model, pri_model
    if ph_model is None and os.path.exists(PH_MODEL):
        ph_model = load(PH_MODEL)
    if pri_model is None and os.path.exists(PRI_MODEL):
        pri_model = load(PRI_MODEL)


@app.route('/v1/predict_ph', methods=['POST'])
def predict_ph():
    data = request.get_json(force=True)
    rgb = data.get('rgb')
    ensure_models()
    if ph_model is None:
        return jsonify({'error': 'model not found'}), 500
    p = float(ph_model.predict([rgb])[0])
    return jsonify({'pH': round(p, 3)})


@app.route('/v1/predict_pri', methods=['POST'])
def predict_pri():
    data = request.get_json(force=True)
    features = data.get('features')
    ensure_models()
    if pri_model is None:
        return jsonify({'error': 'model not found'}), 500
    pred = int(pri_model.predict([features])[0])
    return jsonify({'plaque_risk_binary': pred})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=9090)
