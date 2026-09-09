import base64
import re

from flask import Blueprint, jsonify, request, url_for

from services import supabase_edge as edge

payment_bp = Blueprint("payment", __name__)

ZENIME_CODE_PATTERN = re.compile(r"^ZN-[A-Z0-9]{6}$")

# Batas ukuran file bukti transfer yang diterima (base64 di JSON body, ~5MB
# cukup buat screenshot/foto transfer biasa tanpa bikin request kegedean).
MAX_PROOF_BASE64_CHARS = 7_000_000

# Daftar kode pembayaran Sakurupiah yang kita expose di storefront.
# Sakurupiah sendiri support lebih banyak (lihat dokumentasi API mereka),
# tapi ini yang paling relevan buat pembeli Zenime Store: QRIS (universal),
# e-wallet langsung, VA bank-bank besar, dan gerai retail.
PAYMENT_METHODS = [
    {"code": "QRIS", "label": "QRIS", "group": "QRIS", "note": "Semua e-wallet & m-banking"},
    {"code": "GOPAY", "label": "GoPay", "group": "E-Wallet"},
    {"code": "DANA", "label": "DANA", "group": "E-Wallet"},
    {"code": "ShopeePay", "label": "ShopeePay", "group": "E-Wallet"},
    {"code": "BCAVA", "label": "BCA Virtual Account", "group": "Virtual Account"},
    {"code": "BRIVA", "label": "BRI Virtual Account", "group": "Virtual Account"},
    {"code": "BNCVA", "label": "BNC Virtual Account", "group": "Virtual Account"},
    {"code": "SINARMAS", "label": "Sinarmas Virtual Account", "group": "Virtual Account"},
    {"code": "DANAMON", "label": "Danamon Virtual Account", "group": "Virtual Account"},
    {"code": "MUAMALAT", "label": "Muamalat Virtual Account", "group": "Virtual Account"},
    {"code": "BSIVA", "label": "BSI Virtual Account", "group": "Virtual Account"},
    {"code": "OCBC", "label": "OCBC Virtual Account", "group": "Virtual Account"},
    {"code": "BAGVA", "label": "BAG Virtual Account", "group": "Virtual Account"},
    {"code": "ALFAMART", "label": "Alfamart", "group": "Retail"},
    {"code": "INDOMARET", "label": "Indomaret", "group": "Retail"},
]
VALID_METHOD_CODES = {m["code"] for m in PAYMENT_METHODS}
METHOD_LABELS = {m["code"]: m["label"] for m in PAYMENT_METHODS}


@payment_bp.route("/api/packages", methods=["GET"])
def list_packages():
    try:
        packages = edge.list_packages()
    except edge.UpstreamError:
        return jsonify({"ok": False, "message": "Gagal memuat daftar paket. Coba lagi."}), 502

    return jsonify({"ok": True, "packages": packages})


@payment_bp.route("/api/coin-packages", methods=["GET"])
def list_coin_packages():
    try:
        packages = edge.list_coin_packages()
    except edge.UpstreamError:
        return jsonify({"ok": False, "message": "Gagal memuat daftar paket ZCoin. Coba lagi."}), 502

    return jsonify({"ok": True, "packages": packages})


@payment_bp.route("/api/payment-methods", methods=["GET"])
def list_payment_methods():
    return jsonify({"ok": True, "methods": PAYMENT_METHODS})


@payment_bp.route("/payment/create", methods=["POST"])
def create_payment():
    body = request.get_json(silent=True) or {}

    zenime_code = str(body.get("zenime_code", "")).strip().upper()
    package_id = str(body.get("package_id", "")).strip()
    method = str(body.get("method", "QRIS")).strip()

    # --- Validasi server-side: JANGAN percaya input mentah dari client -----
    if not zenime_code or not ZENIME_CODE_PATTERN.match(zenime_code):
        return jsonify({
            "ok": False,
            "field": "zenime_code",
            "message": "Format kode akun tidak valid. Contoh: ZN-A1B2C3",
        }), 400

    if not package_id:
        return jsonify({
            "ok": False,
            "field": "package_id",
            "message": "Pilih salah satu paket premium terlebih dahulu.",
        }), 400

    if method not in VALID_METHOD_CODES:
        return jsonify({
            "ok": False,
            "field": "method",
            "message": "Pilih metode pembayaran yang tersedia.",
        }), 400

    try:
        invoice = edge.create_invoice(zenime_code, package_id, method)
    except edge.AccountNotFoundError:
        return jsonify({
            "ok": False,
            "field": "zenime_code",
            "message": "Kode akun tidak ditemukan. Periksa lagi di Profil app Zenime.",
        }), 404
    except edge.InvalidPackageError:
        return jsonify({
            "ok": False,
            "field": "package_id",
            "message": "Paket yang dipilih tidak valid. Muat ulang halaman.",
        }), 400
    except edge.UpstreamError:
        return jsonify({
            "ok": False,
            "message": "Gagal membuat pembayaran saat ini. Coba beberapa saat lagi.",
        }), 502

    reference_id = invoice.get("reference_id")
    if not reference_id:
        return jsonify({
            "ok": False,
            "message": "Pembayaran gagal dibuat. Coba beberapa saat lagi.",
        }), 502

    return jsonify({
        "ok": True,
        "reference_id": reference_id,
        # "metode" cuma buat label tampilan di halaman /pembayaran (non-otoritatif,
        # channel yang benar-benar dipakai sudah ditentukan di request ke Sakurupiah).
        "redirect_url": url_for("main.pembayaran", reference_id=reference_id, metode=method),
    })


