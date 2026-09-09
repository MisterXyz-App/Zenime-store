from datetime import datetime, timezone

from flask import Blueprint, render_template, abort, jsonify, request

from services import supabase_edge as edge
from services import github_release
from routes.payment import METHOD_LABELS

main_bp = Blueprint("main", __name__)


def _fmt_dt(value) -> str:
    """Terima epoch (float/int) atau string ISO dari Edge Function, kembalikan
    string yang enak dibaca. Kalau kosong, tampilkan tanda strip."""
    if not value:
        return "—"
    try:
        if isinstance(value, (int, float)):
            dt = datetime.fromtimestamp(value, tz=timezone.utc)
        else:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt.strftime("%d %b %Y, %H:%M UTC")
    except (ValueError, TypeError):
        return str(value)


@main_bp.route("/")
def index():
    return render_template("index.html")


@main_bp.route("/privacy-policy")
def privacy_policy():
    return render_template("privacy_policy.html")


@main_bp.route("/beli-premium")
def beli_premium():
    # Dipanggil dari tombol "Bayar Sekarang" di app Android dengan query
    # param ?code=...&package_id=..., biar form di sini otomatis ke-prefill
    # (kode akun + paket) tanpa user perlu copy-paste/pilih manual lagi.
    # Nilainya cuma dipakai buat prefill tampilan -- validasi kode & paket
    # yang sebenarnya tetap dilakukan ulang di JS (format) dan Edge Function
    # create_premium_claim (keberadaan akun/paket) pas submit, jadi query
    # param ini gak bisa dipakai buat nembus validasi.
    prefill_code = (request.args.get("code") or "").strip().upper()
    prefill_package_id = (request.args.get("package_id") or "").strip()
    return render_template(
        "beli.html",
        prefill_code=prefill_code,
        prefill_package_id=prefill_package_id,
    )


@main_bp.route("/bayar-manual")
def bayar_manual():
    # Halaman buat pembeli luar negeri (mis. Malaysia) yang QRIS Sakurupiah-nya
    # tidak kebaca e-wallet/bank mereka -- bayar pakai QRIS pribadi merchant,
    # diverifikasi manual oleh admin (bukan otomatis lewat webhook).
    prefill_code = (request.args.get("code") or "").strip().upper()
    prefill_package_id = (request.args.get("package_id") or "").strip()
    return render_template(
        "bayar_manual.html",
        prefill_code=prefill_code,
        prefill_package_id=prefill_package_id,
    )


@main_bp.route("/top-up-coin")
def top_up_coin():
    # Dipanggil dari tombol "Bayar Sekarang" di layar ZCoin app Android dengan
    # query param ?code=...&package_id=... -- sama pola-nya kayak /beli-premium.
    prefill_code = (request.args.get("code") or "").strip().upper()
    prefill_package_id = (request.args.get("package_id") or "").strip()
    return render_template(
        "top_up_coin.html",
        prefill_code=prefill_code,
        prefill_package_id=prefill_package_id,
    )


@main_bp.route("/bayar-manual/<claim_id>")
def bayar_manual_detail(claim_id):
    # Sama seperti /pembayaran/<reference_id> (klaim manual disimpan di
    # tabel premium_claims yang sama), jadi status pembayaran/aktivasinya
    # dicek pakai edge function check-status yang sama.
    try:
        data = edge.check_status(claim_id)
    except edge.InvoiceNotFoundError:
        abort(404)
    except edge.UpstreamError:
        abort(500)

    payment = {
        "reference_id": data.get("reference_id", claim_id),
        "amount": data.get("amount", 0),
        "package_label": data.get("package_label", "—"),
        "zenime_code": data.get("zenime_code", "—"),
        "status": (data.get("status") or "pending").lower(),
        "created_at": _fmt_dt(data.get("created_at")),
        "expires_at": _fmt_dt(data.get("expires_at")),
    }
    return render_template("pembayaran_manual.html", payment=payment)


@main_bp.route("/coin-bayar-manual")
def coin_bayar_manual():
    # Versi ZCoin dari /bayar-manual -- buat pembeli luar negeri yang QRIS
    # Sakurupiah-nya gak kebaca e-wallet/bank mereka.
    prefill_code = (request.args.get("code") or "").strip().upper()
    prefill_package_id = (request.args.get("package_id") or "").strip()
    return render_template(
        "coin_bayar_manual.html",
        prefill_code=prefill_code,
        prefill_package_id=prefill_package_id,
    )


@main_bp.route("/coin-bayar-manual/<claim_id>")
def coin_bayar_manual_detail(claim_id):
    try:
        data = edge.check_coin_status(claim_id)
    except edge.InvoiceNotFoundError:
        abort(404)
    except edge.UpstreamError:
        abort(500)

    payment = {
        "reference_id": data.get("reference_id", claim_id),
        "amount": data.get("amount", 0),
        "package_label": data.get("package_label", "—"),
        "zenime_code": data.get("zenime_code", "—"),
        "coin_amount": data.get("coin_amount", 0),
        "status": (data.get("status") or "pending").lower(),
        "created_at": _fmt_dt(data.get("created_at")),
        "expires_at": _fmt_dt(data.get("expires_at")),
    }
    return render_template("coin_pembayaran_manual.html", payment=payment)


