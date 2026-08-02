"""
Visotale — mail için "fotoğraf katmanı" birleştirme (compositing).

SADECE gerçek fotoğraf içeriğini (müze sahnesi + müşterinin ürettiği
tablo + önündeki çift) tek bir görselde birleştiriyoruz. Başlık, açıklama,
kupon, buton, ikonlar artık BURADA değil — emailer.py'de gerçek HTML/CSS
metin olarak yazılıyor, böylece piksel piksel/bulanık görünmüyorlar ve
gerçekten tıklanabilir oluyorlar.

Çift (couple.png) katmanı tabloyu ÖRTMESİN diye en sonda, kendi alfa
kanalıyla üstte yapıştırılıyor — tablo asla insanların önüne geçmiyor.

NOT: Bu modül geliştirme ortamından (bu sandbox) hiç test edilemedi —
Cloudinary'ye buradan ağ erişimi yok. İlk gerçek görsel test, Railway'de
canlı bir istekle yapılmalı.
"""

import io
import os

import requests
from PIL import Image, ImageOps

CLOUDINARY_CLOUD_NAME = os.environ.get("CLOUDINARY_CLOUD_NAME", "dfclxpzlo")
CLOUDINARY_UPLOAD_PRESET = os.environ.get("CLOUDINARY_UPLOAD_PRESET", "visotale_uploads")
CLOUDINARY_UPLOAD_URL = f"https://api.cloudinary.com/v1_1/{CLOUDINARY_CLOUD_NAME}/image/upload"

# Fotoğraf katmanı — 600 genişlik, müze görselinin kendi yüksekliği kadar
PHOTO_W, PHOTO_H = 600, 1142

ASSET_BASE = "https://res.cloudinary.com/dfclxpzlo/image/upload/v1785620004"
ASSET_BASE_2 = "https://res.cloudinary.com/dfclxpzlo/image/upload/v1785620003"

ASSETS = {
    "museum": f"{ASSET_BASE}/museum-image_xic50t.jpg",
    "couple": f"{ASSET_BASE_2}/couple_jqbfwv.png",
}

_asset_cache: dict[str, Image.Image] = {}


def _fetch_image(url: str) -> Image.Image:
    if url in _asset_cache:
        return _asset_cache[url].copy()
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    img = Image.open(io.BytesIO(r.content))
    img.load()
    _asset_cache[url] = img
    return img.copy()


def compose_photo_layer(preview_bytes: bytes) -> bytes:
    """Müze arka planı + gerçek tablo + çift'i tek görselde birleştirir.
    JPG bytes döner."""
    museum = _fetch_image(ASSETS["museum"]).convert("RGB")
    canvas = ImageOps.fit(museum, (PHOTO_W, PHOTO_H), method=Image.LANCZOS, centering=(0.5, 0.5))

    # Gerçek üretilen tablo — çerçeve boşluğuna (145,383) 310x310
    tablo = Image.open(io.BytesIO(preview_bytes)).convert("RGB")
    tablo = ImageOps.fit(tablo, (310, 310), method=Image.LANCZOS, centering=(0.5, 0.5))
    canvas.paste(tablo, (145, 383))

    # Çift — tablonun ÜSTÜNE, kendi şeffaflığıyla (couple.png RGBA olmalı)
    couple = _fetch_image(ASSETS["couple"])
    if couple.mode != "RGBA":
        couple = couple.convert("RGBA")
    couple = couple.resize((206, 408), Image.LANCZOS)
    canvas.paste(couple, (240, 625), couple)  # üçüncü argüman: kendi alfa kanalı maske olarak

    buf = io.BytesIO()
    canvas.save(buf, format="JPEG", quality=92)
    return buf.getvalue()


def upload_composed_image(image_bytes: bytes, filename: str = "visotale-mail-photo.jpg") -> str | None:
    """Birleştirilmiş görseli Cloudinary'e yükler, linkini döner. Başarısız
    olursa None döner (çağıran taraf ham önizleme görseline düşer)."""
    try:
        files = {"file": (filename, image_bytes, "image/jpeg")}
        data = {"upload_preset": CLOUDINARY_UPLOAD_PRESET, "folder": "visotale-mail-images"}
        r = requests.post(CLOUDINARY_UPLOAD_URL, files=files, data=data, timeout=15)
        if not r.ok:
            print(f"[email_render] Cloudinary yükleme hatası ({r.status_code}): {r.text[:300]}")
            return None
        return r.json()["secure_url"]
    except requests.RequestException as e:
        print(f"[email_render] Cloudinary'e yüklenemedi: {e}")
        return None
