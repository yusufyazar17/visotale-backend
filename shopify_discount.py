"""
Visotale — Shopify Admin API ile tek seferlik indirim kodu oluşturma.

Her müşteri e-postası için: %20 indirim, tek kullanımlık (usage_limit=1,
once_per_customer=True), 7 gün geçerli — "şimdi al" baskısı için süre
sınırlı.
"""

import os
import random
import string
import time

import requests

SHOPIFY_STORE_DOMAIN = os.environ.get("SHOPIFY_STORE_DOMAIN", "")  # ör. visotale.myshopify.com
SHOPIFY_ADMIN_TOKEN = os.environ.get("SHOPIFY_ADMIN_TOKEN", "")
SHOPIFY_API_VERSION = os.environ.get("SHOPIFY_API_VERSION", "2024-10")

DISCOUNT_PERCENT = 20.0
VALID_DAYS = 7


def _headers():
    return {
        "X-Shopify-Access-Token": SHOPIFY_ADMIN_TOKEN,
        "Content-Type": "application/json",
    }


def _base_url():
    return f"https://{SHOPIFY_STORE_DOMAIN}/admin/api/{SHOPIFY_API_VERSION}"


def _random_suffix(n=6):
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=n))


def create_one_time_discount(email: str) -> dict | None:
    """
    Başarılı olursa {"code": "...", "expires_at": "..."} döndürür.
    Yapılandırma eksikse ya da Shopify hata verirse None döner — bu,
    e-posta gönderimini engellemez, sadece kupon linki olmadan gider.
    Hata sebebi Railway loglarına yazılır ("neden gitmedi" görünür olsun diye).
    """
    if not SHOPIFY_STORE_DOMAIN or not SHOPIFY_ADMIN_TOKEN:
        print("[shopify_discount] SHOPIFY_STORE_DOMAIN veya SHOPIFY_ADMIN_TOKEN eksik — kupon atlanıyor.")
        return None

    code = f"VISOTALE20-{_random_suffix()}"
    ends_at = time.strftime(
        "%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + VALID_DAYS * 86400)
    )

    price_rule_payload = {
        "price_rule": {
            "title": f"Visotale ilk sipariş — {email}",
            "target_type": "line_item",
            "target_selection": "all",
            "allocation_method": "across",
            "value_type": "percentage",
            "value": f"-{DISCOUNT_PERCENT}",
            "customer_selection": "all",
            "once_per_customer": True,
            "usage_limit": 1,
            "starts_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "ends_at": ends_at,
        }
    }

    try:
        r = requests.post(
            f"{_base_url()}/price_rules.json",
            json=price_rule_payload,
            headers=_headers(),
            timeout=10,
        )
        if not r.ok:
            print(f"[shopify_discount] price_rules.json hata döndü ({r.status_code}): {r.text[:400]}")
            return None
        price_rule_id = r.json()["price_rule"]["id"]

        r2 = requests.post(
            f"{_base_url()}/price_rules/{price_rule_id}/discount_codes.json",
            json={"discount_code": {"code": code}},
            headers=_headers(),
            timeout=10,
        )
        if not r2.ok:
            print(f"[shopify_discount] discount_codes.json hata döndü ({r2.status_code}): {r2.text[:400]}")
            return None

        print(f"[shopify_discount] Kupon oluşturuldu: {code}")
        return {"code": code, "expires_at": ends_at}
    except requests.RequestException as e:
        print(f"[shopify_discount] Shopify'a istek atılamadı: {e}")
        return None
