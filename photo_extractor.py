"""
Photo extraction from CNIC / DL images using face detection.
Only depends on OpenCV — no OCR or SLM required.
"""
import base64
import os
import tempfile
import cv2


def extract_photo(image_path: str, output_path: str = None):
    if output_path is None:
        output_path = os.path.join(tempfile.gettempdir(), "extracted_photo.png")
    img = cv2.imread(image_path)
    if img is None:
        return None, None

    gray    = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    faces = cascade.detectMultiScale(gray, scaleFactor=1.1,
                                     minNeighbors=5, minSize=(50, 50))

    if len(faces) > 0:
        x, y, w, h = max(faces, key=lambda r: r[2] * r[3])
        mx, my  = w // 2, h // 2
        x       = max(0, x - mx);   y = max(0, y - my)
        w       = min(img.shape[1] - x, w + 2 * mx)
        h       = min(img.shape[0] - y, h + 2 * my)
        cropped = img[y:y + h, x:x + w]
    else:
        ih, iw  = img.shape[:2]
        cropped = img[int(ih * 0.05):int(ih * 0.40),
                      int(iw * 0.60):int(iw * 0.95)]

    ch, cw = cropped.shape[:2]
    if max(ch, cw) > 400:
        scale   = 400 / max(ch, cw)
        cropped = cv2.resize(cropped, (int(cw * scale), int(ch * scale)),
                             interpolation=cv2.INTER_LANCZOS4)
    elif max(ch, cw) < 200:
        cropped = cv2.resize(cropped, (cw * 2, ch * 2),
                             interpolation=cv2.INTER_CUBIC)

    enhanced = cv2.convertScaleAbs(cropped, alpha=1.1, beta=0)
    cv2.imwrite(output_path, enhanced)
    with open(output_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return output_path, b64
