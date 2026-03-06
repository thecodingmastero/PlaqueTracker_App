"""Hydrogel scan processing and color-to-pH estimation.

Usage:
  python scan.py --image PATH --model model.pkl
"""
import argparse
import json
import os
from datetime import datetime
import numpy as np
from joblib import load
from hydrogel_cv.utils import load_image, white_balance_grayworld, crop_center_square, mean_rgb, rgb_to_lab


def estimate_pH_from_rgb(rgb, model):
    rgb = np.array(rgb).reshape(1, -1)
    try:
        pH = float(model.predict(rgb)[0])
        confidence = 0.85
    except Exception:
        pH = float(6.5)
        confidence = 0.3
    return pH, confidence


def run(image_path, model_path, roi_size=120, out_json=None):
    img = load_image(image_path)
    wb = white_balance_grayworld(img)
    roi = crop_center_square(wb, size=roi_size)
    mean = mean_rgb(roi)
    lab = rgb_to_lab(mean)

    model = None
    if os.path.exists(model_path):
        model = load(model_path)

    pH, confidence = estimate_pH_from_rgb(mean, model) if model is not None else (6.5, 0.3)

    result = {
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'source_type': 'image',
        'estimated_pH': round(float(pH), 2),
        'confidence': round(float(confidence), 3),
        'model_version': os.path.basename(model_path) if model is not None else None,
        'processing_metadata': {
            'white_balance': 'grayworld',
            'roi_size': roi_size,
            'mean_rgb': [float(round(x, 2)) for x in mean.tolist()],
            'mean_lab': [float(round(x, 2)) for x in lab.tolist()]
        }
    }

    out = out_json or (os.path.splitext(image_path)[0] + '.hydrogel.json')
    with open(out, 'w') as f:
        json.dump(result, f, indent=2)

    print(json.dumps(result, indent=2))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--image', required=True)
    parser.add_argument('--model', default='model.pkl')
    parser.add_argument('--roi', type=int, default=120)
    parser.add_argument('--out', default=None)
    args = parser.parse_args()
    run(args.image, args.model, roi_size=args.roi, out_json=args.out)
