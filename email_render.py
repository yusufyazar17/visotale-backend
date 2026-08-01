"""
Visotale — mail görselini sunucu tarafında birleştirme (compositing).

Kullanıcının Figma tasarımını (museum-image + couple + tablo-placement +
metinler) TEK bir görselde birleştiriyoruz: önce arka plan (müze sahnesi +
alt koyu yeşil blok), sonra o boşluğa müşterinin GERÇEK ürettiği tablo,
en üste de çift (couple.png, şeffaf PNG) — böylece çift her zaman tablonun
ÖNÜNDE durur, tablo asla onları kapatmaz.

Koordinatlar, kullanıcının verdiği Figma CSS export'u ile birebir eşleşir
(600×1815 canvas). Kupon kodu her müşteride farklı olduğu için o METNİ de
burada gerçek zamanlı çiziyoruz (Figma'daki "4FJ142" sadece placeholder'dı).

NOT: Bu modül geliştirme ortamından (bu sandbox) hiç test edilemedi —
Cloudinary'ye buradan ağ erişimi yok. İlk gerçek görsel test, Railway'de
canlı bir istekle yapılmalı.
"""

import io
import os

import requests
from PIL import Image, ImageDraw, ImageFont, ImageOps

FONT_PATH = os.path.join(os.path.dirname(__file__), "fonts", "Fraunces-Variable.ttf")

CLOUDINARY_CLOUD_NAME = os.environ.get("CLOUDINARY_CLOUD_NAME", "dfclxpzlo")
CLOUDINARY_UPLOAD_PRESET = os.environ.get("CLOUDINARY_UPLOAD_PRESET", "visotale_uploads")
CLOUDINARY_UPLOAD_URL = f"https://api.cloudinary.com/v1_1/{CLOUDINARY_CLOUD_NAME}/image/upload"

CANVAS_W, CANVAS_H = 600, 1815

WHITE = (255, 255, 255)
GREEN_LIGHT = (94, 195, 126)     # #5EC37E — "%20" ve vurgulu kelimeler
GREEN_MID = (32, 198, 119)       # #20C677 — kupon pili, "siparişini tamamla" yazısı
GREEN_DARK_BG = (23, 55, 34)     # #173722 — alt blok arka planı
GREEN_BUTTON_BG = (31, 83, 49)   # #1F5331 — "siparişini tamamla" pili

ASSET_BASE = "https://res.cloudinary.com/dfclxpzlo/image/upload/v1785620004"
ASSET_BASE_2 = "https://res.cloudinary.com/dfclxpzlo/image/upload/v1785620003"

