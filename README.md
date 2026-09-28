# Zenime Store

Storefront ringan untuk aktivasi Premium akun **Zenime** lewat QRIS (Sakurupiah, via Supabase Edge Function). Flask di sini murni jadi lapisan UI + proxy — semua signature Sakurupiah, verifikasi kode akun, dan aktivasi premium ditangani di sisi Supabase.

## Struktur project

```
zenime_store/
├── app.py                     # entry point, error handler 404/500
├── config.py                  # semua konfigurasi dari environment variable
├── requirements.txt
├── .env.example
├── routes/
│   ├── main.py                 # halaman: home, beli premium, pembayaran, hasil
│   └── payment.py              # API: daftar paket, create invoice, cek status
├── services/
│   └── supabase_edge.py        # proxy tipis ke Supabase Edge Function
├── templates/                  # Jinja2 (base, index, beli, payment, result, 404/500)
└── static/
    ├── css/style.css
    └── js/{main,checkout,payment}.js
```

## Menjalankan lokal

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# isi SUPABASE_URL & SUPABASE_SERVICE_ROLE_KEY di .env kalau sudah ada.
# Kalau dikosongkan, backend otomatis pakai data paket & invoice dummy
# (USE_MOCK_DATA_WHEN_UNCONFIGURED=true) supaya UI tetap bisa dites.

python app.py
# buka http://localhost:5000
```

Untuk production, jalankan lewat gunicorn, contoh:

```bash
gunicorn -w 2 -b 0.0.0.0:8000 app:app
```

## Deploy ke Vercel

Project ini sudah disiapkan untuk deploy langsung ke Vercel (Python serverless function via `@vercel/python`), dengan pola yang sama seperti project Flask lain di brand Dayynime.

```
zenime_store/
├── api/
│   └── index.py        # entry point serverless — mengekspos `app` dari app.py
├── vercel.json          # routing: /static/* lewat CDN, sisanya ke Flask
├── .vercelignore
```

Langkah deploy:

1. Push project ini ke repo GitHub (git init, commit, push).
2. Buka [vercel.com](https://vercel.com) → **Add New Project** → import repo tersebut.
   - Vercel akan otomatis mendeteksi `vercel.json` dan `requirements.txt`, tidak perlu ubah Build & Output Settings secara manual.
3. Di tab **Environment Variables**, isi semua variabel dari `.env.example`:
   - `SECRET_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`
   - `SUPABASE_FN_CREATE_INVOICE`, `SUPABASE_FN_CHECK_STATUS`, `SUPABASE_FN_LIST_PACKAGES` (opsional, sudah ada default)
   - `EDGE_FUNCTION_TIMEOUT_SECONDS` (opsional)
   - `USE_MOCK_DATA_WHEN_UNCONFIGURED=false` (set `false` di production supaya tidak diam-diam jatuh ke data dummy kalau env Supabase salah/kosong)
   - `FLASK_ENV=production`
4. Klik **Deploy**.

Atau lewat Vercel CLI dari Termux/terminal:

```bash
npm i -g vercel
vercel login
vercel            # deploy preview
vercel --prod     # deploy production
```

CLI akan menanyakan environment variable di atas kalau belum diisi lewat dashboard — bisa juga di-set duluan lewat `vercel env add NAMA_VARIABEL`.

**Catatan Vercel:**
- Static assets (`static/css`, `static/js`, `static/img`) dibuild lewat `@vercel/static` dan disajikan langsung dari CDN Vercel — bukan lewat function Python — jadi tidak menambah cold start.
- `templates/`, `routes/`, `services/`, dan `config.py` diikutkan ke bundle function lewat `includeFiles` di `vercel.json`, karena secara default Vercel Python builder cuma men-trace file `.py` yang di-import langsung; asset non-Python (seperti template Jinja) tidak otomatis ikut kalau tidak didaftarkan.
- Fungsi Vercel bersifat stateless/ephemeral per request — cocok dengan desain backend ini yang memang tidak menyimpan session apa pun (semua state transaksi ada di Supabase, bukan di server).

## Menyambungkan Edge Function asli

Ganti nilai di `.env` (URL project Supabase + service role key), lalu pastikan tiga Edge Function berikut ada di project Supabase-mu dan mengikuti kontrak di bawah. Nama function bisa disesuaikan lewat `SUPABASE_FN_*` di `.env` tanpa ubah kode Flask.

### 1. `zenime-list-packages` (GET)
Response:
```json
{ "packages": [
  { "id": "pkg_1m", "label": "1 Bulan", "duration_text": "1 bulan", "price": 15000, "badge": null },
  { "id": "pkg_3m", "label": "3 Bulan", "duration_text": "3 bulan", "price": 40000, "badge": "Hemat" }
]}
```

### 2. `sakurupiah-create-invoice` (POST)
Request body: `{ "zenime_code": "ZN-A1B2C3", "package_id": "pkg_1m" }`

Response sukses (dipakai untuk render halaman pembayaran):
```json
{
  "reference_id": "ZS-XXXXXXXXXX",
  "amount": 15000,
  "package_label": "1 Bulan",
  "zenime_code": "ZN-A1B2C3",
  "qr_image": "data:image/png;base64,....",
  "checkout_url": "https://...",
  "status": "pending",
  "created_at": "2026-08-20T10:00:00Z",
  "expires_at": "2026-08-20T10:15:00Z"
}
```

Response error (dibaca lewat field `error_code`):
- `404` + `{"error_code": "account_not_found", "message": "..."}`
- `400` + `{"error_code": "invalid_package", "message": "..."}`

### 3. `sakurupiah-check-status` (GET, query `?reference_id=...`)
Dipanggil baik oleh polling JS di halaman pembayaran maupun saat Flask merender ulang halaman pembayaran/hasil — jadi response-nya sebaiknya tetap membawa detail invoice lengkap, bukan cuma field `status`.

```json
{
  "reference_id": "ZS-XXXXXXXXXX",
  "status": "pending",
  "amount": 15000,
  "package_label": "1 Bulan",
  "zenime_code": "ZN-A1B2C3",
  "qr_image": "data:image/png;base64,....",
  "checkout_url": "https://...",
  "created_at": "2026-08-20T10:00:00Z",
  "expires_at": "2026-08-20T10:15:00Z",
  "premium_until": "2026-09-20T10:00:00Z"
}
```

`status` yang dikenali frontend: `pending`, `paid`/`berhasil`, `expired`, `failed`/`gagal`.

## Catatan implementasi

- Kode akun Zenime divalidasi formatnya (`ZN-XXXXXX`) di server (`routes/payment.py`) sebelum diteruskan ke Edge Function — input mentah dari client tidak pernah langsung dipakai.
- Daftar paket tidak pernah di-hardcode di template — selalu lewat `GET /api/packages`.
- Halaman pembayaran polling ke `GET /api/payment/status/<reference_id>` setiap 5 detik lewat `fetch`, tanpa reload halaman.
- Tidak ada sistem login di website ini — identitas user cukup dari kode akun Zenime yang diketik.
- Selama `SUPABASE_URL`/`SUPABASE_SERVICE_ROLE_KEY` kosong dan `USE_MOCK_DATA_WHEN_UNCONFIGURED=true`, backend memakai data dummy supaya frontend tetap bisa dikembangkan sebelum Edge Function-nya jadi.