@main_bp.route("/pembayaran/<reference_id>")
def pembayaran(reference_id):
    try:
        data = edge.check_status(reference_id)
    except edge.InvoiceNotFoundError:
        abort(404)
    except edge.UpstreamError:
        abort(500)

    # "metode" cuma dipakai buat label tampilan (dikirim dari routes/payment.py
    # saat redirect abis create invoice) -- channel yang benar-benar dipakai
    # sudah ditentukan duluan di request ke Sakurupiah, jadi query param ini
    # gak bisa dipakai buat nembus/ubah channel pembayaran yang sebenarnya.
    metode = (request.args.get("metode") or "QRIS").strip()
    method_label = METHOD_LABELS.get(metode, metode)

    # Kalau transaksi ini ternyata sudah selesai (paid/expired/failed),
    # tidak relevan lagi ditampilkan sebagai halaman "menunggu pembayaran".
    status = (data.get("status") or "").lower()
    if status in ("paid", "berhasil", "expired", "failed", "gagal"):
        return render_template(
            "payment.html",
            payment={
                "reference_id": data.get("reference_id", reference_id),
                "amount": data.get("amount", 0),
                "qr_image": data.get("qr_image"),
                "checkout_url": data.get("checkout_url"),
                "package_label": data.get("package_label", "—"),
                "zenime_code": data.get("zenime_code", "—"),
                "method_label": method_label,
                "created_at": _fmt_dt(data.get("created_at")),
                "expires_at": _fmt_dt(data.get("expires_at")),
            },
        )

    payment = {
        "reference_id": data.get("reference_id", reference_id),
        "amount": data.get("amount", 0),
        "qr_image": data.get("qr_image"),
        "checkout_url": data.get("checkout_url"),
        "package_label": data.get("package_label", "—"),
        "zenime_code": data.get("zenime_code", "—"),
        "method_label": method_label,
        "created_at": _fmt_dt(data.get("created_at")),
        "expires_at": _fmt_dt(data.get("expires_at")),
    }
    return render_template("payment.html", payment=payment)


@main_bp.route("/coin-pembayaran/<reference_id>")
def coin_pembayaran(reference_id):
    try:
        data = edge.check_coin_status(reference_id)
    except edge.InvoiceNotFoundError:
        abort(404)
    except edge.UpstreamError:
        abort(500)

    metode = (request.args.get("metode") or "QRIS").strip()
    method_label = METHOD_LABELS.get(metode, metode)

    payment = {
        "reference_id": data.get("reference_id", reference_id),
        "amount": data.get("amount", 0),
        "qr_image": data.get("qr_image"),
        "checkout_url": data.get("checkout_url"),
        "package_label": data.get("package_label", "—"),
        "coin_amount": data.get("coin_amount", 0),
        "zenime_code": data.get("zenime_code", "—"),
        "method_label": method_label,
        "created_at": _fmt_dt(data.get("created_at")),
        "expires_at": _fmt_dt(data.get("expires_at")),
    }
    return render_template("coin_payment.html", payment=payment)


@main_bp.route("/api/latest-release")
def latest_release():
    """
    Dipanggil dari app Android Zenime (GithubUpdateChecker) buat cek update,
    GANTI dari hit api.github.com langsung -- server ini yang nge-hit GitHub,
    jadi bukan tiap device Android yang kena rate limit GitHub sendiri-sendiri.

    Response kalau ada release: {"tag_name", "download_url", "body"}
    Response kalau belum ada release / gagal fetch: {"tag_name": null}
    (selalu HTTP 200 -- app Android tinggal cek tag_name kosong atau enggak,
    gak perlu bedain kasus network vs "memang belum ada release").
    """
    try:
        data = github_release.get_latest_release()
    except github_release.UpstreamError:
        return jsonify({"tag_name": None})

    if data is None:
        return jsonify({"tag_name": None})

    return jsonify(data)


@main_bp.route("/hasil/<reference_id>")
def hasil(reference_id):
    try:
        data = edge.check_status(reference_id)
    except edge.InvoiceNotFoundError:
        abort(404)
    except edge.UpstreamError:
        abort(500)

    status = (data.get("status") or "").lower()

    payment = {
        "reference_id": data.get("reference_id", reference_id),
        "status": status,
        "package_label": data.get("package_label", "—"),
        "zenime_code": data.get("zenime_code", "—"),
        "premium_until": _fmt_dt(data.get("premium_until")) if data.get("premium_until") else "—",
    }

    if status in ("paid", "berhasil"):
        return render_template("result_success.html", payment=payment)

    # Kalau masih pending (user buka URL hasil langsung sebelum bayar),
    # perlakukan sama seperti gagal/expired: arahkan user coba lagi.
    return render_template("result_failed.html", payment=payment)


@main_bp.route("/coin-hasil/<reference_id>")
def coin_hasil(reference_id):
    try:
        data = edge.check_coin_status(reference_id)
    except edge.InvoiceNotFoundError:
        abort(404)
    except edge.UpstreamError:
        abort(500)

    status = (data.get("status") or "").lower()

    payment = {
        "reference_id": data.get("reference_id", reference_id),
        "status": status,
        "package_label": data.get("package_label", "—"),
        "zenime_code": data.get("zenime_code", "—"),
        "coin_amount": data.get("coin_amount", 0),
        "balance_after": data.get("balance_after"),
    }

    if status in ("paid", "berhasil"):
        return render_template("coin_result_success.html", payment=payment)

    return render_template("coin_result_failed.html", payment=payment)
