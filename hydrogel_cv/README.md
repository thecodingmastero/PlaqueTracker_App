# Hydrogel CV Prototype

This small prototype demonstrates hydrogel scan image processing and a simple color-to-pH regression model.

Quickstart

1. Create and activate a Python 3.9+ virtualenv.

```bash
python -m venv .venv
source .venv/bin/activate   # on Windows: .venv\Scripts\activate
pip install -r hydrogel_cv/requirements.txt
```

2. Train a demo model (generates `model.pkl`):

```bash
python hydrogel_cv/model_train.py --out model.pkl
```

3. Run the scanner on an image:

```bash
python hydrogel_cv/scan.py --image path/to/scan.jpg --model model.pkl
```

Files

- `scan.py`: main inference script — performs white-balance, ROI extraction, color-to-pH mapping, and emits JSON metadata.
- `model_train.py`: trains a synthetic regression model (demo) and writes `model.pkl`.
- `utils.py`: helper image processing functions.
- `requirements.txt`: Python dependencies.

Notes

- This is a prototype for local experimentation. Replace synthetic training with a real calibrated dataset and integrate device metadata and uploads in production.
