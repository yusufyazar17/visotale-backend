"""
Visotale — Resend ile önizleme teslim maili.

Kullanıcı üretim yavaş gittiği için beklemeden çıktıysa, sonuç hazır
olunca buradan e-posta ile gönderilir. Kuponlu ya da kuponsuz (Shopify
API'si başarısız olursa) çalışabilir — mail gönderimini asla bloklamaz.

TASARIM: sadece "fotoğraf katmanı" (müze sahnesi + gerçek tablo + çift)
sunucuda tek görselde birleştirilir (email_render.py). Başlık, açıklama,
kupon, buton, ikonlar GERÇEK HTML/CSS metin — piksel piksel görünmesinler
ve gerçekten tıklanabilir olsunlar diye.
"""

import os
from urllib.parse import quote

import requests

import email_render

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
RESEND_FROM = os.environ.get("RESEND_FROM", "Visotale <no-reply@visotale.com>")
SITE_URL = os.environ.get("SITE_URL", "https://visotale.com")
PRODUCT_URL = os.environ.get("PRODUCT_URL", SITE_URL)  # ürün sayfasının tam linki

# Sosyal medya linkleri — boş bırakılırsa o ikon mailde hiç görünmez
SOCIAL_INSTAGRAM_URL = os.environ.get("SOCIAL_INSTAGRAM_URL", "")
SOCIAL_TIKTOK_URL = os.environ.get("SOCIAL_TIKTOK_URL", "")
SOCIAL_PINTEREST_URL = os.environ.get("SOCIAL_PINTEREST_URL", "")

RESEND_API_URL = "https://api.resend.com/emails"

# ---------------------------------------------------------------------------
# Statik görseller — SVG kaynaklar Cloudinary'nin f_png dönüşümüyle PNG
# olarak çekiliyor (Outlook SVG göstermez). w_ parametresiyle görüntülenecek
# boyuttan daha yüksek çözünürlükte rasterize ettiriyoruz (retina netliği,
# kaynak SVG olduğu için Cloudinary'nin istediğimiz boyutta net çizmesi
# mümkün).
def _icon_url(path: str, display_w: int) -> str:
    hi_res_w = display_w * 3
    return f"https://res.cloudinary.com/dfclxpzlo/image/upload/f_png,w_{hi_res_w}/{path}"


ICON_INSTAGRAM = _icon_url("v1785034796/instagram_vtfbg0.svg", 22)
ICON_TIKTOK = _icon_url("v1785034796/tiktok_gyfc0x.svg", 22)
ICON_PINTEREST = _icon_url("v1785034796/pinterest_u8ou4b.svg", 22)
LOGO_TOP = "https://res.cloudinary.com/dfclxpzlo/image/upload/v1785620004/visotale-logo-solid_vmgr0b.png"
LOGO_BOTTOM = "https://res.cloudinary.com/dfclxpzlo/image/upload/v1785620004/visotale-logo-solid_copy_vrz1rv.png"
# Kullanıcının kendi kupon grafiği — SVG kaynağı, f_png ile yüksek çözünürlükte
KUPON_BG = _icon_url("v1785620003/kupon_rd8q0l.svg", 200)


def _resume_link(preview_url: str, painting_key: str) -> str:
    """Mail'deki CTA linkine üretilen görseli ve tabloyu gömer — wizard bunu
    algılayıp doğrudan sepet adımına atlar, müşteri en baştan başlamak
    zorunda kalmaz."""
    sep = "&" if "?" in PRODUCT_URL else "?"
    return f"{PRODUCT_URL}{sep}vt_preview={quote(preview_url, safe='')}&vt_tablo={quote(painting_key, safe='')}"


def _social_row() -> str:
    icons = []
    if SOCIAL_INSTAGRAM_URL:
        icons.append(f'<a href="{SOCIAL_INSTAGRAM_URL}" style="margin:0 8px;"><img src="{ICON_INSTAGRAM}" width="22" height="22" alt="Instagram" style="display:inline-block;vertical-align:middle;border:0;"></a>')
    if SOCIAL_TIKTOK_URL:
        icons.append(f'<a href="{SOCIAL_TIKTOK_URL}" style="margin:0 8px;"><img src="{ICON_TIKTOK}" width="22" height="22" alt="TikTok" style="display:inline-block;vertical-align:middle;border:0;"></a>')
    if SOCIAL_PINTEREST_URL:
        icons.append(f'<a href="{SOCIAL_PINTEREST_URL}" style="margin:0 8px;"><img src="{ICON_PINTEREST}" width="22" height="22" alt="Pinterest" style="display:inline-block;vertical-align:middle;border:0;"></a>')
    if not icons:
        return ""
    return f'<div style="text-align:center;margin-top:8px;">{"".join(icons)}</div>'


