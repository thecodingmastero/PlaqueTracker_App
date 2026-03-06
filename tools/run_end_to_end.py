"""End-to-end demo orchestration:
- generate synthetic hydrogel image
- train demo models
- run hydrogel scan to estimate pH
- assemble simulated sensor readings and compute Plaque Risk Index
- generate a PDF report
- evaluate rewards
"""
import sys
import os
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from hydrogel_cv.generate_sample_image import generate as gen_image
from hydrogel_cv import model_train as cv_model_train
from hydrogel_cv.scan import run as scan_run
from services.analytics import train_model as analytics_train
from services.analytics.plaque_risk import plaque_risk_index
from services.reporting.generate_report import generate_simple_pdf
from services.rewards.rewards import evaluate_rewards
import os
from datetime import datetime, timedelta


OUT_DIR = 'outputs'
os.makedirs(OUT_DIR, exist_ok=True)


def make_sensor_series(estimated_pH, count=20):
    now = datetime.utcnow()
    readings = []
    for i in range(count):
        ts = (now - timedelta(minutes=(count - i) * 15)).isoformat() + 'Z'
        # synthetic variation around estimated pH
        p = float(max(3.0, min(8.0, estimated_pH + (i - count/2) * 0.05)))
        readings.append({'timestamp': ts, 'pH': round(p, 2)})
    return readings


def main():
    sample_img = os.path.join('hydrogel_cv', 'sample_scan.jpg')
    gen_image(sample_img, 4.8)

    # (re)train models
    cv_model_train.main('hydrogel_cv/model.pkl')
    analytics_train.train('services/analytics/ph_model.joblib', 'services/analytics/plaque_model.joblib')

    # run scan
    scan_res = scan_run(sample_img, 'hydrogel_cv/model.pkl', roi_size=120,
                       out_json=os.path.join(OUT_DIR, 'scan_result.json'))
    est_pH = float(scan_res['estimated_pH'])

    # build sensor series and compute PRI
    readings = make_sensor_series(est_pH, count=30)
    pri = plaque_risk_index(readings)

    # create report
    summary = {'estimated_pH': est_pH, 'plaque_risk_index': pri, 'acid_spikes': sum(1 for r in readings if r['pH'] < 5.5)}
    pdf_path = os.path.join(OUT_DIR, 'report_demo.pdf')
    generate_simple_pdf(pdf_path, summary)

    # evaluate rewards
    user_state = {'badges': [], 'current_streak': 5}
    analytics_ctx = {'improved': True, 'acid_spikes_reduced': True}
    rewards = evaluate_rewards(user_state, analytics_ctx)

    print('\n=== END-TO-END SUMMARY ===')
    print('scan_result:', scan_res)
    print('pri:', pri)
    print('report:', pdf_path)
    print('rewards:', rewards)


if __name__ == '__main__':
    main()
