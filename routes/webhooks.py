"""
Webhook receiver buat Aulaa -- dipindah dari Edge Function Supabase
(aulaa-webhook) ke sini supaya Aulaa nembak ke Flask/Vercel (jaringannya
lebih stabil daripada VPS self-host), baru Flask yang manggil balik ke
Supabase (lewat PostgREST, services/supabase_edge.py) buat baca & update
tabel premium_claims/coin_claims.

CATATAN: kalau VPS Supabase-nya sendiri yang down total, update ke
database tetap akan gagal dari sini juga -- ini cuma menyelesaikan kasus
dimana Aulaa gagal connect ke VPS (misal firewall/koneksi masuk doang),
bukan downtime total VPS. Daftarkan URL berikut di Dashboard Aulaa >
Projects > Webhook: https://<domain-store-kamu>/webhooks/aulaa

Payload Aulaa flat (order_id, amount, currency, country_code, status,
payment_method, formatted_amount, paid_at) -- order_id (=merchant_ref kita)
jadi kunci utama, gak ada trx_id terpisah.
"""

import hashlib
import hmac
import json
import logging

from flask import Blueprint, current_app, jsonify, request

from services import supabase_edge as edge

logger = logging.getLogger(__name__)

webhook_bp = Blueprint("webhook", __name__)


def _verify_signature(raw_body: bytes, signature: str) -> bool:
    secret = current_app.config.get("AULAA_WEBHOOK_SECRET", "")
    if not secret:
        logger.error("AULAA_WEBHOOK_SECRET belum di-set, menolak semua webhook Aulaa")
        return False
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    # compare_digest -- constant-time, sama kayak timingSafeEqual versi Edge Function.
    return hmac.compare_digest(signature or "", expected)


def _resolve_product_type(merchant_ref: str) -> str | None:
    """Cari order_id (=merchant_ref) ini punya transaksi premium atau coin."""
    if edge.rest_select_one("premium_claims", {"merchant_ref": merchant_ref}):
        return "premium"
    if edge.rest_select_one("coin_claims", {"merchant_ref": merchant_ref}):
        return "coin"
    return None


@webhook_bp.route("/webhooks/aulaa", methods=["POST"])
def aulaa_webhook():
    # WAJIB baca body sebagai raw bytes dulu -- signature dihitung dari raw bytes,
    # bukan dari hasil re-serialize request.get_json().
    raw_body = request.get_data()
    signature = request.headers.get("x-webhook-signature", "")

    if not _verify_signature(raw_body, signature):
        return jsonify({"received": False, "error": "Invalid signature"}), 401

    try:
        data = json.loads(raw_body)
    except ValueError:
        return jsonify({"received": False, "error": "Invalid JSON"}), 400

    merchant_ref = data.get("order_id")
    status_text = str(data.get("status", "")).strip().lower()
    logger.info("aulaa webhook payload diterima: %s", data)

    try:
        product_type = _resolve_product_type(merchant_ref)
    except edge.UpstreamError as exc:
        return jsonify({"received": False, "error": str(exc)}), 500

    if not product_type:
        logger.info("order_id tidak ditemukan di premium_claims maupun coin_claims: %s", merchant_ref)
        return jsonify({"received": False, "error": "order_id tidak dikenal"}), 404

    table = "coin_claims" if product_type == "coin" else "premium_claims"

    try:
        if status_text == "paid":
            # Idempotent di sisi RPC -- aman dipanggil dobel kalau Aulaa retry
            # webhook buat trx yang sama (sampai 4x total: awal + 3 retry).
            rpc_name = "mark_coin_claim_paid" if product_type == "coin" else "mark_premium_claim_paid"
            edge.rest_rpc(rpc_name, {"p_merchant_ref": merchant_ref, "p_trx_id": merchant_ref})

        elif status_text in ("expired", "cancelled", "failed"):
            # jangan overwrite kalau row udah "paid" duluan
            edge.rest_update(table, {"merchant_ref": merchant_ref, "status": "pending"}, {"status": "expired"})

        elif status_text == "refunded":
            # beda dari expired/cancelled/failed -- refund cuma kejadian SETELAH
            # transaksi udah "paid", jadi gak dibatasi status=pending kayak di atas
            edge.rest_update(table, {"merchant_ref": merchant_ref}, {"status": "refunded"})

        elif status_text == "pending":
            pass

        else:
            logger.info("status webhook tidak dikenal: %s", status_text)
            return jsonify({"received": False, "error": "Unrecognized status"}), 400

    except edge.UpstreamError as exc:
        return jsonify({"received": False, "error": str(exc)}), 500

    return jsonify({"received": True})
