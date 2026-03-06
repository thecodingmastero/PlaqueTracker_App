"""Train a demo ML model for Plaque Risk and pH mapping.

This is a prototype script producing a model artifact and a simple plaque-risk mapping.
"""
import argparse
import numpy as np
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from joblib import dump


def synth_training_data(n=500):
    X_reg = []
    y_reg = []
    X_clf = []
    y_clf = []
    for _ in range(n):
        # synthetic rgb features
        r = np.random.normal(150, 30)
        g = np.random.normal(120, 25)
        b = np.random.normal(90, 20)
        X_reg.append([r, g, b])
        # map to synthetic pH
        pH = 3.0 + (g - 80) / 40.0 + np.random.randn() * 0.1
        y_reg.append(pH)

        # plaque risk label (binary) from pH/time noise
        risk = 1 if pH < 5.5 else 0
        X_clf.append([r, g, b, pH])
        y_clf.append(risk)

    return np.array(X_reg), np.array(y_reg), np.array(X_clf), np.array(y_clf)


def train(out_reg='ph_model.joblib', out_clf='plaque_model.joblib'):
    X_reg, y_reg, X_clf, y_clf = synth_training_data()
    reg = RandomForestRegressor(n_estimators=100, random_state=42)
    reg.fit(X_reg, y_reg)
    dump(reg, out_reg)
    clf = RandomForestClassifier(n_estimators=100, random_state=42)
    clf.fit(X_clf, y_clf)
    dump(clf, out_clf)
    print('Saved', out_reg, out_clf)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out-reg', default='ph_model.joblib')
    parser.add_argument('--out-clf', default='plaque_model.joblib')
    args = parser.parse_args()
    train(args.out_reg, args.out_clf)
