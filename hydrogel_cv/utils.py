import numpy as np
from PIL import Image
import cv2

def load_image(path):
    img = Image.open(path).convert('RGB')
    return np.array(img)

def white_balance_grayworld(img: np.ndarray) -> np.ndarray:
    img = img.astype(np.float32)
    avgR = np.mean(img[:, :, 0])
    avgG = np.mean(img[:, :, 1])
    avgB = np.mean(img[:, :, 2])
    avg = (avgR + avgG + avgB) / 3.0
    img[:, :, 0] = np.clip((img[:, :, 0] * (avg / avgR)), 0, 255)
    img[:, :, 1] = np.clip((img[:, :, 1] * (avg / avgG)), 0, 255)
    img[:, :, 2] = np.clip((img[:, :, 2] * (avg / avgB)), 0, 255)
    return img.astype(np.uint8)

def crop_center_square(img: np.ndarray, size: int = 100) -> np.ndarray:
    h, w = img.shape[:2]
    cx, cy = w // 2, h // 2
    half = size // 2
    x1 = max(0, cx - half)
    y1 = max(0, cy - half)
    x2 = min(w, cx + half)
    y2 = min(h, cy + half)
    return img[y1:y2, x1:x2]

def mean_rgb(img: np.ndarray) -> np.ndarray:
    roi = img.reshape(-1, 3)
    mean = np.mean(roi, axis=0)
    return mean

def rgb_to_lab(rgb: np.ndarray) -> np.ndarray:
    rgb = rgb.reshape(1, 1, 3).astype(np.uint8)
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)
    return lab.reshape(3)
