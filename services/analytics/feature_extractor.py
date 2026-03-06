"""Simple analytics feature extractor for pH time series.

This script reads a CSV with timestamp,pH and emits basic features: mean, std, acid_spike_count.
"""
import argparse
import csv
from datetime import datetime, timedelta


def parse_rows(path):
    rows = []
    with open(path, 'r') as f:
        reader = csv.DictReader(f)
        for r in reader:
            ts = datetime.fromisoformat(r['timestamp'])
            ph = float(r['pH'])
            rows.append((ts, ph))
    rows.sort()
    return rows


def extract_features(rows, spike_threshold=5.5):
    phs = [p for _, p in rows]
    mean = sum(phs) / len(phs) if phs else None
    std = (sum((p - mean) ** 2 for p in phs) / len(phs)) ** 0.5 if phs else None
    spikes = sum(1 for p in phs if p < spike_threshold)
    return {'count': len(phs), 'mean_pH': mean, 'std_pH': std, 'acid_spikes': spikes}


def main(path):
    rows = parse_rows(path)
    feats = extract_features(rows)
    print(feats)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('csv')
    args = parser.parse_args()
    main(args.csv)
