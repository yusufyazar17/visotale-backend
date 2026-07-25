"""
Visotale — Wizard Backend (v9, sıfırdan yeniden yazıldı)

Tek endpoint: POST /create-preview
  form-data:
    - file          (opsiyonel, image_url yoksa zorunlu)
    - image_url      (opsiyonel, Cloudinary'den gelen orijinal foto linki)
    - painting_key   (zorunlu — paintings.py içindeki 4 anahtardan biri)

Yanıt (başarı):  {"ok": true,  "preview_url": "https://res.cloudinary.com/..."}
Yanıt (hata):    {"ok": false, "error": "insan-okur mesaj"}

Eski main.py'nin bilinen hataları burada düzeltildi:
  - style_prompt artık gerçekten okunuyor (tablo başına sabit, güvenli tarafta)
  - image_url artık gerçekten işleniyor
  - API anahtarları kod içine gömülü değil, ortam değişkeninden okunuyor
"""

import base64
import os
import time

import requests
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from image_prep import prepare_conditioning_image, to_data_uri
from paintings import get_painting
from watermark import apply_preview_treatment

# ---------------------------------------------------------------------------
# Ayarlar (ortam değişkenlerinden)
# ---------------------------------------------------------------------------
FAL_KEY = os.environ.get("FAL_KEY", "")
FAL_MODEL_URL = "https://fal.run/fal-ai/illusion-diffusion"

CLOUDINARY_CLOUD_NAME = os.environ.get("CLOUDINARY_CLOUD_NAME", "dfclxpzlo")
CLOUDINARY_UPLOAD_PRESET = os.environ.get("CLOUDINARY_UPLOAD_PRESET", "visotale_uploads")
CLOUDINARY_PREVIEW_FOLDER = os.environ.get("CLOUDINARY_PREVIEW_FOLDER", "visotale-previews")
CLOUDINARY_UPLOAD_URL = f"https://api.cloudinary.com/v1_1/{CLOUDINARY_CLOUD_NAME}/image/upload"

ALLOWED_ORIGINS = [
    o.strip()
    for o in os.environ.get(
        "ALLOWED_ORIGINS",
        "https://visotale.com,https://www.visotale.com,https://visotale.de,https://www.visotale.de",
    ).split(",")
    if o.strip()
]

MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20MB — frontend ile aynı sınır
FAL_TIMEOUT_S = 25  # önizleme 30sn hedefini tutturmak için sıkı zaman aşımı

app = FastAPI(title="Visotale Wizard Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Yardımcılar
# ---------------------------------------------------------------------------
def _fetch_source_bytes(file: UploadFile | None, image_url: str | None) -> bytes:
    if image_url:
        r = requests.get(image_url, timeout=10)
        r.raise_for_status()
        data = r.content
    elif file is not None:
        data = file.file.read()
    else:
        raise HTTPException(status_code=400, detail="file veya image_url gerekli.")

    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Dosya 20MB sınırını aşıyor.")
    if len(data) == 0:
        raise HTTPException(status_code=400, detail="Boş dosya.")
    return data


def _call_illusion_diffusion(conditioning_data_uri: str, painting: dict) -> str:
    if not FAL_KEY:
        raise HTTPException(
            status_code=500,
            detail="Sunucu yapılandırma hatası (FAL_KEY eksik). Lütfen daha sonra tekrar deneyin.",
        )

    payload = {
        "image_url": conditioning_data_uri,
        "prompt": painting["prompt"],
        "negative_prompt": painting["negative_prompt"],
        "controlnet_conditioning_scale": painting["conditioning_scale"],
        "guidance_scale": painting["guidance_scale"],
        "num_inference_steps": painting["num_inference_steps"],
        "control_guidance_end": painting.get("control_guidance_end", 0.8),
        "image_size": "square_hd",
    }
    headers = {"Authorization": f"Key {FAL_KEY}", "Content-Type": "application/json"}

    try:
        resp = requests.post(
            FAL_MODEL_URL, json=payload, headers=headers, timeout=FAL_TIMEOUT_S
        )
    except requests.Timeout:
        raise HTTPException(
            status_code=504, detail="Üretim zaman aşımına uğradı. Lütfen tekrar dene."
        )

    if not resp.ok:
        raise HTTPException(
            status_code=502,
            detail=f"Yapay zekâ servisi hata döndü ({resp.status_code}).",
        )

    data = resp.json()
    # fal modelleri genelde images: [{url: ...}] döner; olası varyasyonları da kontrol et
    url = None
    if isinstance(data.get("images"), list) and data["images"]:
        url = data["images"][0].get("url")
    elif isinstance(data.get("image"), dict):
        url = data["image"].get("url")

    if not url:
        raise HTTPException(status_code=502, detail="Yapay zekâ servisinden geçerli sonuç alınamadı.")
    return url


def _download_image_bytes(url: str) -> bytes:
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    return r.content


def _upload_to_cloudinary(image_bytes: bytes, filename: str) -> str:
    files = {"file": (filename, image_bytes, "image/jpeg")}
    data = {
        "upload_preset": CLOUDINARY_UPLOAD_PRESET,
        "folder": CLOUDINARY_PREVIEW_FOLDER,
    }
    r = requests.post(CLOUDINARY_UPLOAD_URL, files=files, data=data, timeout=15)
    if not r.ok:
        raise HTTPException(status_code=502, detail="Önizleme kaydedilemedi. Lütfen tekrar dene.")
    return r.json()["secure_url"]


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------
@app.post("/create-preview")
async def create_preview(
    painting_key: str = Form(...),
    image_url: str | None = Form(None),
    file: UploadFile | None = File(None),
):
    t0 = time.time()

    painting = get_painting(painting_key)
    if not painting:
        raise HTTPException(status_code=400, detail="Geçersiz tablo seçimi.")

    # 1) kaynak fotoğrafı al
    raw_bytes = _fetch_source_bytes(file, image_url)

    # 2) yüz(ler)i bul, kare kırp, gri+kontrast conditioning görseli üret
    conditioning_img = prepare_conditioning_image(raw_bytes)
    conditioning_data_uri = to_data_uri(conditioning_img)

    # 3) illusion-diffusion çağrısı (tablo başına ayarlanmış prompt/negatif/scale)
    result_url = _call_illusion_diffusion(conditioning_data_uri, painting)

    # 4) sonucu indir, önizleme muamelesi uygula (küçült + filigran)
    result_bytes = _download_image_bytes(result_url)
    from io import BytesIO
    from PIL import Image

    result_img = Image.open(BytesIO(result_bytes))
    preview_img = apply_preview_treatment(result_img)

    buf = BytesIO()
    preview_img.save(buf, format="JPEG", quality=88)
    preview_bytes = buf.getvalue()

    # 5) Cloudinary'e yükle, linki döndür
    preview_url = _upload_to_cloudinary(preview_bytes, f"{painting_key}-preview.jpg")

    elapsed = round(time.time() - t0, 1)
    return JSONResponse({"ok": True, "preview_url": preview_url, "elapsed_s": elapsed})


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code, content={"ok": False, "error": exc.detail}
    )


@app.get("/health")
async def health():
    return {"ok": True}
