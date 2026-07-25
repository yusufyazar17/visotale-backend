"""
Fotoğraf hazırlama: illusion-diffusion'a giden "conditioning" görselini üretir.

Adımlar (test sürecinde elle onaylanan Photoshop akışının otomatik hâli):
  1. OpenCV Haar cascade ile yüz(ler)i bul — tek kişi ya da çift/grup fark etmez.
  2. Tüm yüzleri kapsayan, biraz paylı bir kare kırpım hesapla.
  3. Gri tonlamaya çevir.
  4. Autocontrast + hafif kontrast artışı uygula (orta tonları koru — aşırı
     siyah/beyaza düşürme, yoksa illüzyon dokusu kaybolur).
  5. 1024×1024'e getir.

Yüz bulunamazsa (evcil hayvan, manzara, soyut obje vb.) merkezi kare kırpıma
düşer — bu bir hata değil, güvenli bir yedektir.
"""

import io
import cv2
import numpy as np
from PIL import Image, ImageOps, ImageEnhance

FACE_CASCADE = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)

CONDITIONING_SIZE = 1024


def _detect_faces(cv_img_gray):
    faces = FACE_CASCADE.detectMultiScale(cv_img_gray, 1.08, 5, minSize=(40, 40))
    return faces


def _bbox_from_faces(faces, img_w, img_h):
    xs = [x for (x, y, w, h) in faces]
    ys = [y for (x, y, w, h) in faces]
    xe = [x + w for (x, y, w, h) in faces]
    ye = [y + h for (x, y, w, h) in faces]
    x0, y0, x1, y1 = min(xs), min(ys), max(xe), max(ye)

    # yüzlerin etrafına pay bırak (saç, çene, omuz için)
    pad_x = int((x1 - x0) * 0.6)
    pad_y_top = int((y1 - y0) * 0.6)
    pad_y_bottom = int((y1 - y0) * 0.8)
    x0 -= pad_x
    x1 += pad_x
    y0 -= pad_y_top
    y1 += pad_y_bottom

    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    side = int(max(x1 - x0, y1 - y0) * 1.05)
    x0, y0 = cx - side // 2, cy - side // 2
    x1, y1 = x0 + side, y0 + side

    # sınırlar içinde tut
    x0 = max(0, x0)
    y0 = max(0, y0)
    x1 = min(img_w, x1)
    y1 = min(img_h, y1)
    return x0, y0, x1, y1


def prepare_conditioning_image(raw_bytes: bytes) -> Image.Image:
    """raw_bytes -> 1024x1024 gri/yüksek-kontrast conditioning görseli (PIL Image, RGB)."""
    img = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
    W, H = img.size

    cv_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    gray_cv = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    faces = _detect_faces(gray_cv)

    if len(faces) > 0:
        x0, y0, x1, y1 = _bbox_from_faces(faces, W, H)
    else:
        # yedek: merkezi kare (hafifçe üstten, portre eğilimine uygun)
        side = int(min(W, H) * 0.9)
        x0 = (W - side) // 2
        y0 = int(H * 0.05)
        x1, y1 = x0 + side, y0 + side
        x0, y0 = max(0, x0), max(0, y0)
        x1, y1 = min(W, x1), min(H, y1)

    crop = img.crop((x0, y0, x1, y1))
    side = min(crop.size)
    crop = ImageOps.fit(crop, (side, side), centering=(0.5, 0.45))

    gwork = ImageOps.grayscale(crop)
    gwork = ImageOps.autocontrast(gwork, cutoff=1)
    gwork = ImageEnhance.Contrast(gwork).enhance(1.35)
    gwork = gwork.resize((CONDITIONING_SIZE, CONDITIONING_SIZE), Image.LANCZOS)

    return gwork.convert("RGB")


def to_data_uri(img: Image.Image, fmt: str = "JPEG", quality: int = 92) -> str:
    import base64

    buf = io.BytesIO()
    img.save(buf, format=fmt, quality=quality)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    mime = "image/jpeg" if fmt.upper() == "JPEG" else f"image/{fmt.lower()}"
    return f"data:{mime};base64,{b64}"
