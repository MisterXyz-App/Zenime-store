"""
Lapisan service untuk memanggil Supabase Edge Function.

PENTING: Flask TIDAK pernah menyimpan/menghitung signature atau API key
Sakurupiah secara langsung. Semua itu ditangani di dalam Edge Function
`sakurupiah-create-invoice` / `sakurupiah-check-status` di sisi Supabase.
Modul ini hanya jadi jembatan HTTP yang tipis + validasi & error handling.
"""

import time
import uuid
import requests
from flask import current_app


class UpstreamError(Exception):
    """Error umum saat memanggil Edge Function (timeout, 5xx, koneksi putus, dll)."""


class AccountNotFoundError(Exception):
    """Kode akun Zenime tidak ditemukan / tidak valid di sisi backend."""


class InvalidPackageError(Exception):
    """package_id yang dikirim tidak dikenali di sisi backend."""


class InvoiceNotFoundError(Exception):
    """reference_id transaksi tidak ditemukan saat cek status."""


def _edge_function_url(function_name: str) -> str:
    base = current_app.config["SUPABASE_URL"].rstrip("/")
    return f"{base}/functions/v1/{function_name}"


def _edge_headers() -> dict:
    service_key = current_app.config["SUPABASE_SERVICE_ROLE_KEY"]
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {service_key}",
        "apikey": service_key,
    }


def _admin_headers() -> dict:
    """Header buat Edge Function yang diproteksi x-admin-key (manual-payment-list-pending/approve/reject)."""
    headers = _edge_headers()
    headers["x-admin-key"] = current_app.config["MANUAL_APPROVE_ADMIN_KEY"]
    return headers


def _is_configured() -> bool:
    return bool(current_app.config["SUPABASE_URL"] and current_app.config["SUPABASE_SERVICE_ROLE_KEY"])


def _post(function_name: str, payload: dict) -> dict:
    """POST tipis ke Edge Function dengan timeout & error handling seragam."""
    url = _edge_function_url(function_name)
    timeout = current_app.config["EDGE_FUNCTION_TIMEOUT_SECONDS"]

    try:
        response = requests.post(url, json=payload, headers=_edge_headers(), timeout=timeout)
    except requests.Timeout as exc:
        raise UpstreamError(f"Timeout saat menghubungi {function_name}") from exc
    except requests.RequestException as exc:
        raise UpstreamError(f"Gagal menghubungi {function_name}: {exc}") from exc

    if response.status_code >= 500:
        raise UpstreamError(f"{function_name} mengembalikan error server ({response.status_code})")

    try:
        data = response.json()
    except ValueError as exc:
        raise UpstreamError(f"Respons {function_name} bukan JSON yang valid") from exc

    if response.status_code == 404:
        raise InvoiceNotFoundError(data.get("message", "Data tidak ditemukan"))

    if response.status_code >= 400:
        # Edge Function diharapkan mengirim { "error_code": "...", "message": "..." }
        error_code = data.get("error_code", "")
        message = data.get("message", "Permintaan ditolak")

        if error_code == "account_not_found":
            raise AccountNotFoundError(message)
        if error_code == "invalid_package":
            raise InvalidPackageError(message)

        raise UpstreamError(message)

    return data


def _get(function_name: str, params: dict | None = None) -> dict:
    url = _edge_function_url(function_name)
    timeout = current_app.config["EDGE_FUNCTION_TIMEOUT_SECONDS"]

    try:
        response = requests.get(url, params=params or {}, headers=_edge_headers(), timeout=timeout)
    except requests.Timeout as exc:
        raise UpstreamError(f"Timeout saat menghubungi {function_name}") from exc
    except requests.RequestException as exc:
        raise UpstreamError(f"Gagal menghubungi {function_name}: {exc}") from exc

    if response.status_code >= 500:
        raise UpstreamError(f"{function_name} mengembalikan error server ({response.status_code})")

    try:
        data = response.json()
    except ValueError as exc:
        raise UpstreamError(f"Respons {function_name} bukan JSON yang valid") from exc

    if response.status_code == 404:
        raise InvoiceNotFoundError(data.get("message", "Data tidak ditemukan"))

    if response.status_code >= 400:
        raise UpstreamError(data.get("message", "Permintaan ditolak"))

    return data


# ---------------------------------------------------------------------------
# Daftar paket
# ---------------------------------------------------------------------------