@payment_bp.route("/api/payment/status/<reference_id>", methods=["GET"])
def check_status(reference_id):
    try:
        data = edge.check_status(reference_id)
    except edge.InvoiceNotFoundError:
        return jsonify({"ok": False, "message": "Transaksi tidak ditemukan."}), 404
    except edge.UpstreamError:
        # Untuk polling, jangan matikan status "waiting" di client hanya karena
        # satu request gagal — cukup balas 502 dan biarkan JS coba lagi di siklus berikutnya.
        return jsonify({"ok": False, "message": "Gagal memeriksa status."}), 502

    return jsonify({
        "ok": True,
        "reference_id": data.get("reference_id", reference_id),
        "status": data.get("status", "pending"),
    })


# ---------------------------------------------------------------------------
# ZCoin — top up (pola sama persis dengan checkout Premium di atas)
# ---------------------------------------------------------------------------

@payment_bp.route("/coin-payment/create", methods=["POST"])
def create_coin_payment():
    body = request.get_json(silent=True) or {}

    zenime_code = str(body.get("zenime_code", "")).strip().upper()
    package_id = str(body.get("package_id", "")).strip()
    method = str(body.get("method", "QRIS")).strip()

    if not zenime_code or not ZENIME_CODE_PATTERN.match(zenime_code):
        return jsonify({
            "ok": False,
            "field": "zenime_code",
            "message": "Format kode akun tidak valid. Contoh: ZN-A1B2C3",
        }), 400

    if not package_id:
        return jsonify({
            "ok": False,
            "field": "package_id",
            "message": "Pilih salah satu paket ZCoin terlebih dahulu.",
        }), 400

    if method not in VALID_METHOD_CODES:
        return jsonify({
            "ok": False,
            "field": "method",
            "message": "Pilih metode pembayaran yang tersedia.",
        }), 400

    try:
        invoice = edge.create_coin_invoice(zenime_code, package_id, method)
    except edge.AccountNotFoundError:
        return jsonify({
            "ok": False,
            "field": "zenime_code",
            "message": "Kode akun tidak ditemukan. Periksa lagi di Profil app Zenime.",
        }), 404
    except edge.InvalidPackageError:
        return jsonify({
            "ok": False,
            "field": "package_id",
            "message": "Paket ZCoin yang dipilih tidak valid. Muat ulang halaman.",
        }), 400
    except edge.UpstreamError:
        return jsonify({
            "ok": False,
            "message": "Gagal membuat pembayaran saat ini. Coba beberapa saat lagi.",
        }), 502

    reference_id = invoice.get("reference_id")
    if not reference_id:
        return jsonify({
            "ok": False,
            "message": "Pembayaran gagal dibuat. Coba beberapa saat lagi.",
        }), 502

    return jsonify({
        "ok": True,
        "reference_id": reference_id,
        "redirect_url": url_for("main.coin_pembayaran", reference_id=reference_id, metode=method),
    })


@payment_bp.route("/api/coin-payment/status/<reference_id>", methods=["GET"])
def check_coin_payment_status(reference_id):
    try:
        data = edge.check_coin_status(reference_id)
    except edge.InvoiceNotFoundError:
        return jsonify({"ok": False, "message": "Transaksi tidak ditemukan."}), 404
    except edge.UpstreamError:
        return jsonify({"ok": False, "message": "Gagal memeriksa status."}), 502

    return jsonify({
        "ok": True,
        "reference_id": data.get("reference_id", reference_id),
        "status": data.get("status", "pending"),
    })


# ---------------------------------------------------------------------------
# Pembayaran manual (QRIS pribadi) — untuk pembeli luar negeri yang QRIS
# Sakurupiah-nya tidak kebaca e-wallet/bank mereka. Verifikasi dilakukan
# manual oleh admin, bukan otomatis lewat webhook.
# ---------------------------------------------------------------------------