ASSETS = {
    "museum": f"{ASSET_BASE}/museum-image_xic50t.jpg",
    "couple": f"{ASSET_BASE_2}/couple_jqbfwv.png",
    "logo_top": f"{ASSET_BASE}/visotale-logo-solid_vmgr0b.png",
    "logo_bottom": f"{ASSET_BASE}/visotale-logo-solid_copy_vrz1rv.png",
    "ig": f"{ASSET_BASE_2}/instagram_vtfbg0_kcem0g.png",
    "pin": f"{ASSET_BASE_2}/pinterest_u8ou4b_i7nmbz.png",
    "tt": f"{ASSET_BASE}/tiktok_gyfc0x_xlhxf6.png",
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


def _font(size: int, weight: int = 400) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(FONT_PATH, size)
    try:
        f.set_variation_by_axes([size if size <= 144 else 144, weight, 0, 0])
    except Exception:
        pass  # değişken font ekseni desteklenmiyorsa normal ağırlıkla devam
    return f


def _draw_centered(draw, text, cy, font, fill, canvas_w=CANVAS_W):
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    x = (canvas_w - w) / 2
    draw.text((x, cy), text, font=font, fill=fill)


def _paste_cover(base: Image.Image, overlay_url: str, box, position=(0, 0)):
    """overlay'i box (w,h) alanını tam kaplayacak şekilde ölçekleyip kırpar, position'a yapıştırır."""
    img = _fetch_image(overlay_url).convert("RGB")
    fitted = ImageOps.fit(img, box, method=Image.LANCZOS, centering=(0.5, 0.5))
    base.paste(fitted, position)


def compose_email_image(preview_bytes: bytes, coupon_code: str) -> bytes:
    """Tam mail görselini üretir, JPG bytes döner."""
    canvas = Image.new("RGB", (CANVAS_W, CANVAS_H), GREEN_DARK_BG)
    draw = ImageDraw.Draw(canvas)

    # 1) Müze sahnesi (arka plan üst kısım) — 600x1142
    museum = _fetch_image(ASSETS["museum"]).convert("RGB")
    museum = ImageOps.fit(museum, (600, 1142), method=Image.LANCZOS, centering=(0.5, 0.5))
    canvas.paste(museum, (0, 0))

    # 2) Alt koyu yeşil blok (kupon + footer alanı) — y:1116'dan tuvalin sonuna kadar
    draw.rectangle([0, 1116, CANVAS_W, CANVAS_H], fill=GREEN_DARK_BG)

    # 3) Gerçek üretilen tablo — çerçeve boşluğuna (145,383) 310x310
    tablo = Image.open(io.BytesIO(preview_bytes)).convert("RGB")
    tablo = ImageOps.fit(tablo, (310, 310), method=Image.LANCZOS, centering=(0.5, 0.5))
    canvas.paste(tablo, (145, 383))

    # 4) Çift — tablonun ÜSTÜNE, şeffaflığıyla birlikte (couple.png RGBA olmalı)
    couple = _fetch_image(ASSETS["couple"])
    if couple.mode != "RGBA":
        couple = couple.convert("RGBA")
    couple = couple.resize((206, 408), Image.LANCZOS)
    canvas.paste(couple, (240, 625), couple)  # üçüncü argüman: kendi alfa kanalı maske olarak

    # 5) Üst logo
    logo_top = _fetch_image(ASSETS["logo_top"])
    if logo_top.mode != "RGBA":
        logo_top = logo_top.convert("RGBA")
    logo_top = logo_top.resize((193, 44), Image.LANCZOS)
    canvas.paste(logo_top, (203, 51), logo_top)

    # 6) Başlık — "ÖNİZLEMEN HAZIR" (iki satır)
    title_font = _font(64, 400)
    _draw_centered(draw, "ÖNİZLEMEN", 129, title_font, WHITE)
    _draw_centered(draw, "HAZIR", 129 + 79, title_font, WHITE)

    # 7) Alt açıklama (iki satır, "5 farklı" vurgulu yeşil)
    sub_font = _font(22, 400)
    line1 = "bu sadece bir önizleme, siparişin sonrasında"
    line2a, line2b, line2c = "sana ", "5 farklı", " örnek daha ileteceğiz."
    _draw_centered(draw, line1, 282, sub_font, WHITE)
    # ikinci satırı 3 parçaya bölüp ortalayarak çiziyoruz ki "5 farklı" farklı renkte olsun
    w_a = draw.textbbox((0, 0), line2a, font=sub_font)[2]
    w_b = draw.textbbox((0, 0), line2b, font=sub_font)[2]
    w_c = draw.textbbox((0, 0), line2c, font=sub_font)[2]
    total_w = w_a + w_b + w_c
    start_x = (CANVAS_W - total_w) / 2
    y2 = 282 + 31
    draw.text((start_x, y2), line2a, font=sub_font, fill=WHITE)
    draw.text((start_x + w_a, y2), line2b, font=sub_font, fill=GREEN_LIGHT)
    draw.text((start_x + w_a + w_b, y2), line2c, font=sub_font, fill=WHITE)

    # 8) "24 SAAT GEÇERLİ"
    _draw_centered(draw, "24 SAAT GEÇERLİ", 1216, _font(30, 400), WHITE)

    # 9) "%20"
    _draw_centered(draw, "%20", 1249, _font(64, 400), GREEN_LIGHT)

    # 10) "İNDİRİM KODUN"
    _draw_centered(draw, "İNDİRİM KODUN", 1327, _font(30, 400), WHITE)

    # 11) Kupon pili — (181,1387) 238x86, yuvarlak, üzerinde gerçek kupon kodu
    # NOT: gerçek kodlarımız (VISOTALE20-XXXXXX) Figma'daki placeholder'dan
    # (4FJ142) çok daha uzun — font boyutu pile sığana kadar otomatik küçülür.
    pill_box = [181, 1387, 181 + 238, 1387 + 86]
    draw.rounded_rectangle(pill_box, radius=20, fill=GREEN_MID)
    max_code_w = 238 - 24  # her yandan 12px pay
    code_size = 40
    while code_size > 16:
        code_font = _font(code_size, 400)
        bbox = draw.textbbox((0, 0), coupon_code, font=code_font)
        if bbox[2] - bbox[0] <= max_code_w:
            break
        code_size -= 2
    code_w = bbox[2] - bbox[0]
    code_h = bbox[3] - bbox[1]
    code_x = pill_box[0] + (238 - code_w) / 2
    code_y = pill_box[1] + (86 - code_h) / 2 - bbox[1]
    draw.text((code_x, code_y), coupon_code, font=code_font, fill=WHITE)

    # 12) "siparişini tamamla" pili — (125,1528) 349x80, radius 28
    btn_box = [125, 1528, 125 + 349, 1528 + 80]
    draw.rounded_rectangle(btn_box, radius=28, fill=GREEN_BUTTON_BG)
    btn_font = _font(30, 400)  # 36 yerine 30 — 349px genişliğe güvenli sığsın
    _draw_centered(draw, "siparişini tamamla", 1528 + 22, btn_font, GREEN_MID)

    # 13) Sosyal medya ikonları
    for key, x in (("ig", 231), ("pin", 289), ("tt", 342)):
        icon = _fetch_image(ASSETS[key])
        if icon.mode != "RGBA":
            icon = icon.convert("RGBA")
        icon = icon.resize((29, 29), Image.LANCZOS)
        canvas.paste(icon, (x, 1675), icon)

    # 14) Alt logo
    logo_bottom = _fetch_image(ASSETS["logo_bottom"])
    if logo_bottom.mode != "RGBA":
        logo_bottom = logo_bottom.convert("RGBA")
    logo_bottom = logo_bottom.resize((151, 35), Image.LANCZOS)
    canvas.paste(logo_bottom, (225, 1718), logo_bottom)

    # 15) "proudly designed in türkiye"
    foot_font = _font(16, 400)
    text = "proudly designed in türkiye"
    bbox = draw.textbbox((0, 0), text, font=foot_font)
    fw = bbox[2] - bbox[0]
    fx = (CANVAS_W - fw) / 2
    draw.text((fx, 1766), "proudly designed in ", font=foot_font, fill=WHITE)
    prefix_w = draw.textbbox((0, 0), "proudly designed in ", font=foot_font)[2]
    draw.text((fx + prefix_w, 1766), "türkiye", font=foot_font, fill=GREEN_LIGHT)

    buf = io.BytesIO()
    canvas.save(buf, format="JPEG", quality=92)
    return buf.getvalue()


def upload_composed_image(image_bytes: bytes, filename: str = "visotale-mail.jpg") -> str | None:
    """Birleştirilmiş görseli Cloudinary'e yükler, linkini döner. Başarısız
    olursa None döner (çağıran taraf eski basit şablona düşer)."""
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