_MOCK_PACKAGES = [
    {"id": "pkg_1m", "label": "1 Bulan", "duration_text": "1 bulan", "price": 15000, "badge": None},
    {"id": "pkg_3m", "label": "3 Bulan", "duration_text": "3 bulan", "price": 40000, "badge": "Hemat"},
    {"id": "pkg_12m", "label": "1 Tahun", "duration_text": "12 bulan", "price": 140000, "badge": "Paling Populer"},
]


def list_packages() -> list[dict]:
    """
    Ambil daftar paket premium. Sumber kebenaran ada di Supabase (lewat
    Edge Function `zenime-list-packages` yang membaca tabel paket), BUKAN
    hardcode di sini. Selama kredensial Supabase belum diisi, fallback ke
    data mock supaya frontend tetap bisa dikembangkan secara lokal.
    """
    if not _is_configured():
        if current_app.config["USE_MOCK_DATA_WHEN_UNCONFIGURED"]:
            return _MOCK_PACKAGES
        raise UpstreamError("Supabase belum dikonfigurasi")

    data = _get(current_app.config["SUPABASE_FN_LIST_PACKAGES"])
    return data.get("packages", [])


def get_package_by_id(package_id: str) -> dict | None:
    for pkg in list_packages():
        if pkg["id"] == package_id:
            return pkg
    return None


# ---------------------------------------------------------------------------
# Invoice (create) — proxy ke sakurupiah-create-invoice
# ---------------------------------------------------------------------------

def create_invoice(zenime_code: str, package_id: str, method: str = "QRIS") -> dict:
    """
    Minta Edge Function `sakurupiah-create-invoice` membuat invoice.
    Edge Function yang menangani signature Sakurupiah, verifikasi kode akun
    ke tabel user, dan penyimpanan record transaksi.

    `method` adalah kode channel pembayaran Sakurupiah (QRIS, GOPAY, DANA,
    BCAVA, dll — lihat routes/payment.py PAYMENT_METHODS untuk daftar yang
    kita expose). Default QRIS biar backward-compatible kalau caller lama
    belum kirim method.

    Return dict diharapkan berisi minimal:
      reference_id, amount, qr_image (data URI/URL) atau checkout_url,
      package_label, zenime_code, created_at, expires_at
    """
    package = get_package_by_id(package_id)
    if package is None:
        raise InvalidPackageError("Paket yang dipilih tidak valid")

    if not _is_configured():
        if not current_app.config["USE_MOCK_DATA_WHEN_UNCONFIGURED"]:
            raise UpstreamError("Supabase belum dikonfigurasi")
        return _mock_create_invoice(zenime_code, package)

    payload = {"zenime_code": zenime_code, "package_id": package_id, "method": method}
    data = _post(current_app.config["SUPABASE_FN_CREATE_INVOICE"], payload)
    return data


def _mock_create_invoice(zenime_code: str, package: dict) -> dict:
    """Dipakai hanya saat SUPABASE_URL/SERVICE_ROLE_KEY belum diisi (mode dev lokal)."""
    reference_id = f"ZS-{uuid.uuid4().hex[:10].upper()}"
    now = time.time()
    return {
        "reference_id": reference_id,
        "amount": package["price"],
        "package_id": package["id"],
        "package_label": package["label"],
        "zenime_code": zenime_code,
        "qr_image": None,  # isi dengan data URI QR asli setelah Edge Function tersambung
        "checkout_url": None,
        "status": "pending",
        "created_at": now,
        "expires_at": now + 15 * 60,
    }


# ---------------------------------------------------------------------------
# Status pembayaran — proxy ke sakurupiah-check-status
# ---------------------------------------------------------------------------

def check_status(reference_id: str) -> dict:
    """
    Cek status transaksi berdasarkan reference_id. Return dict diharapkan
    berisi minimal: reference_id, status ("pending" | "paid"/"berhasil" |
    "expired" | "failed"), amount, package_label, zenime_code, dan
    premium_until bila sudah berhasil.
    """
    if not _is_configured():
        if not current_app.config["USE_MOCK_DATA_WHEN_UNCONFIGURED"]:
            raise UpstreamError("Supabase belum dikonfigurasi")
        return _mock_check_status(reference_id)

    data = _get(current_app.config["SUPABASE_FN_CHECK_STATUS"], params={"reference_id": reference_id})
    return data


def _mock_check_status(reference_id: str) -> dict:
    """Mode dev lokal: status tetap 'pending' — sambungkan Edge Function asli untuk hasil nyata."""
    return {
        "reference_id": reference_id,
        "status": "pending",
        "amount": 0,
        "package_label": "—",
        "zenime_code": "—",
        "premium_until": None,
    }


