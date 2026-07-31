"""
Visotale — Shopify Admin API token'ını OAuth client_credentials akışıyla al.

Dev Dashboard'da oluşturulan custom app'ler için Shopify artık sabit bir
Admin API token göstermiyor — Client ID + Client Secret ile programatik
olarak token istemen gerekiyor (bkz. Shopify destek yanıtı). Token'ın bir
süresi (expires_in) olduğu için burada basit bir bellek-içi önbellek
tutuyoruz, her istekte yeniden almak yerine süresi dolunca yeniliyoruz.
"""

import os
import time

import requests

SHOPIFY_STORE_DOMAIN = os.environ.get("SHOPIFY_STORE_DOMAIN", "")  # ör. visotale.myshopify.com
SHOPIFY_CLIENT_ID = os.environ.get("SHOPIFY_CLIENT_ID", "")
SHOPIFY_CLIENT_SECRET = os.environ.get("SHOPIFY_CLIENT_SECRET", "")

_cache = {"token": None, "expires_at": 0}


def get_access_token() -> str | None:
    """Geçerli bir Admin API access token döner (gerekirse yeniler).
    Yapılandırma eksikse ya da Shopify hata verirse None döner."""
    if not SHOPIFY_STORE_DOMAIN or not SHOPIFY_CLIENT_ID or not SHOPIFY_CLIENT_SECRET:
        print("[shopify_auth] SHOPIFY_STORE_DOMAIN/CLIENT_ID/CLIENT_SECRET eksik.")
        return None

    # önbellekte hâlâ geçerli bir token varsa (60sn pay bırakarak) onu kullan
    if _cache["token"] and time.time() < _cache["expires_at"] - 60:
        return _cache["token"]

    url = f"https://{SHOPIFY_STORE_DOMAIN}/admin/oauth/access_token"
    payload = {
        "client_id": SHOPIFY_CLIENT_ID,
        "client_secret": SHOPIFY_CLIENT_SECRET,
        "grant_type": "client_credentials",
    }

    try:
        r = requests.post(url, json=payload, timeout=10)
        if not r.ok:
            print(f"[shopify_auth] Token isteği hata döndü ({r.status_code}): {r.text[:400]}")
            return None
        data = r.json()
        token = data.get("access_token")
        expires_in = data.get("expires_in", 3600)
        if not token:
            print(f"[shopify_auth] Beklenmeyen yanıt: {data}")
            return None
        _cache["token"] = token
        _cache["expires_at"] = time.time() + expires_in
        print("[shopify_auth] Yeni Admin API token alındı.")
        return token
    except requests.RequestException as e:
        print(f"[shopify_auth] Token isteği atılamadı: {e}")
        return None
