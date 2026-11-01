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
import os
import hashlib
import base64
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps, ImageEnhance

FACE_CASCADE = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)

CONDITIONING_SIZE = 1024


def _detect_faces(cv_img_gray):
    faces = FACE_CASCADE.detectMultiScale(cv_img_gray, 1.08, 5, minSize=(40, 40))
    return faces


def _bbox_from_faces(faces, img_w, img_h, pad_top=0.6):
    xs = [x for (x, y, w, h) in faces]
    ys = [y for (x, y, w, h) in faces]
    xe = [x + w for (x, y, w, h) in faces]
    ye = [y + h for (x, y, w, h) in faces]
    x0, y0, x1, y1 = min(xs), min(ys), max(xe), max(ye)

    # yüzlerin etrafına pay bırak (saç, çene, omuz için)
    pad_x = int((x1 - x0) * 0.6)
    pad_y_top = int((y1 - y0) * pad_top)
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


def _gray_square(raw_bytes: bytes, pad_top: float = 0.6) -> Image.Image:
    """raw_bytes -> 1024x1024 gri/yüksek-kontrast kare (PIL Image, RGB). Yüz(ler) ortada."""
    img = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
    W, H = img.size

    cv_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    gray_cv = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    faces = _detect_faces(gray_cv)

    if len(faces) > 0:
        x0, y0, x1, y1 = _bbox_from_faces(faces, W, H, pad_top)
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
    "size": 0.68,     # portre karesinin tuvale oranı (0 = elipse otomatik sığdır)
    "halo": 150,      # portre dışı, elips içi parlaklık (saç/kontrast kaybolmasın diye açık)
    "dy": 0.02,       # portrenin elips merkezine göre dikey kayması (+ aşağı)
    "pad_top": 1.0,   # baş üstü boşluğu (yüz yüksekliğinin katı)
    "fit": 0.92,      # [cutout] kişinin elipse sığma oranı (1.0 = elipse değer)
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
        "halo": int(_clamp(p["halo"], 0, 255, LAYOUT_BOUQUET["halo"])),
        "dy": _clamp(p["dy"], -0.15, 0.15, LAYOUT_BOUQUET["dy"]),
        "pad_top": _clamp(p["pad_top"], 0.3, 1.6, LAYOUT_BOUQUET["pad_top"]),
        "fit": _clamp(p["fit"], 0.5, 1.0, LAYOUT_BOUQUET["fit"]),
    }


def _compose_bouquet(gray_square: Image.Image, params: dict | None) -> Image.Image:
    p = _sanitize_layout(params)
    S = CONDITIONING_SIZE
    w = int(S * p["w"])
    h = int(S * p["h"])
    cx = int(S * p["cx"])
    cy = int(S * p["cy"])
    py = cy + int(S * p["dy"])  # portrenin dikey merkezi
    if p["size"] == 0:
        # elipse tam sığan en büyük kare: yarı kenar = 1 / sqrt(1/a^2 + 1/b^2)
        a, b = w / 2.0, h / 2.0
        side = int(2.0 / ((1.0 / a ** 2 + 1.0 / b ** 2) ** 0.5))
    else:
        side = int(S * p["size"])

    face = ImageOps.grayscale(gray_square).resize((side, side), Image.LANCZOS)

    # Portre, ELİPS İÇİNDE açık bir halkanın (halo) üstüne yerleşir.
    # Böylece portrenin kenarı koyuya değil açığa erir: koyu saç, açık zeminle
    # kontrastını kaybetmez ve baş silueti kesilmez.
    halo_layer = Image.new("L", (S, S), p["halo"])
    x0, y0 = cx - side // 2, py - side // 2
    face_layer = Image.new("L", (S, S), p["halo"])
    face_layer.paste(face, (x0, y0))

    sq = Image.new("L", (S, S), 0)
    ImageDraw.Draw(sq).rounded_rectangle(
        [x0, y0, x0 + side, y0 + side], radius=int(side * 0.30), fill=255
    )
    sq = sq.filter(ImageFilter.GaussianBlur(max(1.0, side * max(0.09, p["feather"] * 1.3))))
    inner = Image.composite(face_layer, halo_layer, sq)

    # Elips: silüetin ve açık halkanın çiçek bölgesinin dışına çıkmasını engeller.
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).ellipse(
        [cx - w // 2, cy - h // 2, cx + w // 2, cy + h // 2], fill=255
    )
    radius = max(0.1, min(w, h) * p["feather"])
    mask = mask.filter(ImageFilter.GaussianBlur(radius))

    base = Image.new("L", (S, S), p["bg"])
    out = Image.composite(inner, base, mask)
    return out.convert("RGB")


# ---------------------------------------------------------------------------
# CUTOUT: fal.ai ile arka planı sil, kişiyi elipse sığdır
# ---------------------------------------------------------------------------
_CUTOUT_CACHE: dict = {}   # aynı fotoğraf için tekrar ücret ödememek için
FAL_BG_MODELS = ("fal-ai/birefnet/v2", "fal-ai/imageutils/rembg")


def _remove_background(raw_bytes: bytes) -> Image.Image:
    """Fotoğraftan kişiyi ayırır -> RGBA. fal.ai çağrısı (~1 kuruş)."""
    import requests

    key = hashlib.sha1(raw_bytes).hexdigest()
    if key in _CUTOUT_CACHE:
        return _CUTOUT_CACHE[key].copy()

    fal_key = os.environ.get("FAL_KEY", "")
    if not fal_key:
        raise RuntimeError("FAL_KEY yok")
    # çok büyük fotoğrafları küçült (hız + maliyet)
    im = ImageOps.exif_transpose(Image.open(io.BytesIO(raw_bytes))).convert("RGB")
    im.thumbnail((1536, 1536))
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=92)
    data_uri = "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")

    last_err = None
    for model in FAL_BG_MODELS:
        try:
            r = requests.post(
                f"https://fal.run/{model}",
                headers={"Authorization": f"Key {fal_key}", "Content-Type": "application/json"},
                json={"image_url": data_uri},
                timeout=90,
            )
            r.raise_for_status()
            url = r.json()["image"]["url"]
            png = requests.get(url, timeout=60)
            png.raise_for_status()
            out = Image.open(io.BytesIO(png.content)).convert("RGBA")
            if len(_CUTOUT_CACHE) > 40:
                _CUTOUT_CACHE.clear()
            _CUTOUT_CACHE[key] = out
            return out.copy()
        except Exception as e:  # sıradaki modeli dene
            last_err = e
    raise RuntimeError(f"arka plan silinemedi: {last_err}")


