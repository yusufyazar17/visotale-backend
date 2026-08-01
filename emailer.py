"""
Visotale — Resend ile önizleme teslim maili.

Kullanıcı üretim yavaş gittiği için beklemeden çıktıysa, sonuç hazır
olunca buradan e-posta ile gönderilir. Kuponlu ya da kuponsuz (Shopify
API'si başarısız olursa) çalışabilir — mail gönderimini asla bloklamaz.
"""

import os

import requests

import email_render

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
RESEND_FROM = os.environ.get("RESEND_FROM", "Visotale <no-reply@visotale.com>")
SITE_URL = os.environ.get("SITE_URL", "https://visotale.com")
PRODUCT_URL = os.environ.get("PRODUCT_URL", SITE_URL)  # ürün sayfasının tam linki — ayarlanmazsa ana sayfaya düşer

# Sosyal medya linkleri — boş bırakılırsa o ikon mailde hiç görünmez
SOCIAL_INSTAGRAM_URL = os.environ.get("SOCIAL_INSTAGRAM_URL", "")
SOCIAL_TIKTOK_URL = os.environ.get("SOCIAL_TIKTOK_URL", "")
SOCIAL_PINTEREST_URL = os.environ.get("SOCIAL_PINTEREST_URL", "")

# Footer'daki SVG ikonlarla aynı kaynak — ama mail istemcileri (özellikle
# Outlook) SVG göstermez, bu yüzden Cloudinary'nin f_png dönüşümüyle PNG
# olarak çekiyoruz.
_ICON_BASE = "https://res.cloudinary.com/dfclxpzlo/image/upload/f_png/v1785034796"
ICON_INSTAGRAM = f"{_ICON_BASE}/instagram_vtfbg0.svg"
ICON_TIKTOK = f"{_ICON_BASE}/tiktok_gyfc0x.svg"
ICON_PINTEREST = f"{_ICON_BASE}/pinterest_u8ou4b.svg"


def _social_row() -> str:
    icons = []
    if SOCIAL_INSTAGRAM_URL:
        icons.append(f'<a href="{SOCIAL_INSTAGRAM_URL}" style="margin:0 8px;"><img src="{ICON_INSTAGRAM}" width="22" height="22" alt="Instagram" style="display:inline-block;vertical-align:middle;"></a>')
    if SOCIAL_TIKTOK_URL:
        icons.append(f'<a href="{SOCIAL_TIKTOK_URL}" style="margin:0 8px;"><img src="{ICON_TIKTOK}" width="22" height="22" alt="TikTok" style="display:inline-block;vertical-align:middle;"></a>')
    if SOCIAL_PINTEREST_URL:
        icons.append(f'<a href="{SOCIAL_PINTEREST_URL}" style="margin:0 8px;"><img src="{ICON_PINTEREST}" width="22" height="22" alt="Pinterest" style="display:inline-block;vertical-align:middle;"></a>')
    if not icons:
        return ""
    return f'<div style="text-align:center;margin-top:24px;">{"".join(icons)}</div>'


def _resume_link(preview_url: str, painting_key: str) -> str:
    """Mail'deki CTA linkine üretilen görseli ve tabloyu gömer — wizard bunu
    algılayıp doğrudan sepet adımına atlar, müşteri en baştan başlamak
    zorunda kalmaz."""
    from urllib.parse import quote

    sep = "&" if "?" in PRODUCT_URL else "?"
    return f"{PRODUCT_URL}{sep}vt_preview={quote(preview_url, safe='')}&vt_tablo={quote(painting_key, safe='')}"

RESEND_API_URL = "https://api.resend.com/emails"


def _build_html(preview_url: str, painting_label: str, painting_key: str, discount: dict | None) -> str:
    coupon_block = ""
    if discount:
        coupon_block = f"""
        <div style="margin:32px 0;padding:24px;background:#f6f4f1;border-radius:14px;text-align:center;">
          <p style="margin:0 0 6px;font-size:13px;color:#8a857d;letter-spacing:.04em;text-transform:uppercase;">İlk siparişine özel</p>
          <p style="margin:0 0 14px;font-size:28px;font-weight:700;color:#1b3e28;letter-spacing:.02em;">%20 İNDİRİM</p>
          <p style="margin:0 0 4px;font-size:20px;font-weight:600;letter-spacing:.05em;background:#fff;display:inline-block;padding:10px 20px;border-radius:8px;border:1.5px dashed #225033;color:#1a1a1a;">{discount['code']}</p>
          <p style="margin:14px 0 0;font-size:12px;color:#b3403f;font-weight:600;">Sadece 24 saat geçerli — tek kullanımlık.</p>
        </div>
        """

    return f"""
    <div style="font-family:'DM Sans',Helvetica,Arial,sans-serif;max-width:560px;margin:0 auto;padding:32px 24px;color:#1a1a1a;">
      <div style="text-align:center;margin-bottom:28px;">
        <span style="font-family:Georgia,serif;font-size:26px;font-weight:600;background:linear-gradient(135deg,#225033,#1b3e28);-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;">visot<em>a</em>le</span>
      </div>
      <h1 style="font-family:Georgia,serif;font-size:24px;font-weight:500;text-align:center;margin:0 0 8px;">Tablon hazır 🎨</h1>
      <p style="text-align:center;color:#6b6b6b;font-size:13.5px;line-height:1.6;margin:0 0 24px;">
        Bu sadece bir önizleme — siparişinin sonrasında sana <strong style="color:#1a1a1a;">5 farklı örnek</strong> daha ileteceğiz.
      </p>
      <img src="{preview_url}" alt="Tablo önizlemesi" style="width:100%;border-radius:14px;display:block;margin-bottom:8px;">
      <p style="text-align:center;font-size:12px;color:#a0a0a0;margin:0 0 28px;">{painting_label} · Siparişin sonrası 4K kalitesinde, filigransız üretilir.</p>
      {coupon_block}
      <div style="text-align:center;margin-top:28px;">
        <a href="{_resume_link(preview_url, painting_key)}" style="display:inline-block;background:#1a1a1a;color:#fff;text-decoration:none;padding:14px 32px;border-radius:10px;font-weight:600;font-size:14px;">Siparişini tamamla</a>
      </div>
      {_social_row()}
      <p style="text-align:center;font-size:11px;color:#a0a0a0;margin-top:20px;">Visotale · Bu e-postayı bir önizleme talebiniz olduğu için aldınız.</p>
    </div>
    """


