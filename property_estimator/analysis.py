"""
Phase 2 property estimator: color-based segmentation and blob detection.
Uses OpenCV for grass, pavement, mulch detection and tree/bush counting.
"""
import io
import base64
from decimal import Decimal

try:
    import cv2
    import numpy as np
    HAS_OPENCV = True
except ImportError:
    HAS_OPENCV = False


def enhance_image(image_path):
    """Basic enhancement: contrast, sharpening. Returns enhanced image as numpy array."""
    if not HAS_OPENCV:
        return None
    img = cv2.imread(str(image_path))
    if img is None:
        return None
    # CLAHE for contrast
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l = clahe.apply(l)
    lab = cv2.merge([l, a, b])
    enhanced = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
    # Slight sharpening
    kernel = np.array([[-0.5, -0.5, -0.5], [-0.5, 5, -0.5], [-0.5, -0.5, -0.5]])
    enhanced = cv2.filter2D(enhanced, -1, kernel)
    return enhanced


def segment_property(img_array):
    """
    Color-based segmentation. Returns masks and pixel counts.
    Uses HSV for better color range matching.
    """
    if not HAS_OPENCV or img_array is None:
        return {}
    hsv = cv2.cvtColor(img_array, cv2.COLOR_BGR2HSV)
    total_pixels = img_array.shape[0] * img_array.shape[1]

    # Grass: green hues (typically H 35-85, S and V vary)
    lower_grass = np.array([25, 40, 40])
    upper_grass = np.array([95, 255, 255])
    grass_mask = cv2.inRange(hsv, lower_grass, upper_grass)
    grass_pixels = int(np.sum(grass_mask > 0))

    # Pavement: gray/neutral (low saturation)
    lower_pavement_sat = np.array([0, 0, 50])
    upper_pavement_sat = np.array([180, 60, 200])
    pavement_mask = cv2.inRange(hsv, lower_pavement_sat, upper_pavement_sat)
    pavement_pixels = int(np.sum(pavement_mask > 0))

    # Mulch: brown (low H, medium S, low V) - brown is orange-ish in HSV
    lower_mulch = np.array([5, 30, 20])
    upper_mulch = np.array([25, 200, 150])
    mulch_mask = cv2.inRange(hsv, lower_mulch, upper_mulch)
    mulch_pixels = int(np.sum(mulch_mask > 0))

    # Tree/bush detection: circular green blobs - use morphology and contour filtering
    green_mask = grass_mask  # trees/bushes are often darker green
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    green_closed = cv2.morphologyEx(green_mask, cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(green_closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    tree_count = 0
    bush_count = 0
    min_tree_area = total_pixels * 0.002  # ~0.2% of image
    max_tree_area = total_pixels * 0.15   # ~15%
    min_bush_area = total_pixels * 0.0003  # smaller
    max_bush_area = total_pixels * 0.02

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if min_tree_area <= area <= max_tree_area:
            # Check circularity
            peri = cv2.arcLength(cnt, True)
            if peri > 0:
                circularity = 4 * np.pi * area / (peri * peri)
                if circularity > 0.5:
                    tree_count += 1
        elif min_bush_area <= area <= max_bush_area:
            bush_count += 1

    return {
        'grass_pixels': grass_pixels,
        'pavement_pixels': pavement_pixels,
        'mulch_pixels': mulch_pixels,
        'tree_count': tree_count,
        'bush_count': bush_count,
        'total_pixels': total_pixels,
        'grass_mask': grass_mask,
        'pavement_mask': pavement_mask,
        'mulch_mask': mulch_mask,
    }


def build_overlay_image(img_array, result):
    """Create RGB overlay: grass=green, pavement=gray, mulch=brown (semi-transparent)."""
    if not HAS_OPENCV or img_array is None or not result:
        return None
    overlay = img_array.copy()
    # Blue channel = pavement, Green = grass, Red = mulch (BGR)
    overlay[result['grass_mask'] > 0] = [0, 180, 0]      # grass = green
    overlay[result['pavement_mask'] > 0] = [120, 120, 120]  # pavement = gray
    overlay[result['mulch_mask'] > 0] = [40, 80, 140]    # mulch = brown-ish
    blended = cv2.addWeighted(img_array, 0.6, overlay, 0.4, 0)
    return blended


def numpy_to_png(arr):
    """Convert BGR numpy array to PNG bytes."""
    if not HAS_OPENCV or arr is None:
        return None
    ok, buf = cv2.imencode('.png', arr)
    return buf.tobytes() if ok else None


def analyze_image(image_path, total_area_sqft=None, enhance=True):
    """
    Full analysis pipeline. Returns dict with pixel counts, sqft (if scale provided), and overlay image bytes.
    """
    if not HAS_OPENCV:
        return {'error': 'OpenCV not installed', 'grass_pixels': 0, 'pavement_pixels': 0, 'mulch_pixels': 0, 'tree_count': 0, 'bush_count': 0}

    img = cv2.imread(str(image_path))
    if img is None:
        return {'error': 'Could not load image', 'grass_pixels': 0, 'pavement_pixels': 0, 'mulch_pixels': 0, 'tree_count': 0, 'bush_count': 0}

    if enhance:
        img = enhance_image(image_path)
        if img is None:
            img = cv2.imread(str(image_path))

    result = segment_property(img)
    if not result:
        return {'error': 'Segmentation failed', 'grass_pixels': 0, 'pavement_pixels': 0, 'mulch_pixels': 0, 'tree_count': 0, 'bush_count': 0}

    total = result['total_pixels']
    pixel_scale = None
    if total_area_sqft and total > 0:
        pixel_scale = float(total_area_sqft) / total
        result['grass_sqft'] = round(result['grass_pixels'] * pixel_scale, 2)
        result['pavement_sqft'] = round(result['pavement_pixels'] * pixel_scale, 2)
        result['mulch_sqft'] = round(result['mulch_pixels'] * pixel_scale, 2)
    else:
        result['grass_sqft'] = None
        result['pavement_sqft'] = None
        result['mulch_sqft'] = None

    overlay = build_overlay_image(img, result)
    if overlay is not None:
        result['overlay_png'] = numpy_to_png(overlay)
    result['enhanced_png'] = numpy_to_png(img) if enhance else None
    result['pixel_scale'] = pixel_scale
    return result