@payment_bp.route("/api/manual-payment/create", methods=["POST"])
def create_manual_payment():
    body = request.get_json(silent=True) or {}

    zenime_code = str(body.get("zenime_code", "")).strip().upper()
    package_id = str(body.get("package_id", "")).strip()

    if not zenime_code or not ZENIME_CODE_PATTERN.match(zenime_code):
        return jsonify({
            "ok": False,
            "field": "zenime_code",
            "message": "Format kode akun tidak valid. Contoh: ZN-A1B2C3",
        }), 400

    if not package_id:
        return jsonify({
            "ok": False,
            "field": "package_id",
            "message": "Pilih salah satu paket premium terlebih dahulu.",
        }), 400

    try:
        claim = edge.create_manual_claim(zenime_code, package_id)
    except edge.AccountNotFoundError:
        return jsonify({
            "ok": False,
            "field": "zenime_code",
            "message": "Kode akun tidak ditemukan. Periksa lagi di Profil app Zenime.",
        }), 404
    except edge.InvalidPackageError:
        return jsonify({
            "ok": False,
            "field": "package_id",
            "message": "Paket yang dipilih tidak valid. Muat ulang halaman.",
        }), 400
    except edge.UpstreamError:
        return jsonify({
            "ok": False,
            "message": "Gagal membuat klaim pembayaran manual. Coba beberapa saat lagi.",
        }), 502

    claim_id = claim.get("claim_id")
    if not claim_id:
        return jsonify({
            "ok": False,
            "message": "Klaim gagal dibuat. Coba beberapa saat lagi.",
        }), 502

    return jsonify({
        "ok": True,
        "claim_id": claim_id,
        "redirect_url": url_for("main.bayar_manual_detail", claim_id=claim_id),
    })


@payment_bp.route("/api/manual-payment/upload-proof", methods=["POST"])
def upload_manual_proof():
    body = request.get_json(silent=True) or {}

    claim_id = str(body.get("claim_id", "")).strip()
    proof_base64 = str(body.get("proof_base64", ""))
    proof_filename = str(body.get("proof_filename", "bukti.jpg")).strip() or "bukti.jpg"

    if not claim_id:
        return jsonify({"ok": False, "message": "Klaim tidak ditemukan."}), 400

    if not proof_base64:
        return jsonify({
            "ok": False,
            "field": "proof",
            "message": "Upload screenshot/foto bukti transfer terlebih dahulu.",
        }), 400

    if len(proof_base64) > MAX_PROOF_BASE64_CHARS:
        return jsonify({
            "ok": False,
            "field": "proof",
            "message": "Ukuran file terlalu besar. Gunakan screenshot di bawah 5MB.",
        }), 400

    try:
        base64.b64decode(proof_base64, validate=True)
    except Exception:
        return jsonify({
            "ok": False,
            "field": "proof",
            "message": "File bukti tidak valid. Coba upload ulang.",
        }), 400

    try:
        edge.upload_manual_proof(claim_id, proof_base64, proof_filename)
    except edge.UpstreamError as exc:
        return jsonify({"ok": False, "message": str(exc) or "Gagal mengunggah bukti transfer."}), 502

    return jsonify({"ok": True})


@payment_bp.route("/api/coin-manual-payment/create", methods=["POST"])
def create_coin_manual_payment():
    body = request.get_json(silent=True) or {}

    zenime_code = str(body.get("zenime_code", "")).strip().upper()
    package_id = str(body.get("package_id", "")).strip()

    if not zenime_code or not ZENIME_CODE_PATTERN.match(zenime_code):
        return jsonify({
            "ok": False,
            "field": "zenime_code",
            "message": "Format kode akun tidak valid. Contoh: ZN-A1B2C3",
        }), 400

    if not package_id:
        return jsonify({
            "ok": False,
            "field": "package_id",
            "message": "Pilih salah satu paket ZCoin terlebih dahulu.",
        }), 400

    try:
        claim = edge.create_coin_manual_claim(zenime_code, package_id)
    except edge.AccountNotFoundError:
        return jsonify({
            "ok": False,
            "field": "zenime_code",
            "message": "Kode akun tidak ditemukan. Periksa lagi di Profil app Zenime.",
        }), 404
    except edge.InvalidPackageError:
        return jsonify({
            "ok": False,
            "field": "package_id",
            "message": "Paket ZCoin yang dipilih tidak valid. Muat ulang halaman.",
        }), 400
    except edge.UpstreamError:
        return jsonify({
            "ok": False,
            "message": "Gagal membuat klaim pembayaran manual. Coba beberapa saat lagi.",
        }), 502

    claim_id = claim.get("claim_id")
    if not claim_id:
        return jsonify({
            "ok": False,
            "message": "Klaim gagal dibuat. Coba beberapa saat lagi.",
        }), 502

    return jsonify({
        "ok": True,
        "claim_id": claim_id,
        "redirect_url": url_for("main.coin_bayar_manual_detail", claim_id=claim_id),
    })
