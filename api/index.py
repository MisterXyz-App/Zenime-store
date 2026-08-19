"""
Entry point untuk Vercel Python Runtime (@vercel/python).

Vercel akan mengimpor modul ini dan mencari objek WSGI bernama `app`.
File ini sengaja tipis — semua logika tetap ada di app.py/routes/services
di root project, supaya kode yang sama tetap bisa dijalankan lokal
(`python app.py`) maupun lewat gunicorn di hosting lain.
"""

import os
import sys

# Root project ada satu level di atas folder api/, tambahkan ke sys.path
# supaya "from routes.main import main_bp" dkk tetap bisa di-resolve.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import app  # noqa: E402  (import setelah sys.path diatur, sengaja)