def _coupon_badge(code: str) -> str:
    """Kullanıcının kendi kupon grafiğini arka plan yapıp, üstüne gerçek
    kodu yazıyoruz. Outlook için hem CSS background-image hem klasik HTML
    background= attribute'u birlikte kullanılıyor (Outlook CSS'i çoğu zaman
    yok sayar ama HTML attribute'unu VML üzerinden gösterebilir)."""
    return f"""
    <table role="presentation" cellpadding="0" cellspacing="0" border="0" align="center" style="margin:0 auto 28px;">
      <tr>
        <td width="200" height="70" background="{KUPON_BG}"
            style="background-image:url('{KUPON_BG}');background-size:cover;background-position:center;
                   text-align:center;vertical-align:middle;border-radius:16px;">
          <span style="font-family:Georgia,serif;font-size:24px;font-weight:600;color:#ffffff;letter-spacing:.04em;">{code}</span>
        </td>
      </tr>
    </table>
    """


def _build_html(photo_url: str, painting_label: str, resume_link: str, discount: dict | None) -> str:
    coupon_section = ""
    if discount:
        coupon_section = f"""
        <p style="color:#ffffff;font-size:16px;letter-spacing:.06em;margin:0 0 4px;">24 SAAT GEÇERLİ</p>
        <p style="font-family:Georgia,serif;color:#5EC37E;font-size:44px;margin:0 0 4px;font-weight:500;">%20</p>
        <p style="color:#ffffff;font-size:16px;letter-spacing:.06em;margin:0 0 20px;">İNDİRİM KODUN</p>
        {_coupon_badge(discount['code'])}
        <p style="color:#b3403f;font-size:12px;font-weight:600;margin:-16px 0 24px;">Sadece 24 saat geçerli — tek kullanımlık.</p>
        """

    return f"""
    <div style="max-width:600px;margin:0 auto;background:#173722;font-family:'DM Sans',Helvetica,Arial,sans-serif;">

      <div style="padding:32px 24px 0;text-align:center;">
        <img src="{LOGO_TOP}" width="160" alt="Visotale" style="margin-bottom:24px;border:0;">
        <h1 style="font-family:Georgia,serif;color:#ffffff;font-size:38px;font-weight:400;margin:0;line-height:1.15;">ÖNİZLEMEN<br>HAZIR</h1>
        <p style="color:#ffffff;font-size:14.5px;line-height:1.6;margin:16px 0 0;">
          bu sadece bir önizleme, siparişin sonrasında sana <strong style="color:#5EC37E;">5 farklı</strong> örnek daha ileteceğiz.
        </p>
      </div>

      <div style="padding:28px 0 0;">
        <img src="{photo_url}" width="600" alt="{painting_label}" style="width:100%;display:block;border:0;">
      </div>

      <div style="padding:40px 24px;text-align:center;">
        {coupon_section}
        <a href="{resume_link}" style="display:inline-block;background:#1F5331;color:#5EC37E;text-decoration:none;padding:18px 56px;border-radius:28px;font-family:Georgia,serif;font-size:18px;">siparişini tamamla</a>

        {_social_row()}
        <div style="margin-top:20px;">
          <img src="{LOGO_BOTTOM}" width="120" alt="Visotale" style="border:0;">
        </div>
        <p style="color:#ffffff;opacity:.65;font-size:11px;margin-top:10px;">proudly designed in <span style="color:#5EC37E;">türkiye</span></p>
      </div>
    </div>
    """


