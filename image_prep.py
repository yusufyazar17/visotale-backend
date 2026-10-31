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
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps, ImageEnhance

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


def _gray_square(raw_bytes: bytes) -> Image.Image:
    """raw_bytes -> 1024x1024 gri/yüksek-kontrast kare (PIL Image, RGB). Yüz(ler) ortada."""
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


# ---------------------------------------------------------------------------
# Yerleşim: silüet SADECE çiçek bölgesine konur, arka plan/vazo/masa sade kalır.
# ControlNet, girdideki parlaklık desenini TÜM tabloya uyguladığı için, silüeti
# yalnızca elips içine koyup dışını koyu tutmak, arka planda silüet çıkmasını önler.
# ---------------------------------------------------------------------------
LAYOUT_BOUQUET = {
    "cx": 0.50,       # elips merkezi (genişliğin oranı)
    "cy": 0.38,       # elips merkezi (yüksekliğin oranı) — buket üst 2/3'te
    "w": 0.86,        # elips genişliği
    "h": 0.66,        # elips yüksekliği
    "feather": 0.10,  # kenar yumuşatma (küçük kenarın oranı)
    "bg": 24,         # elips dışının parlaklığı (0 siyah - 255 beyaz)
    "size": 0.66,     # portre karesinin tuvale oranı (0 = elipse otomatik sığdır)
}


def _clamp(v, lo, hi, default):
    try:
        return max(lo, min(hi, float(v)))
    except (TypeError, ValueError):
        return default


def _sanitize_size(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return LAYOUT_BOUQUET["size"]
    if x <= 0:
        return 0.0  # otomatik sığdır
    return max(0.3, min(1.0, x))


def _sanitize_layout(params: dict | None) -> dict:
    p = dict(LAYOUT_BOUQUET)
    for k, v in (params or {}).items():
        if k in p:
            p[k] = v
    return {
        "cx": _clamp(p["cx"], 0.2, 0.8, LAYOUT_BOUQUET["cx"]),
        "cy": _clamp(p["cy"], 0.2, 0.8, LAYOUT_BOUQUET["cy"]),
        "w": _clamp(p["w"], 0.3, 1.0, LAYOUT_BOUQUET["w"]),
        "h": _clamp(p["h"], 0.3, 1.0, LAYOUT_BOUQUET["h"]),
        "feather": _clamp(p["feather"], 0.0, 0.4, LAYOUT_BOUQUET["feather"]),
        "bg": int(_clamp(p["bg"], 0, 120, LAYOUT_BOUQUET["bg"])),
        "size": _sanitize_size(p["size"]),
    }


def _compose_bouquet(gray_square: Image.Image, params: dict | None) -> Image.Image:
    p = _sanitize_layout(params)
    S = CONDITIONING_SIZE
    w = int(S * p["w"])
    h = int(S * p["h"])
    cx = int(S * p["cx"])
    cy = int(S * p["cy"])
    if p["size"] == 0:
        # elipse tam sığan en büyük kare: yarı kenar = 1 / sqrt(1/a^2 + 1/b^2)
        a, b = w / 2.0, h / 2.0
        side = int(2.0 / ((1.0 / a ** 2 + 1.0 / b ** 2) ** 0.5))
    else:
        side = int(S * p["size"])

    face = ImageOps.grayscale(gray_square).resize((side, side), Image.LANCZOS)

    base = Image.new("L", (S, S), p["bg"])
    layer = Image.new("L", (S, S), p["bg"])
    layer.paste(face, (cx - side // 2, cy - side // 2))

    # 1) elips maskesi: silüetin çiçek bölgesinin dışına çıkmasını engeller
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).ellipse(
        [cx - w // 2, cy - h // 2, cx + w // 2, cy + h // 2], fill=255
    )
    radius = max(0.1, min(w, h) * p["feather"])
    mask = mask.filter(ImageFilter.GaussianBlur(radius))

    # 2) portre karesinin kendi kenarları da yumuşar (sert dikdörtgen izi kalmasın):
    #    yuvarlak köşeli kare + bulanıklık
    sq = Image.new("L", (S, S), 0)
    x0, y0 = cx - side // 2, cy - side // 2
    ImageDraw.Draw(sq).rounded_rectangle(
        [x0, y0, x0 + side, y0 + side], radius=int(side * 0.30), fill=255
    )
    sq = sq.filter(ImageFilter.GaussianBlur(max(1.0, side * max(0.09, p["feather"] * 1.3))))

    mask = ImageChops.multiply(mask, sq)

    out = Image.composite(layer, base, mask)
    return out.convert("RGB")


def prepare_conditioning_image(raw_bytes: bytes, layout: str | None = None,
                               layout_params: dict | None = None) -> Image.Image:
    """
    raw_bytes -> 1024x1024 conditioning görseli (PIL Image, RGB).

    layout=None      : eski davranış (gri kare, tüm tuvali kaplar)
    layout="bouquet" : silüet yalnızca çiçek elipsinde, dışı koyu
    """
    gray = _gray_square(raw_bytes)
    if layout == "bouquet":
        return _compose_bouquet(gray, layout_params)
    return gray


def to_data_uri(img: Image.Image, fmt: str = "JPEG", quality: int = 92) -> str:
    import base64

    buf = io.BytesIO()
    img.save(buf, format=fmt, quality=quality)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    mime = "image/jpeg" if fmt.upper() == "JPEG" else f"image/{fmt.lower()}"
    return f"data:{mime};base64,{b64}"