def _build_composed_html(image_url: str, resume_link: str) -> str:
    """Yeni tasarım: tüm görsel (arka plan + tablo + çift + metinler + kupon)
    sunucuda TEK bir görselde birleştirilmiş. Mail HTML'i bu yüzden çok basit —
    tek görsel, tamamı tıklanabilir link."""
    return f"""
    <div style="max-width:600px;margin:0 auto;">
      <a href="{resume_link}" style="display:block;text-decoration:none;">
        <img src="{image_url}" width="600" alt="Tablon hazır — Visotale" style="width:100%;display:block;border:0;">
      </a>
    </div>
    """


def send_preview_email(to_email: str, preview_url: str, painting_label: str, painting_key: str, discount: dict | None):
    """(ok: bool, detail: str) döner. detail hata mesajı ya da 'sent' olur —
    sessizce yutmuyoruz, Railway loglarına da yazıyoruz ki 'neden gitmedi'
    sorusuna cevap bulabilelim."""
    if not RESEND_API_KEY:
        print("[emailer] RESEND_API_KEY tanımlı değil — mail atlanıyor.")
        return False, "RESEND_API_KEY eksik"

    html = None
    if discount:
        # Yeni tasarım: kupon varsa tam birleşik görseli dene. Herhangi bir
        # adımda sorun çıkarsa (indirme/birleştirme/yükleme) sessizce eski
        # basit şablona düşüyoruz — mail gönderimi asla bunun yüzünden durmaz.
        try:
            r = requests.get(preview_url, timeout=15)
            r.raise_for_status()
            composed_bytes = email_render.compose_email_image(r.content, discount["code"])
            composed_url = email_render.upload_composed_image(composed_bytes)
            if composed_url:
                html = _build_composed_html(composed_url, _resume_link(preview_url, painting_key))
                print("[emailer] Birleşik mail görseli oluşturuldu.")
            else:
                print("[emailer] Birleşik görsel yüklenemedi — eski şablona düşülüyor.")
        except Exception as e:
            print(f"[emailer] Birleşik görsel oluşturulamadı ({e}) — eski şablona düşülüyor.")

    if html is None:
        html = _build_html(preview_url, painting_label, painting_key, discount)

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


def _build_failure_html(discount: dict | None) -> str:
    coupon_block = ""
    if discount:
        coupon_block = f"""
        <div style="margin:32px 0;padding:24px;background:#f6f4f1;border-radius:14px;text-align:center;">
          <p style="margin:0 0 6px;font-size:13px;color:#8a857d;letter-spacing:.04em;text-transform:uppercase;">Özür kuponun</p>
          <p style="margin:0 0 14px;font-size:28px;font-weight:700;color:#1b3e28;letter-spacing:.02em;">%20 İNDİRİM</p>
          <p style="margin:0 0 4px;font-size:20px;font-weight:600;letter-spacing:.05em;background:#fff;display:inline-block;padding:10px 20px;border-radius:8px;border:1.5px dashed #225033;color:#1a1a1a;">{discount['code']}</p>
          <p style="margin:14px 0 0;font-size:12px;color:#b3403f;font-weight:600;">Sadece 24 saat geçerli — tek kullanımlık.</p>
        </div>
        """

    return f"""
    <div style="font-family:'DM Sans',Helvetica,Arial,sans-serif;max-width:560px;margin:0 auto;padding:32px 24px;color:#1a1a1a;">
      <div style="text-align:center;margin-bottom:28px;">
        <span style="font-family:Georgia,serif;font-size:26px;font-weight:600;background:linear-gradient(135deg,#225033,#1b3e28);-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;">visot<em>a</em>le</span>
      </div>
      <h1 style="font-family:Georgia,serif;font-size:22px;font-weight:500;text-align:center;margin:0 0 12px;">Bu sefer olmadı 😔</h1>
      <p style="text-align:center;color:#6b6b6b;font-size:14px;line-height:1.6;margin:0 0 8px;">
        Tablonu hazırlamaya çalışırken teknik bir sorun yaşadık. Kusura bakma —
        tekrar denemeni rica ediyoruz, bu arada özür dileriz.
      </p>
      {coupon_block}
      <div style="text-align:center;margin-top:28px;">
        <a href="{SITE_URL}" style="display:inline-block;background:#1a1a1a;color:#fff;text-decoration:none;padding:14px 32px;border-radius:10px;font-weight:600;font-size:14px;">Tekrar dene</a>
      </div>
      {_social_row()}
      <p style="text-align:center;font-size:11px;color:#a0a0a0;margin-top:20px;">Visotale · Bu e-postayı bir önizleme talebiniz olduğu için aldınız.</p>
    </div>
    """


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
