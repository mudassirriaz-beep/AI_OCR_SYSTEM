import cv2
import numpy as np
from PIL import Image, ImageOps
import math

def correct_orientation_pil(image_path):
    """
    Use PIL to read EXIF orientation and rotate image accordingly.
    Returns BGR image (numpy array).
    """
    pil_img = Image.open(image_path)
    pil_img = ImageOps.exif_transpose(pil_img)  # auto-rotate based on EXIF
    return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

def correct_orientation_contour(img):
    """
    If EXIF not present, detect document edges and rotate so that text lines are horizontal.
    Returns corrected image and angle (degrees).
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blur, 50, 150)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return img, 0
    # Find largest contour (presumably document)
    largest = max(contours, key=cv2.contourArea)
    rect = cv2.minAreaRect(largest)
    angle = rect[2]
    # Normalize angle
    if angle < -45:
        angle = 90 + angle
    # If angle is small, no need to rotate
    if abs(angle) < 1.0:
        return img, 0
    # Rotate image to correct orientation
    (h, w) = img.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    return rotated, angle

def deskew(image):
    """
    Fine deskew using Hough lines (for small angle corrections).
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    lines = cv2.HoughLines(edges, 1, np.pi/180, 100)
    angle = 0
    if lines is not None:
        angles = []
        for rho, theta in lines[:, 0]:
            ang = theta * 180 / np.pi - 90
            if abs(ang) < 45:
                angles.append(ang)
        if angles:
            median_angle = np.median(angles)
            if abs(median_angle) > 0.5:
                angle = median_angle
    if angle != 0:
        (h, w) = image.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        image = cv2.warpAffine(image, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    return image

def enhance_image(image):
    """
    Apply contrast, sharpening, adaptive threshold, morphology.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    # Denoise
    denoised = cv2.fastNlMeansDenoising(gray, None, 30, 7, 21)
    # CLAHE
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8,8))
    enhanced = clahe.apply(denoised)
    # Sharpening
    blurred = cv2.GaussianBlur(enhanced, (0, 0), 3.0)
    sharpened = cv2.addWeighted(enhanced, 1.5, blurred, -0.5, 0)
    # Adaptive threshold
    binary = cv2.adaptiveThreshold(sharpened, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 15, 2)
    # Morph closing
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    closed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=1)
    # Return as 3-channel BGR
    return cv2.cvtColor(closed, cv2.COLOR_GRAY2BGR)

def preprocess_dl(image_path):
    """
    DL-specific B&W preprocessing.

    The standard adaptive-threshold pipeline turns the wavy blue background
    into text noise, garbling the red date labels.  This pipeline converts
    to greyscale and uses a global Otsu threshold instead — the solid
    background becomes white, the text stays black.

    Also upscales 2× first so small bottom-row text (Issue Date / Valid Upto)
    is large enough for RapidOCR to read reliably.
    """
    img = correct_orientation_pil(image_path)
    img, _ = correct_orientation_contour(img)

    # 2× upscale — makes small bottom-row text readable
    h, w = img.shape[:2]
    img = cv2.resize(img, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)

    # Convert to greyscale (pure B&W — eliminates wavy colour background)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Mild denoise (keep text sharp, remove noise)
    denoised = cv2.fastNlMeansDenoising(gray, None, h=15, templateWindowSize=7, searchWindowSize=21)

    # CLAHE — local contrast boost so faint text pops
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(denoised)

    # Global Otsu threshold — background → white, text → black
    # Better than adaptive for wavy/patterned backgrounds
    _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    return cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)


def preprocess_dl_red_strip(image_path, top_ratio=0.60):
    """
    Crop the bottom portion of a DL image and enhance red text (Issue Date /
    Valid Upto labels printed in red) using the green channel, which makes
    red text appear darkest.  3× upscale so the small bottom-row text is
    large enough for RapidOCR to read reliably.
    """
    img = correct_orientation_pil(image_path)
    img, _ = correct_orientation_contour(img)
    h, w = img.shape[:2]

    # Crop bottom strip (where Issue Date + Valid Upto live)
    strip = img[int(h * top_ratio):, :]

    # 3× upscale — bottom text is very small
    strip = cv2.resize(strip, (strip.shape[1] * 3, strip.shape[0] * 3),
                       interpolation=cv2.INTER_CUBIC)

    # Green channel: red text has low green → appears dark on bright background
    green = strip[:, :, 1]

    denoised = cv2.fastNlMeansDenoising(green, None, h=12,
                                         templateWindowSize=7, searchWindowSize=21)
    clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(4, 4))
    enhanced = clahe.apply(denoised)
    _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    return cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)


def preprocess_image(image_path, use_super_res=False, sr_upsampler=None):
    """
    Full preprocessing pipeline:
    1. EXIF orientation correction (PIL)
    2. Document edge detection & rotation (if needed)
    3. Super-resolution (optional)
    4. Denoise, CLAHE, sharpening, adaptive threshold, morph closing
    5. Fine deskew
    Returns processed BGR image ready for OCR.
    """
    # Step 1: EXIF orientation
    img = correct_orientation_pil(image_path)
    
    # Step 2: Document rotation (contour-based)
    img, _ = correct_orientation_contour(img)
    
    # Step 3: Super-resolution (if available and image small)
    if use_super_res and sr_upsampler is not None:
        h, w = img.shape[:2]
        if w < 800 or h < 600:
            print("[INFO] Applying super-resolution...")
            try:
                img, _ = sr_upsampler.enhance(img, outscale=2)
                img = img.astype(np.uint8)
            except Exception as e:
                print(f"[SR] Failed: {e}")
    
    # Step 4: Basic enhancement (denoise, CLAHE, sharpening, threshold, morph)
    img = enhance_image(img)
    
    # Step 5: Fine deskew
    img = deskew(img)
    
    return img