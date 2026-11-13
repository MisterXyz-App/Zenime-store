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
  const checkStatusBtn = document.getElementById('checkStatusBtn');

  const POLL_INTERVAL_MS = 5000;
  const SETTLED_STATUSES = new Set(['paid', 'berhasil', 'expired', 'failed', 'gagal']);

  let pollTimer = null;
  let inFlight = false;
  let settled = false;

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
        settled = true;
        clearInterval(pollTimer);
        window.setTimeout(() => {
          window.location.href = resultUrl;
        }, 900);
        return;
      }

      if (status === 'expired' || status === 'failed' || status === 'gagal') {
        setPillState('bad', status === 'expired' ? 'QR kedaluwarsa' : 'Pembayaran gagal');
        qrFrame.classList.add('is-settled');
        settled = true;
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

  if (checkStatusBtn) {
    checkStatusBtn.addEventListener('click', async () => {
      if (inFlight) return;
      checkStatusBtn.disabled = true;
      const originalHtml = checkStatusBtn.innerHTML;
      checkStatusBtn.innerHTML = '<i class="fa-solid fa-rotate fa-spin"></i> Memeriksa...';
      await pollOnce();
      checkStatusBtn.disabled = false;
      checkStatusBtn.innerHTML = originalHtml;
    });
  }

  // Embedded Checkout Aulaa: buka halaman bayar sebagai jendela di atas halaman ini.
  // Kalau embed.js gagal dimuat, klik jalan normal (buka tab baru) sebagai fallback.
  // onSuccess cuma buat tampilan -- status lunas tetap dicek dari server via pollOnce().
  const payBtn = document.getElementById('aulaaPayBtn');

  function openCheckout() {
    if (!window.Aulaa || !window.Aulaa.checkout) return false;
    window.Aulaa.checkout.open(payBtn.href, {
      onSuccess() {
        setPillState('waiting', 'Mengonfirmasi pembayaran...');
        pollOnce();
      },
      onClose() {
        pollOnce();
      },
    });
    return true;
  }

  if (payBtn) {
    payBtn.addEventListener('click', (e) => {
      if (openCheckout()) e.preventDefault();
    });
  }

  // Auto-buka jendela QRIS Aulaa sekali saat halaman dimuat (khusus tombol
  // yang punya data-auto-open), setelah cek status pertama masih pending.
  // Kalau embed.js belum siap / gagal dimuat, tombol manual tetap ada.
  async function startPolling() {
    await pollOnce();
    if (payBtn && payBtn.hasAttribute('data-auto-open') && !settled) {
      openCheckout();
    }
  }

  startPolling();
  pollTimer = setInterval(pollOnce, POLL_INTERVAL_MS);

  window.addEventListener('beforeunload', () => clearInterval(pollTimer));
})();
