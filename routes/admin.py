"""
Halaman admin sederhana buat lihat & proses klaim pembayaran manual
(QRIS pribadi, buat pembeli luar negeri). Proteksi cuma 1 password di
env var ADMIN_PASSWORD -- cukup buat pemakaian sendiri, BUKAN sistem
user multi-admin.
"""

from functools import wraps

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from services import supabase_edge as edge

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

SESSION_KEY = "admin_authed"


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get(SESSION_KEY):
            return redirect(url_for("admin.login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        password = request.form.get("password", "")
        expected = current_app_config_admin_password()

        if not expected:
            flash("ADMIN_PASSWORD belum diset di environment variable.", "error")
        elif password == expected:
            session[SESSION_KEY] = True
            next_url = request.args.get("next") or url_for("admin.manual_payments")
            return redirect(next_url)
        else:
            flash("Password salah.", "error")

    return render_template("admin_login.html")


@admin_bp.route("/logout", methods=["POST"])
def logout():
    session.pop(SESSION_KEY, None)
    return redirect(url_for("admin.login"))


@admin_bp.route("/manual-payments")
@login_required
def manual_payments():
    try:
        claims = edge.list_pending_manual_claims()
        error = None
    except edge.UpstreamError as exc:
        claims = []
        error = str(exc)

    return render_template("admin_manual_payments.html", claims=claims, error=error)


@admin_bp.route("/manual-payments/<claim_id>/approve", methods=["POST"])
@login_required
def approve_manual_payment(claim_id):
    try:
        edge.approve_manual_claim(claim_id)
        flash(f"Klaim {claim_id[:8]}… disetujui, premium aktif.", "success")
    except edge.UpstreamError as exc:
        flash(f"Gagal approve: {exc}", "error")
    return redirect(url_for("admin.manual_payments"))


@admin_bp.route("/manual-payments/<claim_id>/reject", methods=["POST"])
@login_required
def reject_manual_payment(claim_id):
    try:
        edge.reject_manual_claim(claim_id)
        flash(f"Klaim {claim_id[:8]}… ditolak.", "success")
    except edge.UpstreamError as exc:
        flash(f"Gagal menolak: {exc}", "error")
    return redirect(url_for("admin.manual_payments"))


def current_app_config_admin_password():
    from flask import current_app
    return current_app.config.get("ADMIN_PASSWORD", "")
