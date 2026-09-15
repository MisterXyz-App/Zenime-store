from datetime import datetime, timedelta, timezone

from flask import Flask, render_template

from config import Config
from routes.admin import admin_bp
from routes.main import main_bp
from routes.payment import payment_bp

WIB = timezone(timedelta(hours=7))


def format_wib(value):
    """
    Format timestamp dari Supabase (biasanya ISO 8601 UTC, mis.
    '2026-09-15T00:02:52.177653+00:00') jadi waktu WIB yang gampang dibaca,
    mis. '15 Sep 2026, 07.02 WIB'.
    Kalau value bukan string ISO yang valid, dikembalikan apa adanya
    supaya tidak error di halaman admin.
    """
    if not value:
        return value

    raw = str(value).strip()
    # Python < 3.11 gak bisa parse 'Z' langsung -> ganti ke offset +00:00 dulu.
    normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw

    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        return raw

    # Kalau Supabase kirim tanpa info timezone sama sekali, anggap itu UTC
    # (semua timestamp Supabase/Postgres `timestamptz` memang disimpan UTC).
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    dt_wib = dt.astimezone(WIB)
    return dt_wib.strftime("%d %b %Y, %H.%M") + " WIB"


def create_app(config_object: type = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_object)

    app.register_blueprint(main_bp)
    app.register_blueprint(payment_bp)
    app.register_blueprint(admin_bp)

    app.jinja_env.filters["to_wib"] = format_wib

    @app.context_processor
    def inject_globals():
        return {"current_year": datetime.now(timezone.utc).year}

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("404.html"), 404

    @app.errorhandler(500)
    def server_error(_error):
        return render_template("500.html"), 500

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=app.config["DEBUG"])
