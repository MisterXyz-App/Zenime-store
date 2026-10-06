"""
Konfigurasi terpusat — semua nilai sensitif diambil dari environment variable,
tidak ada yang di-hardcode. Lihat .env.example untuk daftar lengkap.
"""

import os
from dotenv import load_dotenv

load_dotenv()


def _require_bool(value, default=False):
    if value is None:
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "on")


class Config:
    # --- Flask core ---------------------------------------------------------
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    FLASK_ENV = os.environ.get("FLASK_ENV", "production")
    DEBUG = _require_bool(os.environ.get("FLASK_DEBUG"), default=(FLASK_ENV == "development"))

    # --- Supabase (project & edge functions) --------------------------------
    # URL project Supabase, mis. https://xxxxx.supabase.co
    SUPABASE_URL = os.environ.get("SUPABASE_URL", "")

    # Dipakai untuk memanggil Edge Function dari server (jangan pernah expose ke client).
    SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

    # Nama Edge Function (path setelah /functions/v1/) — dibiarkan sebagai
    # config, bukan hardcoded, supaya gampang diganti tanpa ubah kode.
    SUPABASE_FN_CREATE_INVOICE = os.environ.get(
        "SUPABASE_FN_CREATE_INVOICE", "sakurupiah-create-invoice"
    )
    SUPABASE_FN_CHECK_STATUS = os.environ.get(
        "SUPABASE_FN_CHECK_STATUS", "sakurupiah-check-status"
    )
    SUPABASE_FN_LIST_PACKAGES = os.environ.get(
        "SUPABASE_FN_LIST_PACKAGES", "zenime-list-packages"
    )

    # Gateway aktif: Aulaa (QRIS). Function terpisah dari Sakurupiah --
    # dipanggil hanya kalau customer pilih metode "QRIS_AULAA" (lihat
    # routes/payment.py PAYMENT_METHODS &
    # services/supabase_edge.py create_invoice/create_coin_invoice).
    # check_status TIDAK butuh counterpart Aulaa sendiri: aulaa-check-status
    # baca RPC get_claim_full yang sama persis dengan sakurupiah-check-status
    # (generic, baca langsung dari tabel premium_claims/coin_claims), jadi
    # SUPABASE_FN_CHECK_STATUS yang lama tetap kepakai apa adanya.
    SUPABASE_FN_CREATE_INVOICE_AULAA = os.environ.get(
        "SUPABASE_FN_CREATE_INVOICE_AULAA", "aulaa-create-invoice"
    )

    # --- Donasi ("Dukung Kami" / top support, pengganti SociaBuzz) ----------
    # Lepas dari akun Zenime manapun -- lihat supabase/migrations/2026-10-06_donations.sql
    # buat skema tabel donations + RPC-nya.
    SUPABASE_FN_CREATE_DONATION_INVOICE = os.environ.get(
        "SUPABASE_FN_CREATE_DONATION_INVOICE", "aulaa-create-donation-invoice"
    )
    SUPABASE_FN_CHECK_DONATION_STATUS = os.environ.get(
        "SUPABASE_FN_CHECK_DONATION_STATUS", "aulaa-check-donation-status"
    )

    # --- ZCoin -----------------------------------------------------------
    SUPABASE_FN_LIST_COIN_PACKAGES = os.environ.get(
        "SUPABASE_FN_LIST_COIN_PACKAGES", "zenime-list-coin-packages"
    )
    # Sengaja DEFAULT-nya sama kayak function premium (sakurupiah-create-invoice /
    # sakurupiah-check-status) -- Flask kirim field tambahan "product_type":"coin"
    # di payload, jadi cukup 1 pasang Edge Function yang nge-branch di dalam
    # (bukan duplikat function baru). Kalau ternyata kamu mau pisah jadi function
    # sendiri, override env var ini ke nama function coin yang baru.
    SUPABASE_FN_CREATE_COIN_INVOICE = os.environ.get(
        "SUPABASE_FN_CREATE_COIN_INVOICE", SUPABASE_FN_CREATE_INVOICE
    )
    SUPABASE_FN_CHECK_COIN_STATUS = os.environ.get(
        "SUPABASE_FN_CHECK_COIN_STATUS", SUPABASE_FN_CHECK_STATUS
    )
    SUPABASE_FN_CREATE_COIN_INVOICE_AULAA = os.environ.get(
        "SUPABASE_FN_CREATE_COIN_INVOICE_AULAA", SUPABASE_FN_CREATE_INVOICE_AULAA
    )

    # Flow pembayaran manual (QRIS pribadi, untuk pembeli luar negeri yang
    # tidak bisa scan QRIS Sakurupiah — verifikasi dilakukan manual oleh admin).
    SUPABASE_FN_MANUAL_SUBMIT = os.environ.get(
        "SUPABASE_FN_MANUAL_SUBMIT", "manual-payment-submit"
    )
    SUPABASE_FN_MANUAL_UPLOAD_PROOF = os.environ.get(
        "SUPABASE_FN_MANUAL_UPLOAD_PROOF", "manual-payment-upload-proof"
    )
    SUPABASE_FN_MANUAL_LIST_PENDING = os.environ.get(
        "SUPABASE_FN_MANUAL_LIST_PENDING", "manual-payment-list-pending"
    )
    SUPABASE_FN_MANUAL_APPROVE = os.environ.get(
        "SUPABASE_FN_MANUAL_APPROVE", "manual-payment-approve"
    )
    SUPABASE_FN_MANUAL_REJECT = os.environ.get(
        "SUPABASE_FN_MANUAL_REJECT", "manual-payment-reject"
    )
    # OPSIONAL. Nama Edge Function yang mengembalikan riwayat klaim manual
    # (approved/rejected) buat kartu pendapatan & grafik di dashboard admin.
    # Kosong = fitur pendapatan tidak aktif, dashboard tetap jalan dengan
    # data antrean (pending) saja.
    SUPABASE_FN_MANUAL_LIST_HISTORY = os.environ.get("SUPABASE_FN_MANUAL_LIST_HISTORY", "")

    # Server-side saja, JANGAN pernah dikirim ke browser -- dipakai Flask
    # buat manggil manual-payment-list-pending / approve / reject.
    MANUAL_APPROVE_ADMIN_KEY = os.environ.get("MANUAL_APPROVE_ADMIN_KEY", "")

    # Password buat masuk /admin -- ganti lewat env var, JANGAN pakai default ini di production.
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")

    # --- HTTP client ke Edge Function ---------------------------------------
    EDGE_FUNCTION_TIMEOUT_SECONDS = float(os.environ.get("EDGE_FUNCTION_TIMEOUT_SECONDS", "12"))

    # Secret buat verifikasi signature webhook Aulaa (header x-webhook-signature,
    # HMAC-SHA256 dari raw body). Dipakai sama persis seperti Edge Function
    # aulaa-webhook sebelumnya -- diisi dengan nilai yang sama yang didaftarkan
    # di Dashboard Aulaa. Webhook diterima langsung di Flask (/webhooks/aulaa),
    # BUKAN lagi di Edge Function Supabase, biar gak kena timeout kalau VPS
    # Supabase self-host lagi gangguan koneksi masuk.
    AULAA_WEBHOOK_SECRET = os.environ.get("AULAA_WEBHOOK_SECRET", "")

    # --- GitHub Releases (cek update Zenime) --------------------------------
    # Repo tempat APK Zenime di-release. Endpoint /api/latest-release nge-
    # proxy request ke GitHub, biar app Android gak hit api.github.com
    # langsung dari device (di-hardcode karena repo-nya tetap).
    GITHUB_REPO_OWNER = "RMBLOGG"
    GITHUB_REPO_NAME = "zenime"

    # Halaman Zenime di APKPure -- ditampilkan di /download sebagai jalur
    # unduh alternatif (mirror pihak ketiga, bukan rilis resmi GitHub).
    APKPURE_URL = os.environ.get(
        "APKPURE_URL",
        "https://apkpure.com/id/zenime/com.aistudio.zenime.app",
    )

    # Personal Access Token GitHub, OPSIONAL. Kalau diisi, limit naik jadi
    # 5000/jam. TETAP lewat environment variable (bukan hardcode) karena ini
    # credential -- kalau di-hardcode, siapapun yang buka source code ini
    # (mis. kalau repo-nya public) bisa lihat token-nya.
    GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

    # --- Firebase Remote Config (maintenance mode) ---------------------------
    # Sengaja pakai project Firebase yang SAMA dengan app Android Zenime --
    # ambil 3 nilai ini dari google-services.json Zenime (atau Firebase
    # Console > Project Settings > General > Your apps > Android app):
    #   FIREBASE_PROJECT_ID = "project_id"
    #   FIREBASE_API_KEY    = client[0].api_key[0].current_key
    #   FIREBASE_APP_ID     = client[0].client_info.mobilesdk_app_id
    # BUKAN service account key -- nilai-nilai ini memang public (ikut
    # ke-bundle di APK), jadi aman dipakai langsung di sini tanpa
    # firebase-admin/credential JSON.
    FIREBASE_PROJECT_ID = os.environ.get("FIREBASE_PROJECT_ID", "")
    FIREBASE_API_KEY = os.environ.get("FIREBASE_API_KEY", "")
    FIREBASE_APP_ID = os.environ.get("FIREBASE_APP_ID", "")

    # Nama parameter Remote Config yang jadi saklar maintenance mode. Bikin
    # dulu di Firebase Console > Remote Config: parameter baru, tipe
    # Boolean, default value "false" -- set "true" & publish buat nyalain
    # maintenance (langsung kepakai tanpa perlu deploy ulang store).
    MAINTENANCE_PARAM_NAME = os.environ.get("MAINTENANCE_PARAM_NAME", "maintenance_mode")

    # Opsional: parameter String di Remote Config buat custom pesan
    # maintenance (mis. "Lagi migrasi server, balik lagi ~30 menit lagi").
    # Kalau parameter ini gak dibikin/kosong, halaman maintenance pakai
    # pesan default di template.
    MAINTENANCE_MESSAGE_PARAM_NAME = os.environ.get(
        "MAINTENANCE_MESSAGE_PARAM_NAME", "maintenance_message"
    )

    # Saklar per-metode pembayaran (Firebase Remote Config, tipe Boolean).
    # Parameter TIDAK ada / kosong = metode dianggap AKTIF (fail-open).
    # Set "false" & publish buat mematikan metode itu (berlaku Premium DAN ZCoin):
    #   PAYMENT_AUTO_PARAM_NAME   -> QRIS Otomatis (Aulaa)
    #   PAYMENT_MANUAL_PARAM_NAME -> Transfer Manual
    PAYMENT_AUTO_PARAM_NAME = os.environ.get("PAYMENT_AUTO_PARAM_NAME", "payment_auto_enabled")
    PAYMENT_MANUAL_PARAM_NAME = os.environ.get("PAYMENT_MANUAL_PARAM_NAME", "payment_manual_enabled")

    # Berapa detik hasil fetch Remote Config disimpan di memory sebelum
    # fetch ulang -- biar gak nembak Firebase di setiap request. Karena
    # Vercel serverless bisa cold start kapan aja, cache ini cuma jalan
    # efektif selama instance masih warm, tapi tetap ngurangin beban pas
    # traffic lagi rame di 1 instance yang sama.
    MAINTENANCE_CACHE_SECONDS = int(os.environ.get("MAINTENANCE_CACHE_SECONDS", "30"))

    # --- Perilaku aplikasi ---------------------------------------------------
    # Kalau True dan Supabase belum dikonfigurasi, backend pakai data paket
    # dummy supaya frontend tetap bisa dikembangkan/di-demo secara lokal.
    USE_MOCK_DATA_WHEN_UNCONFIGURED = _require_bool(
        os.environ.get("USE_MOCK_DATA_WHEN_UNCONFIGURED"), default=True
    )
