"""
Dashboard admin sederhana buat lihat & proses klaim pembayaran manual
(QRIS pribadi, buat pembeli luar negeri). Proteksi cuma 1 password di
env var ADMIN_PASSWORD -- cukup buat pemakaian sendiri, BUKAN sistem
user multi-admin.

Data antrean (pending) datang dari Edge Function `manual-payment-list-pending`.
Statistik pendapatan butuh Edge Function riwayat OPSIONAL
(SUPABASE_FN_MANUAL_LIST_HISTORY); kalau belum ada, kartu pendapatan
menampilkan keadaan "belum terhubung" dan sisanya tetap jalan.
"""

from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from services import supabase_edge as edge

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

SESSION_KEY = "admin_authed"
WIB = timezone(timedelta(hours=7))

BULAN = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
         "Agustus", "September", "Oktober", "November", "Desember"]
HARI = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]

APPROVED_STATUSES = {"approved", "success", "completed", "paid"}
REJECTED_STATUSES = {"rejected", "declined", "failed"}


# --- Filter Jinja ---------------------------------------------------------

@admin_bp.app_template_filter("rupiah")
def rupiah(value):
    try:
        return "Rp " + f"{int(round(float(value))):,}".replace(",", ".")
    except (TypeError, ValueError):
        return "Rp 0"


@admin_bp.app_template_filter("rupiah_short")
def rupiah_short(value):
    """Ringkas buat sumbu grafik: 1.250.000 -> 1,25 jt."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "0"
    if v >= 1_000_000:
        return f"{v / 1_000_000:.2f}".rstrip("0").rstrip(".").replace(".", ",") + " jt"
    if v >= 1_000:
        return f"{v / 1_000:.1f}".rstrip("0").rstrip(".").replace(".", ",") + " rb"
    return str(int(v))


@admin_bp.app_template_filter("wait_text")
def wait_text(seconds):
    if seconds is None:
        return "—"
    minutes = int(seconds // 60)
    if minutes < 1:
        return "Baru saja"
    if minutes < 60:
        return f"{minutes} mnt"
    hours, mins = divmod(minutes, 60)
    if hours < 24:
        return f"{hours} j {mins} m" if mins else f"{hours} j"
    days, hrs = divmod(hours, 24)
    return f"{days} h {hrs} j" if hrs else f"{days} h"


# --- Helper ---------------------------------------------------------------

def _parse_dt(value):
    if not value:
        return None
    raw = str(value).strip()
    normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _kind(claim):
    return "coin" if claim.get("product_type") == "coin" else "premium"


def _to_int(value):
    try:
        return int(round(float(value or 0)))
    except (TypeError, ValueError):
        return 0


def _build_queue(claims, now):
    items = []
    for c in claims:
        created = _parse_dt(c.get("created_at"))
        age = max(0, int((now - created).total_seconds())) if created else None
        items.append({
            **c,
            "kind": _kind(c),
            "amount_int": _to_int(c.get("amount")),
            "coin_int": _to_int(c.get("coin_amount")),
            "has_proof": bool(c.get("proof_url")),
            "created_iso": created.isoformat() if created else "",
            "age_seconds": age,
        })
    # Terlama dulu = yang paling lama menunggu diproses duluan.
    items.sort(key=lambda x: x["age_seconds"] if x["age_seconds"] is not None else -1, reverse=True)
    return items


def _queue_stats(queue):
    stats = {
        "total": len(queue),
        "amount": sum(i["amount_int"] for i in queue),
        "no_proof": sum(1 for i in queue if not i["has_proof"]),
        "oldest_age": None,
        "premium": {"count": 0, "amount": 0},
        "coin": {"count": 0, "amount": 0},
    }
    ages = [i["age_seconds"] for i in queue if i["age_seconds"] is not None]
    if ages:
        stats["oldest_age"] = max(ages)
    for i in queue:
        stats[i["kind"]]["count"] += 1
        stats[i["kind"]]["amount"] += i["amount_int"]
    stats["premium_pct"] = round(stats["premium"]["count"] * 100 / stats["total"]) if stats["total"] else 0
    stats["coin_pct"] = 100 - stats["premium_pct"] if stats["total"] else 0
    return stats


def _build_revenue(history, now, days=14):
    """Ringkas riwayat jadi angka pendapatan + deret harian buat grafik."""
    today = now.astimezone(WIB).date()
    approved, rejected = [], 0

    for h in history:
        status = str(h.get("status", "")).lower()
        if status in REJECTED_STATUSES:
            rejected += 1
            continue
        if status not in APPROVED_STATUSES:
            continue
        dt = _parse_dt(h.get("approved_at") or h.get("processed_at") or h.get("updated_at") or h.get("created_at"))
        if not dt:
            continue
        approved.append({
            "day": dt.astimezone(WIB).date(),
            "amount": _to_int(h.get("amount")),
            "kind": _kind(h),
        })

    def total(since_days):
        start = today - timedelta(days=since_days - 1)
        return sum(a["amount"] for a in approved if a["day"] >= start)

    daily = []
    for offset in range(days - 1, -1, -1):
        d = today - timedelta(days=offset)
        rows = [a for a in approved if a["day"] == d]
        amt = sum(a["amount"] for a in rows)
        daily.append({
            "label": str(d.day),
            "amount": amt,
            "count": len(rows),
            "title": f"{d.day} {BULAN[d.month - 1][:3]}: {rupiah(amt)} ({len(rows)} klaim)",
            "is_today": offset == 0,
        })
    peak = max((d["amount"] for d in daily), default=0)
    for d in daily:
        d["pct"] = round(d["amount"] * 100 / peak) if peak else 0

    handled = len(approved) + rejected
    return {
        "today": total(1),
        "week": total(7),
        "month": total(30),
        "approved_count": len(approved),
        "approval_rate": round(len(approved) * 100 / handled) if handled else None,
        "daily": daily,
        "peak": peak,
        "days": days,
        "premium_total": sum(a["amount"] for a in approved if a["kind"] == "premium"),
        "coin_total": sum(a["amount"] for a in approved if a["kind"] == "coin"),
    }


# --- Auth -----------------------------------------------------------------

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


# --- Dashboard ------------------------------------------------------------

@admin_bp.route("/")
@login_required
def index():
    return redirect(url_for("admin.manual_payments"))


@admin_bp.route("/manual-payments")
@login_required
def manual_payments():
    now = datetime.now(timezone.utc)

    try:
        claims = edge.list_pending_manual_claims()
        error = None
    except edge.UpstreamError as exc:
        claims = []
        error = str(exc)

    queue = _build_queue(claims, now)

    rev, rev_error = None, None
    try:
        history = edge.list_manual_claim_history(days=30)
        if history is not None:
            rev = _build_revenue(history, now)
    except edge.UpstreamError as exc:
        rev_error = str(exc)

    wib_now = now.astimezone(WIB)
    today_label = f"{HARI[wib_now.weekday()]}, {wib_now.day} {BULAN[wib_now.month - 1]} {wib_now.year}"

    return render_template(
        "admin_manual_payments.html",
        queue=queue,
        qs=_queue_stats(queue),
        rev=rev,
        rev_error=rev_error,
        error=error,
        today_label=today_label,
    )


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
