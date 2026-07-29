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
import threading
import time

import requests
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from image_prep import prepare_conditioning_image, to_data_uri
from paintings import get_painting
from watermark import apply_preview_treatment
import jobs
import emailer
import shopify_discount

# ---------------------------------------------------------------------------
# Ayarlar (ortam değişkenlerinden)
# ---------------------------------------------------------------------------
FAL_KEY = os.environ.get("FAL_KEY", "")
FAL_SUBMIT_URL = "https://queue.fal.run/fal-ai/illusion-diffusion"
FAL_QUEUE_MAX_WAIT_S = 55   # senkron /create-preview yolu için — Railway'in gateway'i araya girmesin diye temkinli
FAL_QUEUE_MAX_WAIT_S_BACKGROUND = 300  # arka plan job'ları için — açık bir bağlantı yok, çok daha sabırlı olabiliriz
FAL_POLL_INTERVAL_S = 1.2   # her durum sorgusu arası bekleme
FAL_SHORT_CALL_TIMEOUT_S = 12  # gönderim/sorgu/sonuç çağrılarının HER BİRİ kısa tutulur

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


def _call_illusion_diffusion(conditioning_data_uri: str, painting: dict, timings: dict, max_wait_s: int = FAL_QUEUE_MAX_WAIT_S) -> str:
    """
    fal.ai'nin KUYRUK API'sini kullanır: tek uzun bağlantı yerine
    (gönder -> kısa aralıklarla durumu sor -> bitince sonucu al).
    Bu yöntem, tek bir uzun HTTP bağlantısının bir ara katmanda
    (proxy, yük dengeleyici vb.) zamanından önce kesilme riskini
    ortadan kaldırır ve soğuk başlangıçlara karşı çok daha dayanıklıdır.

    `timings` dict'ine 3a/3b/3c alt adım sürelerini yazar (main.py'deki
    genel zaman ölçümüyle aynı sözlüğü paylaşır).
    """
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

    # 3a) İşi kuyruğa gönder
    t_sub = time.time()
    try:
        submit = requests.post(
            FAL_SUBMIT_URL, json=payload, headers=headers, timeout=FAL_SHORT_CALL_TIMEOUT_S
        )
    except requests.RequestException:
        raise HTTPException(status_code=502, detail="Yapay zekâ servisine ulaşılamadı. Lütfen tekrar dene.")
    timings["3a_kuyruga_gonder"] = round(time.time() - t_sub, 2)

    if not submit.ok:
        raise HTTPException(
            status_code=502, detail=f"Yapay zekâ servisi hata döndü ({submit.status_code})."
        )

    sub_data = submit.json()
    request_id = sub_data.get("request_id")
    status_url = sub_data.get("status_url")
    response_url = sub_data.get("response_url")
    if not request_id:
        raise HTTPException(status_code=502, detail="Yapay zekâ servisi geçerli bir istek kimliği döndürmedi.")
    if not status_url:
        status_url = f"{FAL_SUBMIT_URL}/requests/{request_id}/status"
    if not response_url:
        response_url = f"{FAL_SUBMIT_URL}/requests/{request_id}"

    # 3b) Kısa aralıklarla durumu sor (her sorgu kısa, toplam bekleme uzun olabilir)
    t_wait = time.time()
    deadline = time.time() + max_wait_s
    status = None
    poll_count = 0
    while time.time() < deadline:
        time.sleep(FAL_POLL_INTERVAL_S)
        poll_count += 1
        try:
            st_resp = requests.get(status_url, headers=headers, timeout=FAL_SHORT_CALL_TIMEOUT_S)
        except requests.RequestException:
            continue  # geçici ağ hatası — bir sonraki turda tekrar dene
        if not st_resp.ok:
            continue
        status = st_resp.json().get("status")
        if status == "COMPLETED":
            break
        if status in ("FAILED", "ERROR"):
            raise HTTPException(status_code=502, detail="Yapay zekâ servisi üretimi tamamlayamadı. Lütfen tekrar dene.")
    else:
        timings["3b_kuyrukta_bekleme"] = round(time.time() - t_wait, 2)
        timings["3b_poll_sayisi"] = poll_count
        raise HTTPException(status_code=504, detail="Üretim zaman aşımına uğradı. Lütfen tekrar dene.")
    timings["3b_kuyrukta_bekleme"] = round(time.time() - t_wait, 2)
    timings["3b_poll_sayisi"] = poll_count

    # 3c) Sonucu al
    t_fetch = time.time()
    try:
        result_resp = requests.get(response_url, headers=headers, timeout=FAL_SHORT_CALL_TIMEOUT_S)
    except requests.RequestException:
        raise HTTPException(status_code=502, detail="Sonuç alınamadı. Lütfen tekrar dene.")

    if not result_resp.ok:
        raise HTTPException(status_code=502, detail="Sonuç alınamadı. Lütfen tekrar dene.")
    timings["3c_sonucu_al"] = round(time.time() - t_fetch, 2)

    data = result_resp.json()
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
def _run_pipeline(raw_bytes: bytes, painting_key: str, painting: dict, max_wait_s: int = FAL_QUEUE_MAX_WAIT_S):
    """
    Ortak üretim hattı: hem senkron /create-preview hem de arka plan
    job worker'ı bunu kullanır. Başarılı olursa dict döner, hata
    durumunda HTTPException fırlatır (çağıran taraf yakalar).
    """
    t0 = time.time()
    timings = {}
    conditioning_url = None

    def mark(label, since):
        timings[label] = round(time.time() - since, 2)
        return time.time()

    try:
        t = time.time()
        conditioning_img = prepare_conditioning_image(raw_bytes)
        conditioning_data_uri = to_data_uri(conditioning_img)
        t = mark("2_yuz_tespit_hazirlik", t)

        from io import BytesIO
        cond_buf = BytesIO()
        conditioning_img.save(cond_buf, format="JPEG", quality=90)
        conditioning_url = _upload_to_cloudinary(cond_buf.getvalue(), f"{painting_key}-conditioning.jpg")
        t = mark("2b_conditioning_yukle", t)

        result_url = _call_illusion_diffusion(conditioning_data_uri, painting, timings, max_wait_s)
        t = time.time()

        from PIL import Image
        result_bytes = _download_image_bytes(result_url)
        t = mark("4a_sonucu_indir", t)

        result_img = Image.open(BytesIO(result_bytes))
        preview_img = apply_preview_treatment(result_img)
        t = mark("4b_watermark", t)

        buf = BytesIO()
        preview_img.save(buf, format="JPEG", quality=88)
        preview_bytes = buf.getvalue()

        preview_url = _upload_to_cloudinary(preview_bytes, f"{painting_key}-preview.jpg")
        t = mark("5_preview_yukle", t)

        elapsed = round(time.time() - t0, 1)
        return {
            "preview_url": preview_url,
            "raw_result_url": result_url,
            "conditioning_url": conditioning_url,
            "timings_s": timings,
            "elapsed_s": elapsed,
        }
    except HTTPException:
        raise
    except Exception as exc:  # beklenmedik hata — yine de düzgün bir mesajla geri dön
        raise HTTPException(status_code=500, detail=f"Beklenmedik hata: {exc}")


