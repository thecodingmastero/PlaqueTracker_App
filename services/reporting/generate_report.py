from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from datetime import datetime


def generate_simple_pdf(out_path, summary: dict):
    c = canvas.Canvas(out_path, pagesize=letter)
    width, height = letter
    c.setFont('Helvetica', 12)
    c.drawString(50, height - 50, f"PlaqueTracker Report — {datetime.utcnow().date().isoformat()}")
    y = height - 80
    for k, v in summary.items():
        c.drawString(60, y, f"{k}: {v}")
        y -= 20
    c.save()


if __name__ == '__main__':
    sample = {'avg_pH': 6.5, 'acid_exposures': 3, 'plaque_risk_index': 0.42}
    generate_simple_pdf('report_demo.pdf', sample)
    print('Wrote report_demo.pdf')
