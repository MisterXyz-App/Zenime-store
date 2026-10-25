# Setup metode "QRIS Dayy"

Alur: checkout pilih **QRIS Dayy** → Flask → Edge Function `dayy-create-invoice` (VPS) bikin klaim + tagihan paygate → halaman `/pembayaran` nampilin QR → PayListener nangkep notif SpeedCash → paygate callback ke `/webhooks/dayy` → RPC `mark_premium_claim_paid` / `mark_coin_claim_paid` → Premium/ZCoin aktif.

## 1. VPS Zenime: Edge Function

```bash
cd /home/zenime/supabase/docker
mkdir -p volumes/functions/dayy-create-invoice
# salin isi supabase_functions/dayy-create-invoice/index.ts ke sana
nano volumes/functions/dayy-create-invoice/index.ts
```

Tambah ke `.env` VPS:

```
PAYGATE_URL=https://mafnnqttvkdgqqxczqyt.supabase.co/functions/v1/paygate
PAYGATE_API_KEY=<PAYGATE_API_KEY project paygate>
DAYY_CALLBACK_URL=https://zenime.biz.id/webhooks/dayy
```

Pastikan tiga variabel itu ikut diteruskan ke service `functions` di `docker-compose.yml` (lihat cara AULAA_API_KEY diteruskan, tambahkan baris yang sama), lalu:

```bash
docker compose up -d --force-recreate functions
```

## 2. Vercel (Zenime-store)

Environment variable baru: `PAYGATE_CALLBACK_SECRET` = nilai yang sama dengan secret `PAYGATE_CALLBACK_SECRET` di project Supabase paygate. Redeploy.

## 3. Firebase Remote Config (opsional)

| Parameter | Fungsi |
|---|---|
| `payment_auto_enabled` | saklar utama QRIS otomatis (sudah ada) |
| `payment_aulaa_enabled` | QRIS Aulaa saja |
| `payment_dayy_enabled` | QRIS Dayy saja, matikan kalau HP listener lagi mati |

Parameter yang belum dibuat dianggap aktif.

## 4. Tes

Beli paket termurah lewat zenime.biz.id, pilih **QRIS Dayy**, bayar persis nominal yang tampil (sudah termasuk kode unik). Halaman otomatis pindah ke sukses begitu callback masuk.

Kalau sudah bayar tapi status tidak berubah: cek `paygate/health` (HP online? notif tidak cocok?), lalu `paygate/callback-retry` dengan id tagihan paygate untuk kirim ulang callback.