def _build_failure_html(discount: dict | None) -> str:
    coupon_section = ""
    if discount:
        coupon_section = f"""
        <p style="color:#ffffff;font-size:16px;letter-spacing:.06em;margin:0 0 4px;">24 SAAT GEÇERLİ</p>
        <p style="font-family:Georgia,serif;color:#5EC37E;font-size:44px;margin:0 0 4px;font-weight:500;">%20</p>
        <p style="color:#ffffff;font-size:16px;letter-spacing:.06em;margin:0 0 20px;">ÖZÜR KUPONUN</p>
        {_coupon_badge(discount['code'])}
        <p style="color:#b3403f;font-size:12px;font-weight:600;margin:-16px 0 24px;">Sadece 24 saat geçerli — tek kullanımlık.</p>
        """

    return f"""
    <div style="max-width:600px;margin:0 auto;background:#173722;font-family:'DM Sans',Helvetica,Arial,sans-serif;padding:40px 24px;text-align:center;">
      <img src="{LOGO_TOP}" width="160" alt="Visotale" style="margin-bottom:24px;border:0;">
      <h1 style="font-family:Georgia,serif;color:#ffffff;font-size:28px;font-weight:400;margin:0 0 12px;">Bu sefer olmadı 😔</h1>
      <p style="color:#ffffff;opacity:.85;font-size:14.5px;line-height:1.6;margin:0 0 8px;">
        Tablonu hazırlamaya çalışırken teknik bir sorun yaşadık. Kusura bakma —
        tekrar denemeni rica ediyoruz, bu arada özür dileriz.
      </p>
      {coupon_section}
      <a href="{SITE_URL}" style="display:inline-block;background:#1F5331;color:#5EC37E;text-decoration:none;padding:18px 56px;border-radius:28px;font-family:Georgia,serif;font-size:18px;">tekrar dene</a>
      {_social_row()}
      <div style="margin-top:20px;">
        <img src="{LOGO_BOTTOM}" width="120" alt="Visotale" style="border:0;">
      </div>
      <p style="color:#ffffff;opacity:.65;font-size:11px;margin-top:10px;">proudly designed in <span style="color:#5EC37E;">türkiye</span></p>
    </div>
    """


def send_preview_email(to_email: str, preview_url: str, painting_label: str, painting_key: str, discount: dict | None):
    """(ok: bool, detail: str) döner. detail hata mesajı ya da 'sent' olur —
    sessizce yutmuyoruz, Railway loglarına da yazıyoruz ki 'neden gitmedi'
    sorusuna cevap bulabilelim."""
    if not RESEND_API_KEY:
        print("[emailer] RESEND_API_KEY tanımlı değil — mail atlanıyor.")
        return False, "RESEND_API_KEY eksik"

    photo_url = preview_url  # sonuç bulunamazsa ham önizlemeye düş
    try:
        r = requests.get(preview_url, timeout=15)
        r.raise_for_status()
        photo_bytes = email_render.compose_photo_layer(r.content)
        composed_url = email_render.upload_composed_image(photo_bytes)
        if composed_url:
            photo_url = composed_url
        else:
            print("[emailer] Fotoğraf katmanı yüklenemedi — ham önizleme kullanılıyor.")
    except Exception as e:
        print(f"[emailer] Fotoğraf katmanı oluşturulamadı ({e}) — ham önizleme kullanılıyor.")

    resume_link = _resume_link(preview_url, painting_key)
    html = _build_html(photo_url, painting_label, resume_link, discount)

    payload = {
        "from": RESEND_FROM,
        "to": [to_email],
        "subject": f"Tablon hazır — {painting_label} 🎨",
        "html": html,
    }
    headers = {"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"}

    try:
        r = requests.post(RESEND_API_URL, json=payload, headers=headers, timeout=10)
        if not r.ok:
            print(f"[emailer] Resend hata döndü ({r.status_code}): {r.text[:300]}")
            return False, f"Resend {r.status_code}: {r.text[:200]}"
        print(f"[emailer] Mail gönderildi: {to_email}")
        return True, "sent"
    except requests.RequestException as e:
        print(f"[emailer] Resend'e istek atılamadı: {e}")
        return False, str(e)


def send_failure_email(to_email: str, discount: dict | None):
    if not RESEND_API_KEY:
        print("[emailer] RESEND_API_KEY tanımlı değil — mail atlanıyor.")
        return False, "RESEND_API_KEY eksik"

    payload = {
        "from": RESEND_FROM,
        "to": [to_email],
        "subject": "Tablon için biraz daha zamana ihtiyacımız var",
        "html": _build_failure_html(discount),
    }
    headers = {"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"}

    try:
        r = requests.post(RESEND_API_URL, json=payload, headers=headers, timeout=10)
        if not r.ok:
            print(f"[emailer] Resend hata döndü ({r.status_code}): {r.text[:300]}")
            return False, f"Resend {r.status_code}: {r.text[:200]}"
        print(f"[emailer] Özür maili gönderildi: {to_email}")
        return True, "sent"
    except requests.RequestException as e:
        print(f"[emailer] Resend'e istek atılamadı: {e}")
        return False, str(e)
