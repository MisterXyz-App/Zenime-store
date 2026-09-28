"""
Ambil status maintenance mode dari Firebase Remote Config -- pakai project
Firebase yang SAMA dengan app Android Zenime, biar 1 toggle di Firebase
Console (Remote Config) langsung ngefek ke Android & storefront ini
bersamaan.

Sengaja cuma manggil REST API publik `firebase:fetch` (yang sama dipakai
Remote Config Web SDK) pakai `appInstanceId` statis, BUKAN firebase-admin
SDK. Ini artinya: gak butuh service account / credential JSON sama sekali
-- cukup FIREBASE_PROJECT_ID, FIREBASE_API_KEY, FIREBASE_APP_ID (3 nilai
public yang sama kayak di google-services.json Zenime).

Konsekuensi dari pendekatan ini: fetch selalu ngembaliin SEMUA parameter
Remote Config apa adanya (gak ada evaluasi kondisi/percentage rollout
per-device, karena appInstanceId-nya bukan device asli) -- cocok banget
buat kasus simpel kayak maintenance flag yang sama buat semua orang.
"""

import logging
import time

import requests
from flask import current_app

logger = logging.getLogger(__name__)

# Cache in-memory per-process (per warm Vercel instance). Disengaja
# module-level supaya kepakai bareng lintas request selama instance masih
# hidup, bukan di-reset tiap request.
_cache = {"entries": None, "expires_at": 0.0}


def _fetch_template() -> dict:
    project_id = current_app.config["FIREBASE_PROJECT_ID"]
    api_key = current_app.config["FIREBASE_API_KEY"]
    app_id = current_app.config["FIREBASE_APP_ID"]

    url = (
        f"https://firebaseremoteconfig.googleapis.com/v1/projects/"
        f"{project_id}/namespaces/firebase:fetch?key={api_key}"
    )
    payload = {
        # ID instance statis -- gak perlu registrasi Firebase Installations
        # asli, karena kita cuma butuh nilai parameter apa adanya (tanpa
        # targeting per-device/percentage rollout).
        "appId": app_id,
        "appInstanceId": "zenime-store-server",
    }
    timeout = current_app.config.get("EDGE_FUNCTION_TIMEOUT_SECONDS", 12)

    resp = requests.post(url, json=payload, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    return data.get("entries", {}) or {}


def _get_entries() -> dict:
    """Entries Remote Config, di-cache MAINTENANCE_CACHE_SECONDS detik.

    Kalau fetch gagal (Firebase down, API key salah, dsb), fail-OPEN:
    pakai cache lama kalau ada (stale-but-served), atau dict kosong kalau
    belum pernah berhasil fetch sama sekali -- supaya gangguan di Firebase
    gak ikut nge-down-in seluruh store. Tetap nge-set expires_at biar gak
    nembak ulang di SETIAP request pas lagi ada gangguan.
    """
    now = time.time()
    if _cache["entries"] is not None and now < _cache["expires_at"]:
        return _cache["entries"]

    if not current_app.config.get("FIREBASE_PROJECT_ID") or not current_app.config.get(
        "FIREBASE_API_KEY"
    ):
        return {}

    ttl = current_app.config.get("MAINTENANCE_CACHE_SECONDS", 30)
    try:
        entries = _fetch_template()
    except Exception:
        logger.exception("Gagal fetch Firebase Remote Config, anggap bukan maintenance")
        entries = _cache["entries"] if _cache["entries"] is not None else {}

    _cache["entries"] = entries
    _cache["expires_at"] = now + ttl
    return entries


def is_maintenance_mode() -> bool:
    param_name = current_app.config.get("MAINTENANCE_PARAM_NAME", "maintenance_mode")
    raw = str(_get_entries().get(param_name, "false")).strip().lower()
    return raw in ("true", "1", "yes", "on")


def get_maintenance_message():
    """Pesan custom dari Remote Config, atau None kalau parameter-nya
    gak diisi -- biar template pakai pesan default."""
    param_name = current_app.config.get(
        "MAINTENANCE_MESSAGE_PARAM_NAME", "maintenance_message"
    )
    message = _get_entries().get(param_name)
    return message.strip() if isinstance(message, str) and message.strip() else None


def is_payment_enabled(kind: str) -> bool:
    """Apakah metode pembayaran `kind` ("auto" atau "manual") aktif.

    Sumbernya parameter Remote Config PAYMENT_AUTO_PARAM_NAME /
    PAYMENT_MANUAL_PARAM_NAME. Fail-open: parameter belum dibikin, kosong,
    atau Firebase gagal di-fetch -> dianggap AKTIF. Cuma nilai eksplisit
    false/0/no/off yang mematikan metode.
    """
    key = "PAYMENT_AUTO_PARAM_NAME" if kind == "auto" else "PAYMENT_MANUAL_PARAM_NAME"
    default = "payment_auto_enabled" if kind == "auto" else "payment_manual_enabled"
    param_name = current_app.config.get(key, default)
    raw = _get_entries().get(param_name)
    if raw is None:
        return True
    return str(raw).strip().lower() not in ("false", "0", "no", "off")


def payment_options() -> dict:
    return {"auto": is_payment_enabled("auto"), "manual": is_payment_enabled("manual")}