@app.post("/create-preview")
async def create_preview(
    painting_key: str = Form(...),
    strength: str = Form("orta"),
    image_url: str | None = Form(None),
    file: UploadFile | None = File(None),
):
    t0 = time.time()

    painting = get_painting(painting_key, strength)
    if not painting:
        raise HTTPException(status_code=400, detail="Geçersiz tablo seçimi.")

    raw_bytes = _fetch_source_bytes(file, image_url)

    try:
        result = _run_pipeline(raw_bytes, painting_key, painting)
        return JSONResponse({
            "ok": True,
            "preview_url": result["preview_url"],
            "elapsed_s": result["elapsed_s"],
            "debug": {
                "conditioning_url": result["conditioning_url"],
                "raw_result_url": result["raw_result_url"],
                "timings_s": result["timings_s"],
            },
        })
    except HTTPException as exc:
        elapsed = round(time.time() - t0, 1)
        return JSONResponse(
            status_code=exc.status_code,
            content={"ok": False, "error": exc.detail, "elapsed_s": elapsed},
        )


# ---------------------------------------------------------------------------
# Job tabanlı akış — "Önizleme İste": kısa süre canlı denenir, uzarsa
# arka planda devam edip sonucu e-posta ile gönderir.
# ---------------------------------------------------------------------------
FAST_PATH_THRESHOLD_S = 22  # bu sürenin üzerinde biterse "geç kaldı" sayılır, mail atılır


