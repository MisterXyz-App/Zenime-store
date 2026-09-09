"""
Proxy ke release GitHub terbaru Zenime, dipanggil dari endpoint
/api/latest-release di routes/main.py.

KENAPA INI ADA: kalau tiap device Android hit api.github.com langsung buat
cek update, banyak user yang share IP yang sama (NAT operator seluler) bisa
gampang kena rate limit GitHub (60 request/jam per IP tanpa autentikasi).
Server ini jadi perantara -- device Android manggil server ini, server ini
yang manggil GitHub.
"""

import requests
from flask import current_app


class UpstreamError(Exception):
    """Gagal menghubungi GitHub (network/timeout)."""


def _fmt_size(num_bytes) -> str:
    """Ubah ukuran file dari bytes ke string yang enak dibaca (MB/KB)."""
    if not num_bytes:
        return ""
    try:
        num_bytes = float(num_bytes)
    except (TypeError, ValueError):
        return ""
    mb = num_bytes / (1024 * 1024)
    if mb >= 1:
        return f"{mb:.1f} MB"
    kb = num_bytes / 1024
    return f"{kb:.0f} KB"


def get_latest_release() -> dict | None:
    """
    Return dict {tag_name, download_url, body, size, published_at} kalau
    repo punya release, None kalau repo belum punya release sama sekali
    (GitHub 404).
    """
    owner = current_app.config["GITHUB_REPO_OWNER"]
    repo = current_app.config["GITHUB_REPO_NAME"]
    url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"

    headers = {"Accept": "application/vnd.github+json"}
    token = current_app.config.get("GITHUB_TOKEN", "")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        response = requests.get(url, headers=headers, timeout=10)
    except requests.RequestException as exc:
        raise UpstreamError(str(exc)) from exc

    if response.status_code == 404:
        return None

    if not response.ok:
        raise UpstreamError(f"GitHub API balikin status {response.status_code}")

    payload = response.json()
    assets = payload.get("assets") or []
    first_asset = assets[0] if assets else {}
    download_url = first_asset.get("browser_download_url", "")

    return {
        "tag_name": payload.get("tag_name", ""),
        "download_url": download_url,
        "body": payload.get("body", ""),
        "size": _fmt_size(first_asset.get("size")),
        "published_at": payload.get("published_at", ""),
        "download_count": first_asset.get("download_count", 0),
    }
