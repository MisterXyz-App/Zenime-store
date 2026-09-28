"""
Proxy ke release GitHub terbaru Zenime, dipanggil dari endpoint
/api/latest-release di routes/main.py.

KENAPA INI ADA: kalau tiap device Android hit api.github.com langsung buat
cek update, banyak user yang share IP yang sama (NAT operator seluler) bisa
gampang kena rate limit GitHub (60 request/jam per IP tanpa autentikasi).
Server ini jadi perantara -- device Android manggil server ini, server ini
yang manggil GitHub.
"""

import time

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


# ---------------------------------------------------------------------------
# Statistik unduhan (versi terbaru + total semua versi)
# ---------------------------------------------------------------------------

_STATS_TTL_SECONDS = 300  # 5 menit; cukup segar, hemat rate limit GitHub
_STATS_MAX_PAGES = 10     # 10 x 100 = maksimal 1000 rilis
_stats_cache: dict = {"at": 0.0, "data": None}


def _release_downloads(release: dict) -> int:
    """Jumlah unduhan satu rilis. Hitung aset .apk saja (kalau ada), supaya
    file pendamping seperti checksum tidak ikut terhitung."""
    assets = release.get("assets") or []
    apks = [a for a in assets if str(a.get("name", "")).lower().endswith(".apk")]
    return sum(int(a.get("download_count") or 0) for a in (apks or assets))


def get_download_stats() -> dict | None:
    """
    Return {latest_tag, latest, total, releases} atau None kalau repo belum
    punya rilis.

    - latest : unduhan rilis terbaru (yang sama dengan /releases/latest)
    - total  : jumlah unduhan SEMUA rilis yang masih ada di GitHub
    - Draft tidak dihitung. Pre-release ikut masuk ke total.

    Hasil di-cache di memori. Kalau GitHub gagal tapi ada cache lama, cache
    lama dipakai; kalau tidak ada sama sekali, UpstreamError dilempar.
    """
    now = time.time()
    if _stats_cache["data"] is not None and now - _stats_cache["at"] < _STATS_TTL_SECONDS:
        return _stats_cache["data"]

    owner = current_app.config["GITHUB_REPO_OWNER"]
    repo = current_app.config["GITHUB_REPO_NAME"]
    headers = {"Accept": "application/vnd.github+json"}
    token = current_app.config.get("GITHUB_TOKEN", "")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    releases: list[dict] = []
    try:
        for page in range(1, _STATS_MAX_PAGES + 1):
            response = requests.get(
                f"https://api.github.com/repos/{owner}/{repo}/releases",
                params={"per_page": 100, "page": page},
                headers=headers,
                timeout=10,
            )
            if response.status_code == 404:
                break
            if not response.ok:
                raise UpstreamError(f"GitHub API balikin status {response.status_code}")
            batch = response.json()
            releases.extend(batch)
            if len(batch) < 100:
                break
    except (requests.RequestException, ValueError) as exc:
        if _stats_cache["data"] is not None:
            return _stats_cache["data"]
        raise UpstreamError(str(exc)) from exc
    except UpstreamError:
        if _stats_cache["data"] is not None:
            return _stats_cache["data"]
        raise

    published = [r for r in releases if not r.get("draft")]
    if not published:
        return None

    # "Terbaru" versi GitHub = rilis non-prerelease terakhir dipublikasikan.
    stable = [r for r in published if not r.get("prerelease")] or published
    latest = max(stable, key=lambda r: r.get("published_at") or r.get("created_at") or "")

    data = {
        "latest_tag": latest.get("tag_name", ""),
        "latest": _release_downloads(latest),
        "total": sum(_release_downloads(r) for r in published),
        "releases": len(published),
    }
    _stats_cache["at"] = now
    _stats_cache["data"] = data
    return data
