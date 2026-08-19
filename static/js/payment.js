/**
 * Zenime Store — polling status pembayaran di halaman QRIS.
 * Polling ke GET {status_url} setiap 5 detik sampai status
 * "paid"/"berhasil" atau "expired"/"failed", lalu redirect ke halaman hasil.
 * Tidak ada reload manual — murni fetch + update DOM.
 */

(function () {
  const root = document.getElementById('paymentRoot');
  if (!root) return;

  const statusUrl = root.getAttribute('data-status-url');
  const resultUrl = root.getAttribute('data-result-url');

  const statusPill = document.getElementById('statusPill');
  const statusPillText = document.getElementById('statusPillText');
  const qrFrame = document.getElementById('qrFrame');

  const POLL_INTERVAL_MS = 5000;
  const SETTLED_STATUSES = new Set(['paid', 'berhasil', 'expired', 'failed', 'gagal']);

  let pollTimer = null;
  let inFlight = false;

  function setPillState(kind, label) {
    statusPill.classList.remove('waiting');
    statusPill.style.background = '';
    statusPill.style.color = '';

    if (kind === 'waiting') {
      statusPill.classList.add('waiting');
    } else if (kind === 'ok') {
      statusPill.style.background = 'var(--success-dim)';
      statusPill.style.color = 'var(--success)';
    } else if (kind === 'bad') {
      statusPill.style.background = 'var(--danger-dim)';
      statusPill.style.color = 'var(--danger)';
    }
    statusPillText.textContent = label;
  }

  async function pollOnce() {
    if (inFlight) return;
    inFlight = true;

    try {
      const res = await fetch(statusUrl, { headers: { Accept: 'application/json' } });
      if (!res.ok) throw new Error('status check failed');

      const data = await res.json();
      const status = (data.status || '').toLowerCase();

      if (status === 'paid' || status === 'berhasil') {
        setPillState('ok', 'Pembayaran diterima');
        qrFrame.classList.add('is-settled');
        clearInterval(pollTimer);
        window.setTimeout(() => {
          window.location.href = resultUrl;
        }, 900);
        return;
      }

      if (status === 'expired' || status === 'failed' || status === 'gagal') {
        setPillState('bad', status === 'expired' ? 'QR kedaluwarsa' : 'Pembayaran gagal');
        qrFrame.classList.add('is-settled');
        clearInterval(pollTimer);
        window.setTimeout(() => {
          window.location.href = resultUrl;
        }, 900);
        return;
      }

      // Masih pending — tetap di status menunggu.
      setPillState('waiting', 'Menunggu pembayaran');
    } catch (err) {
      // Gangguan jaringan sesaat: jangan alarm-kan user, cukup coba lagi di siklus berikutnya.
    } finally {
      inFlight = false;
    }
  }

  pollOnce();
  pollTimer = setInterval(pollOnce, POLL_INTERVAL_MS);

  window.addEventListener('beforeunload', () => clearInterval(pollTimer));
})();
