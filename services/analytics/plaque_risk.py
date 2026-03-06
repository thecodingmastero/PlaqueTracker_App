"""Compute a Plaque Risk Index from a window of pH readings.

This is a simple, explainable prototype combining mean pH, spike count, and time-in-range.
"""
from datetime import datetime, timedelta


def plaque_risk_index(readings):
    """readings: list of dicts with keys `timestamp` (ISO str) and `pH` (float)
    returns a float index 0..1
    """
    if not readings:
        return 0.0
    phs = [r['pH'] for r in readings]
    mean_ph = sum(phs) / len(phs)
    spikes = sum(1 for p in phs if p < 5.5)
    recent = readings[-10:]
    recent_mean = sum(r['pH'] for r in recent) / len(recent)

    # normalize
    mean_score = max(0.0, (7.0 - mean_ph) / 4.0)
    spike_score = min(1.0, spikes / max(1, len(phs)) )
    recent_score = max(0.0, (6.8 - recent_mean) / 4.0)

    # weighted sum
    pri = 0.5 * mean_score + 0.3 * spike_score + 0.2 * recent_score
    return round(min(max(pri, 0.0), 1.0), 3)


if __name__ == '__main__':
    sample = [{'timestamp': '2026-01-01T00:00:00Z', 'pH': 6.8}, {'timestamp': '2026-01-01T01:00:00Z', 'pH': 5.2}]
    print('PRI=', plaque_risk_index(sample))
