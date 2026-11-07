"""
Visotale — 2 aşamalı (kalıp tablo + gizli yüz) üretim hattı, TEST amaçlı.

Mantık: stilin sabit referans tablosu (template_url) fal.ai Flux img2img'ye
başlangıç görseli olarak verilir; müşterinin gri tonlu fotoğrafı ControlNet
olarak yüzü tablonun içine gizler. Böylece buket/vazo/perde tablodaki gibi kalır.

Gerekli ortam değişkenleri: FAL_KEY (zaten var).
İsteğe bağlı: FLUX_CONTROLNET_PATH (varsayılan aşağıda; DOĞRULANMADI, test edilecek).
"""
import os
import time
from io import BytesIO

import requests
from fastapi import HTTPException

FLUX_URL = "https://queue.fal.run/fal-ai/flux-general/image-to-image"
FLUX_CONTROLNET_PATH = os.environ.get(
    "FLUX_CONTROLNET_PATH",
    "https://huggingface.co/lucataco/flux-dev-controlnet-qr-code/resolve/main/diffusion_pytorch_model.safetensors",
)
MAX_WAIT_S = 150


def run_flux(raw_bytes: bytes, painting_key: str, painting: dict):
    # main.py'deki yardımcılar (geç import: döngüsel import olmasın)
    from main import FAL_KEY, _upload_to_cloudinary, _download_image_bytes
    from image_prep import prepare_conditioning_image
    from watermark import apply_preview_treatment
    from PIL import Image

    tpl = painting.get("template_url")
    if not tpl or tpl.startswith("PASTE"):
        raise HTTPException(status_code=500, detail="Bu stil için template_url girilmemiş.")
    f = painting.get("flux", {})
    t0 = time.time()

    cond = prepare_conditioning_image(raw_bytes)  # gri kare, tüm tuval
    buf = BytesIO()
    cond.save(buf, format="JPEG", quality=90)
    cond_url = _upload_to_cloudinary(buf.getvalue(), f"{painting_key}-flux-cond.jpg")

    payload = {
        "image_url": tpl,
        "prompt": painting["prompt"],
        "strength": f.get("strength", 0.8),
        "num_inference_steps": f.get("steps", 28),
        "guidance_scale": f.get("guidance", 3.5),
        "image_size": "square_hd",
        "output_format": "jpeg",
        "controlnets": [{
            "path": f.get("cn_path", FLUX_CONTROLNET_PATH),
            "control_image_url": cond_url,
            "conditioning_scale": f.get("cn_scale", 0.7),
            "start_percentage": 0.0,
            "end_percentage": f.get("cn_end", 0.8),
        }],
    }
    h = {"Authorization": f"Key {FAL_KEY}", "Content-Type": "application/json"}
    sub = requests.post(FLUX_URL, json=payload, headers=h, timeout=20)
    if not sub.ok:
        raise HTTPException(status_code=502, detail=f"Flux hata ({sub.status_code}): {sub.text[:300]}")
    d = sub.json()
    status_url, resp_url = d["status_url"], d["response_url"]

    deadline = time.time() + MAX_WAIT_S
    while time.time() < deadline:
        time.sleep(2)
        try:
            s = requests.get(status_url, headers=h, timeout=15).json()
        except Exception:
            continue
        if s.get("status") == "COMPLETED":
            break
        if s.get("status") in ("FAILED", "ERROR"):
            raise HTTPException(status_code=502, detail="Flux üretimi başarısız: " + str(s)[:300])
    else:
        raise HTTPException(status_code=504, detail="Flux zaman aşımı.")

    r = requests.get(resp_url, headers=h, timeout=20)
    if not r.ok:
        raise HTTPException(status_code=502, detail=f"Flux sonuç hatası: {r.text[:300]}")
    url = r.json()["images"][0]["url"]

    img = Image.open(BytesIO(_download_image_bytes(url)))
    out = BytesIO()
    apply_preview_treatment(img).save(out, format="JPEG", quality=88)
    preview_url = _upload_to_cloudinary(out.getvalue(), f"{painting_key}-flux-preview.jpg")
    return {
        "preview_url": preview_url,
        "raw_result_url": url,
        "conditioning_url": cond_url,
        "timings_s": {},
        "elapsed_s": round(time.time() - t0, 1),
    }
