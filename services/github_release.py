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


def get_latest_release() -> dict | None:
    """
    Return dict {tag_name, download_url, body} kalau repo punya release,
    None kalau repo belum punya release sama sekali (GitHub 404).
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
    download_url = assets[0].get("browser_download_url", "") if assets else ""

    return {
        "tag_name": payload.get("tag_name", ""),
        "download_url": download_url,
        "body": payload.get("body", ""),
    }
