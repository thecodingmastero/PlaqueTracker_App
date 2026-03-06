"""Generate a synthetic hydrogel scan image corresponding to a target pH.

Usage:
  python generate_sample_image.py --pH 4.5 --out sample_scan.jpg
"""
import argparse
from PIL import Image, ImageDraw
import numpy as np


def synth_rgb_from_pH(pH: float):
    t = (pH - 3.0) / (8.0 - 3.0)
    r = 200 - 120 * t
    g = 120 + 110 * t
    b = 80 + 100 * t
    return [int(max(0, min(255, r))), int(max(0, min(255, g))), int(max(0, min(255, b)))]


def generate(out_path: str, pH: float, size=400):
    bg = (230, 230, 230)
    img = Image.new('RGB', (size, size), bg)
    draw = ImageDraw.Draw(img)
    center = (size // 2, size // 2)
    radius = size // 3
    rgb = tuple(synth_rgb_from_pH(pH))
    # draw colored circle to simulate hydrogel patch
    for r in range(radius, 0, -1):
        factor = 1 - (r / radius) * 0.2
        fill = tuple(int(max(0, min(255, c * factor + bg[i] * (1 - factor)))) for i, c in enumerate(rgb))
        draw.ellipse([center[0]-r, center[1]-r, center[0]+r, center[1]+r], fill=fill)
    img.save(out_path)
    print(f"Wrote sample image to {out_path} (pH={pH})")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--pH', type=float, default=6.5)
    parser.add_argument('--out', default='sample_scan.jpg')
    args = parser.parse_args()
    generate(args.out, args.pH)
