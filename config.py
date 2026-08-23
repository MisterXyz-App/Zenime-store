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

    # --- HTTP client ke Edge Function ---------------------------------------
    EDGE_FUNCTION_TIMEOUT_SECONDS = float(os.environ.get("EDGE_FUNCTION_TIMEOUT_SECONDS", "12"))

    # --- GitHub Releases (cek update Zenime) --------------------------------
    # Repo tempat APK Zenime di-release. Endpoint /api/latest-release nge-
    # proxy request ke GitHub, biar app Android gak hit api.github.com
    # langsung dari device (di-hardcode karena repo-nya tetap).
    GITHUB_REPO_OWNER = "RMBLOGG"
    GITHUB_REPO_NAME = "zenime"

    # Personal Access Token GitHub, OPSIONAL. Kalau diisi, limit naik jadi
    # 5000/jam. TETAP lewat environment variable (bukan hardcode) karena ini
    # credential -- kalau di-hardcode, siapapun yang buka source code ini
    # (mis. kalau repo-nya public) bisa lihat token-nya.
    GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

    # --- Perilaku aplikasi ---------------------------------------------------
    # Kalau True dan Supabase belum dikonfigurasi, backend pakai data paket
    # dummy supaya frontend tetap bisa dikembangkan/di-demo secara lokal.
    USE_MOCK_DATA_WHEN_UNCONFIGURED = _require_bool(
        os.environ.get("USE_MOCK_DATA_WHEN_UNCONFIGURED"), default=True
    )
