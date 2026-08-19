import re

from flask import Blueprint, jsonify, request, url_for

from services import supabase_edge as edge

payment_bp = Blueprint("payment", __name__)

ZENIME_CODE_PATTERN = re.compile(r"^ZN-[A-Z0-9]{6}$")


@payment_bp.route("/api/packages", methods=["GET"])
def list_packages():
    try:
        packages = edge.list_packages()
    except edge.UpstreamError:
        return jsonify({"ok": False, "message": "Gagal memuat daftar paket. Coba lagi."}), 502

    return jsonify({"ok": True, "packages": packages})


@payment_bp.route("/payment/create", methods=["POST"])
def create_payment():
    body = request.get_json(silent=True) or {}

    zenime_code = str(body.get("zenime_code", "")).strip().upper()
    package_id = str(body.get("package_id", "")).strip()

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

    try:
        invoice = edge.create_invoice(zenime_code, package_id)
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
        "redirect_url": url_for("main.pembayaran", reference_id=reference_id),
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
