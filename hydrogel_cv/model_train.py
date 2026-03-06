"""Train a small synthetic color->pH regression model for demo purposes."""
import argparse
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from joblib import dump


def synth_rgb_from_pH(pH: float):
    # Synthetic mapping: lower pH -> more red/yellow; higher pH -> greener/bluer
    # This is a toy mapping for demo only.
    t = (pH - 3.0) / (8.0 - 3.0)
    r = 200 - 120 * t + np.random.randn() * 3
    g = 120 + 110 * t + np.random.randn() * 3
    b = 80 + 100 * t + np.random.randn() * 3
    return [np.clip(r, 0, 255), np.clip(g, 0, 255), np.clip(b, 0, 255)]


def main(out_path: str):
    xs = []
    ys = []
    for pH in np.linspace(3.0, 8.0, 200):
        for _ in range(5):
            rgb = synth_rgb_from_pH(pH)
            xs.append(rgb)
            ys.append(pH + np.random.randn() * 0.05)

    X = np.array(xs)
    y = np.array(ys)

    model = RandomForestRegressor(n_estimators=50, random_state=42)
    model.fit(X, y)
    dump(model, out_path)
    print(f"Trained demo model saved to {out_path}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', default='model.pkl')
    args = parser.parse_args()
    main(args.out)