def _compose_cutout(raw_bytes: bytes, params: dict | None) -> Image.Image:
    p = _sanitize_layout(params)
    S = CONDITIONING_SIZE
    rgba = _remove_background(raw_bytes)
    alpha = np.array(rgba.split()[3])
    solid = alpha > 128
    cols = np.where(solid.sum(axis=0) > 2)[0]
    rows = np.where(solid.sum(axis=1) > 2)[0]
    if len(cols) < 10 or len(rows) < 10:
        raise RuntimeError("kişi bulunamadı")
    x0, x1, y0, y1 = int(cols[0]), int(cols[-1]) + 1, int(rows[0]), int(rows[-1]) + 1
    person = rgba.crop((x0, y0, x1, y1))
    bw, bh = person.size

    # gri + kontrast (eski hazırlıkla aynı mantık)
    gray = ImageOps.autocontrast(ImageOps.grayscale(person.convert("RGB")), cutoff=1)
    gray = ImageEnhance.Contrast(gray).enhance(1.35)

    # elips yarı eksenleri
    w = int(S * p["w"]); h = int(S * p["h"])
    a, b = w / 2.0, h / 2.0
    # kişinin sınır kutusunun köşeleri elipse sığsın: (bw/2/a)^2 + (bh/2/b)^2 <= 1
    k = 1.0 / (((bw / 2.0) / a) ** 2 + ((bh / 2.0) / b) ** 2) ** 0.5
    # sığdırma: kutu köşeleri yerine gerçek siluet daha içeri olduğu için
    # köşeleri biraz taşırmaya izin ver, ama dikey/yatay olarak tuvali aşma
    scale = k * p["fit"] * 1.12
    scale = min(scale, w / bw * 1.0, h / bh * 1.0)
    nw, nh = max(1, int(bw * scale)), max(1, int(bh * scale))
    gray = gray.resize((nw, nh), Image.LANCZOS)
    a_resized = person.split()[3].resize((nw, nh), Image.LANCZOS).filter(ImageFilter.GaussianBlur(1.2))

    cx = int(S * p["cx"]); cy = int(S * p["cy"]) + int(S * p["dy"])
    layer = Image.new("L", (S, S), p["halo"])
    layer.paste(gray, (cx - nw // 2, cy - nh // 2), a_resized)

    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).ellipse([cx - w // 2, int(S * p["cy"]) - h // 2,
                                  cx + w // 2, int(S * p["cy"]) + h // 2], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(max(0.1, min(w, h) * p["feather"])))
    base = Image.new("L", (S, S), p["bg"])
    return Image.composite(layer, base, mask).convert("RGB")


def prepare_conditioning_image(raw_bytes: bytes, layout: str | None = None,
                               layout_params: dict | None = None) -> Image.Image:
    """
    raw_bytes -> 1024x1024 conditioning görseli (PIL Image, RGB).

    layout=None      : eski davranış (gri kare, tüm tuvali kaplar)
    layout="bouquet" : silüet yalnızca çiçek elipsinde, dışı koyu
    """
    if layout == "cutout":
        try:
            return _compose_cutout(raw_bytes, layout_params)
        except Exception:
            # arka plan silme başarısızsa eski yönteme düş (üretim durmasın)
            return _compose_bouquet(_gray_square(raw_bytes, 1.0), layout_params)
    if layout == "bouquet":
        pad_top = _sanitize_layout(layout_params)["pad_top"]
        return _compose_bouquet(_gray_square(raw_bytes, pad_top), layout_params)
    return _gray_square(raw_bytes)


def to_data_uri(img: Image.Image, fmt: str = "JPEG", quality: int = 92) -> str:
    import base64

    buf = io.BytesIO()
    img.save(buf, format=fmt, quality=quality)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    mime = "image/jpeg" if fmt.upper() == "JPEG" else f"image/{fmt.lower()}"
    return f"data:{mime};base64,{b64}"