# ---------------------------------------------------------------------------
# Pembayaran manual (QRIS pribadi) — untuk pembeli luar negeri yang tidak
# bisa scan QRIS Sakurupiah. Dua langkah: buat klaim dulu (dapat nominal
# unik buat dicocokkan di mutasi), baru upload bukti transfer setelah bayar.
# Status transaksi tetap dicek lewat check_status() di atas (fungsi yang
# sama dipakai flow Sakurupiah) karena baris klaimnya ada di tabel yang sama.
# ---------------------------------------------------------------------------

def create_manual_claim(zenime_code: str, package_id: str) -> dict:
    """
    Buat klaim pembayaran manual lewat Edge Function `manual-payment-submit`.
    Return dict berisi: claim_id, merchant_ref, package_label, zenime_code,
    unique_amount, expires_at.
    """
    package = get_package_by_id(package_id)
    if package is None:
        raise InvalidPackageError("Paket yang dipilih tidak valid")

    if not _is_configured():
        if not current_app.config["USE_MOCK_DATA_WHEN_UNCONFIGURED"]:
            raise UpstreamError("Supabase belum dikonfigurasi")
        return _mock_create_manual_claim(zenime_code, package)

    payload = {"zenime_code": zenime_code, "package_id": package_id}
    data = _post(current_app.config["SUPABASE_FN_MANUAL_SUBMIT"], payload)
    return data


def _mock_create_manual_claim(zenime_code: str, package: dict) -> dict:
    claim_id = f"mock-{uuid.uuid4().hex[:10]}"
    return {
        "claim_id": claim_id,
        "merchant_ref": f"ZNM-MOCK-{uuid.uuid4().hex[:6]}",
        "package_label": package["label"],
        "zenime_code": zenime_code,
        "unique_amount": package["price"] + 123,
        "expires_at": None,
    }


def upload_manual_proof(claim_id: str, proof_base64: str, proof_filename: str) -> dict:
    """Upload bukti transfer untuk klaim manual yang sudah dibuat sebelumnya."""
    if not _is_configured():
        if not current_app.config["USE_MOCK_DATA_WHEN_UNCONFIGURED"]:
            raise UpstreamError("Supabase belum dikonfigurasi")
        return {"success": True}

    payload = {
        "claim_id": claim_id,
        "proof_base64": proof_base64,
        "proof_filename": proof_filename,
    }
    data = _post(current_app.config["SUPABASE_FN_MANUAL_UPLOAD_PROOF"], payload)
    return data


# ---------------------------------------------------------------------------
# Admin: lihat & proses klaim manual (halaman /admin/manual-payments).
# Dipisah dari _post() karena butuh header x-admin-key, bukan cuma
# Authorization service-role.
# ---------------------------------------------------------------------------

def list_pending_manual_claims() -> list:
    if not _is_configured():
        return []

    url = _edge_function_url(current_app.config["SUPABASE_FN_MANUAL_LIST_PENDING"])
    timeout = current_app.config["EDGE_FUNCTION_TIMEOUT_SECONDS"]

    try:
        response = requests.get(url, headers=_admin_headers(), timeout=timeout)
    except requests.RequestException as exc:
        raise UpstreamError(f"Gagal menghubungi daftar klaim manual: {exc}") from exc

    if response.status_code >= 400:
        raise UpstreamError(f"Gagal mengambil daftar klaim manual (HTTP {response.status_code})")

    return response.json().get("claims", [])


def approve_manual_claim(claim_id: str) -> dict:
    return _admin_post(current_app.config["SUPABASE_FN_MANUAL_APPROVE"], {"claim_id": claim_id})


def reject_manual_claim(claim_id: str) -> dict:
    return _admin_post(current_app.config["SUPABASE_FN_MANUAL_REJECT"], {"claim_id": claim_id})


def _admin_post(function_name: str, payload: dict) -> dict:
    url = _edge_function_url(function_name)
    timeout = current_app.config["EDGE_FUNCTION_TIMEOUT_SECONDS"]

    try:
        response = requests.post(url, json=payload, headers=_admin_headers(), timeout=timeout)
    except requests.RequestException as exc:
        raise UpstreamError(f"Gagal menghubungi {function_name}: {exc}") from exc

    if response.status_code >= 400:
        try:
            message = response.json().get("message", f"HTTP {response.status_code}")
        except ValueError:
            message = f"HTTP {response.status_code}"
        raise UpstreamError(message)

    return response.json()
