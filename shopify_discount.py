"""
Visotale — Shopify Admin API (GraphQL) ile tek seferlik indirim kodu oluşturma.

Her müşteri e-postası için: %20 indirim, tek kullanımlık (usageLimit=1),
7 gün geçerli — "şimdi al" baskısı için süre sınırlı.

NOT: Eski REST price_rules.json endpoint'i yerine GraphQL kullanıyoruz —
Shopify indirimler tarafını GraphQL'e taşıdı, ve bu yöntem write_discounts/
read_discounts izinleriyle (write_price_rules'a gerek kalmadan) çalışıyor.
"""

import os
import random
import string
import time

import requests

import shopify_auth

SHOPIFY_STORE_DOMAIN = os.environ.get("SHOPIFY_STORE_DOMAIN", "")  # ör. visotale.myshopify.com
SHOPIFY_API_VERSION = os.environ.get("SHOPIFY_API_VERSION", "2024-10")

DISCOUNT_PERCENT = 20.0
VALID_DAYS = 1  # 24 saat — mail metnindeki aciliyet mesajıyla birebir eşleşmeli

MUTATION = """
mutation discountCodeBasicCreate($basicCodeDiscount: DiscountCodeBasicInput!) {
  discountCodeBasicCreate(basicCodeDiscount: $basicCodeDiscount) {
    codeDiscountNode {
      id
      codeDiscount {
        ... on DiscountCodeBasic {
          codes(first: 1) { nodes { code } }
        }
      }
    }
    userErrors { field message }
  }
}
"""


def _graphql_url():
    return f"https://{SHOPIFY_STORE_DOMAIN}/admin/api/{SHOPIFY_API_VERSION}/graphql.json"


def _headers(token):
    return {
        "X-Shopify-Access-Token": token,
        "Content-Type": "application/json",
    }


def _random_suffix(n=6):
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=n))


def create_one_time_discount(email: str) -> dict | None:
    """
    Başarılı olursa {"code": "...", "expires_at": "..."} döndürür.
    Yapılandırma eksikse ya da Shopify hata verirse None döner — bu,
    e-posta gönderimini engellemez, sadece kupon linki olmadan gider.
    Hata sebebi Railway loglarına yazılır ("neden gitmedi" görünür olsun diye).
    """
    token = shopify_auth.get_access_token()
    if not token:
        print("[shopify_discount] Geçerli bir Admin API token alınamadı — kupon atlanıyor.")
        return None

    code = f"VISOTALE20-{_random_suffix()}"
    now = time.gmtime()
    ends_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + VALID_DAYS * 86400))
    starts_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", now)

    variables = {
        "basicCodeDiscount": {
            "title": f"Visotale ilk sipariş — {email}",
            "code": code,
            "startsAt": starts_at,
            "endsAt": ends_at,
            "customerSelection": {"all": True},
            "customerGets": {
                "value": {"percentage": DISCOUNT_PERCENT / 100},
                "items": {"all": True},
            },
            "appliesOncePerCustomer": True,
            "usageLimit": 1,
        }
    }

    try:
        r = requests.post(
            _graphql_url(),
            json={"query": MUTATION, "variables": variables},
            headers=_headers(token),
            timeout=10,
        )
        if not r.ok:
            print(f"[shopify_discount] GraphQL isteği hata döndü ({r.status_code}): {r.text[:400]}")
            return None

        data = r.json()
        if "errors" in data:
            print(f"[shopify_discount] GraphQL hatası: {data['errors']}")
            return None

        result = data.get("data", {}).get("discountCodeBasicCreate", {})
        user_errors = result.get("userErrors") or []
        if user_errors:
            print(f"[shopify_discount] Shopify indirim oluşturamadı: {user_errors}")
            return None

        node = result.get("codeDiscountNode")
        if not node:
            print(f"[shopify_discount] Beklenmeyen yanıt şekli: {data}")
            return None

        print(f"[shopify_discount] Kupon oluşturuldu: {code}")
        return {"code": code, "expires_at": ends_at}
    except requests.RequestException as e:
        print(f"[shopify_discount] Shopify'a istek atılamadı: {e}")
        return None
