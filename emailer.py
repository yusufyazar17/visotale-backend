"""
Visotale — Resend ile önizleme teslim maili.

Kullanıcı üretim yavaş gittiği için beklemeden çıktıysa, sonuç hazır
olunca buradan e-posta ile gönderilir. Kuponlu ya da kuponsuz (Shopify
API'si başarısız olursa) çalışabilir — mail gönderimini asla bloklamaz.
"""

import os

import requests

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
RESEND_FROM = os.environ.get("RESEND_FROM", "Visotale <no-reply@visotale.com>")
SITE_URL = os.environ.get("SITE_URL", "https://visotale.com")

RESEND_API_URL = "https://api.resend.com/emails"


def _build_html(preview_url: str, painting_label: str, discount: dict | None) -> str:
    coupon_block = ""
    if discount:
        coupon_block = f"""
        <div style="margin:32px 0;padding:24px;background:#f6f4f1;border-radius:14px;text-align:center;">
          <p style="margin:0 0 6px;font-size:13px;color:#8a857d;letter-spacing:.04em;text-transform:uppercase;">İlk siparişine özel</p>
          <p style="margin:0 0 14px;font-size:28px;font-weight:700;color:#1b3e28;letter-spacing:.02em;">%20 İNDİRİM</p>
          <p style="margin:0 0 4px;font-size:20px;font-weight:600;letter-spacing:.05em;background:#fff;display:inline-block;padding:10px 20px;border-radius:8px;border:1.5px dashed #225033;color:#1a1a1a;">{discount['code']}</p>
          <p style="margin:14px 0 0;font-size:12px;color:#8a857d;">Bu kod tek kullanımlıktır ve 7 gün geçerlidir.</p>
        </div>
        """

    return f"""
    <div style="font-family:'DM Sans',Helvetica,Arial,sans-serif;max-width:560px;margin:0 auto;padding:32px 24px;color:#1a1a1a;">
      <div style="text-align:center;margin-bottom:28px;">
        <span style="font-family:Georgia,serif;font-size:26px;font-weight:600;background:linear-gradient(135deg,#225033,#1b3e28);-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;">visot<em>a</em>le</span>
      </div>
      <h1 style="font-family:Georgia,serif;font-size:24px;font-weight:500;text-align:center;margin:0 0 8px;">Tablon hazır 🎨</h1>
      <p style="text-align:center;color:#6b6b6b;font-size:14px;margin:0 0 28px;">{painting_label} — önizlemen aşağıda</p>
      <img src="{preview_url}" alt="Tablo önizlemesi" style="width:100%;border-radius:14px;display:block;margin-bottom:8px;">
      <p style="text-align:center;font-size:12px;color:#a0a0a0;margin:0 0 28px;">Bu bir ön önizlemedir — siparişin sonrası 4K kalitesinde, filigransız üretilir.</p>
      {coupon_block}
      <div style="text-align:center;margin-top:28px;">
        <a href="{SITE_URL}" style="display:inline-block;background:#1a1a1a;color:#fff;text-decoration:none;padding:14px 32px;border-radius:10px;font-weight:600;font-size:14px;">Siparişini tamamla</a>
      </div>
      <p style="text-align:center;font-size:11px;color:#a0a0a0;margin-top:32px;">Visotale · Bu e-postayı bir önizleme talebiniz olduğu için aldınız.</p>
    </div>
    """


def send_preview_email(to_email: str, preview_url: str, painting_label: str, discount: dict | None) -> bool:
    if not RESEND_API_KEY:
        return False

    payload = {
        "from": RESEND_FROM,
        "to": [to_email],
        "subject": f"Tablon hazır — {painting_label} 🎨",
        "html": _build_html(preview_url, painting_label, discount),
    }
    headers = {"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"}

    try:
        r = requests.post(RESEND_API_URL, json=payload, headers=headers, timeout=10)
        return r.ok
    except requests.RequestException:
        return False


def _build_failure_html(discount: dict | None) -> str:
    coupon_block = ""
    if discount:
        coupon_block = f"""
        <div style="margin:32px 0;padding:24px;background:#f6f4f1;border-radius:14px;text-align:center;">
          <p style="margin:0 0 6px;font-size:13px;color:#8a857d;letter-spacing:.04em;text-transform:uppercase;">Özür kuponun</p>
          <p style="margin:0 0 14px;font-size:28px;font-weight:700;color:#1b3e28;letter-spacing:.02em;">%20 İNDİRİM</p>
          <p style="margin:0 0 4px;font-size:20px;font-weight:600;letter-spacing:.05em;background:#fff;display:inline-block;padding:10px 20px;border-radius:8px;border:1.5px dashed #225033;color:#1a1a1a;">{discount['code']}</p>
          <p style="margin:14px 0 0;font-size:12px;color:#8a857d;">Bu kod tek kullanımlıktır ve 7 gün geçerlidir.</p>
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
      <p style="text-align:center;font-size:11px;color:#a0a0a0;margin-top:32px;">Visotale · Bu e-postayı bir önizleme talebiniz olduğu için aldınız.</p>
    </div>
    """


def send_failure_email(to_email: str, discount: dict | None) -> bool:
    if not RESEND_API_KEY:
        return False

    payload = {
        "from": RESEND_FROM,
        "to": [to_email],
        "subject": "Tablon için biraz daha zamana ihtiyacımız var",
        "html": _build_failure_html(discount),
    }
    headers = {"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"}

    try:
        r = requests.post(RESEND_API_URL, json=payload, headers=headers, timeout=10)
        return r.ok
    except requests.RequestException:
        return False