def _generation_job_worker(job_id: str, raw_bytes: bytes, painting_key: str, painting: dict, email: str | None):
    t0 = time.time()
    try:
        result = _run_pipeline(raw_bytes, painting_key, painting, FAL_QUEUE_MAX_WAIT_S_BACKGROUND)
        jobs.set_job_done(job_id, result)  # üretim başarılı — job durumu artık kesin "done"

        elapsed = time.time() - t0
        if email and elapsed > FAST_PATH_THRESHOLD_S:
            # Mail gönderimi ayrı bir try/except'te — burada bir şey patlarsa
            # az önce "done" olarak işaretlediğimiz job'ı asla "error"a çevirmesin.
            try:
                discount = shopify_discount.create_one_time_discount(email)
                ok, detail = emailer.send_preview_email(
                    to_email=email,
                    preview_url=result["preview_url"],
                    painting_label=painting.get("label", "Tablon"),
                    discount=discount,
                )
                jobs.set_email_status(job_id, ok, detail)
            except Exception as email_exc:
                print(f"[job {job_id}] Mail gönderirken beklenmedik hata: {email_exc}")
                jobs.set_email_status(job_id, False, f"Beklenmedik hata: {email_exc}")
    except HTTPException as exc:
        jobs.set_job_error(job_id, exc.detail)
        if email:
            try:
                discount = shopify_discount.create_one_time_discount(email)
                ok, detail = emailer.send_failure_email(to_email=email, discount=discount)
                jobs.set_email_status(job_id, ok, detail)
            except Exception as email_exc:
                print(f"[job {job_id}] Özür maili gönderirken hata: {email_exc}")
    except Exception as exc:
        jobs.set_job_error(job_id, f"Beklenmedik hata: {exc}")
        if email:
            try:
                discount = shopify_discount.create_one_time_discount(email)
                ok, detail = emailer.send_failure_email(to_email=email, discount=discount)
                jobs.set_email_status(job_id, ok, detail)
            except Exception as email_exc:
                print(f"[job {job_id}] Özür maili gönderirken hata: {email_exc}")


@app.post("/create-preview-job")
async def create_preview_job(
    painting_key: str = Form(...),
    strength: str = Form("orta"),
    email: str | None = Form(None),
    image_url: str | None = Form(None),
    file: UploadFile | None = File(None),
):
    painting = get_painting(painting_key, strength)
    if not painting:
        raise HTTPException(status_code=400, detail="Geçersiz tablo seçimi.")

    # dosyayı burada, istek hâlâ açıkken okumak zorundayız —
    # arka plan thread'i başladığında UploadFile artık kapanmış olabilir
    raw_bytes = _fetch_source_bytes(file, image_url)

    job_id = jobs.create_job({"painting_key": painting_key, "email": email})

    thread = threading.Thread(
        target=_generation_job_worker,
        args=(job_id, raw_bytes, painting_key, painting, email),
        daemon=True,
    )
    thread.start()

    return JSONResponse({"ok": True, "job_id": job_id})


@app.get("/job-status/{job_id}")
async def job_status(job_id: str):
    job = jobs.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="İş bulunamadı.")

    email_info = {"email_sent": job.get("email_sent"), "email_detail": job.get("email_detail")}

    if job["status"] == "done":
        result = job["result"]
        return JSONResponse({
            "ok": True,
            "status": "done",
            "preview_url": result["preview_url"],
            "elapsed_s": result["elapsed_s"],
            "debug": {
                "conditioning_url": result["conditioning_url"],
                "raw_result_url": result["raw_result_url"],
                "timings_s": result["timings_s"],
            },
            **email_info,
        })
    if job["status"] == "error":
        return JSONResponse({"ok": False, "status": "error", "error": job["error"], **email_info})
    return JSONResponse({"ok": True, "status": "pending", **email_info})


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code, content={"ok": False, "error": exc.detail}
    )


@app.get("/health")
async def health():
    return {"ok": True}
