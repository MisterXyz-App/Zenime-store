/**
 * Zenime Store — halaman "Bayar via QRIS (manual)".
 * 1. User upload bukti transfer -> POST ke /api/manual-payment/upload-proof
 * 2. Setelah terkirim, polling status (fungsi yang sama dipakai flow
 *    Sakurupiah) sampai admin approve manual -> redirect ke halaman hasil.
 */

(function () {
  const root = document.getElementById('manualPaymentRoot');
  if (!root) return;

  const claimId = root.getAttribute('data-claim-id');
  const statusUrl = root.getAttribute('data-status-url');
  const uploadProofUrl = root.getAttribute('data-upload-proof-url');
  const resultUrl = root.getAttribute('data-result-url');
  const initialStatus = (root.getAttribute('data-initial-status') || 'pending').toLowerCase();

  const statusPill = document.getElementById('statusPill');
  const statusPillText = document.getElementById('statusPillText');
  const proofFile = document.getElementById('proofFile');
  const proofHint = document.getElementById('proofHint');
  const uploadProofBtn = document.getElementById('uploadProofBtn');
  const proofSection = document.getElementById('proofSection');
  const proofDoneNotice = document.getElementById('proofDoneNotice');

  const SETTLED_STATUSES = new Set(['paid', 'berhasil', 'expired', 'failed', 'gagal']);
  const MAX_FILE_BYTES = 5 * 1024 * 1024;

  let pollTimer = null;
  let inFlight = false;
  let proofSubmitted = false;

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

  // ---- Kalau halaman ini dibuka ulang setelah settled, langsung redirect ----
  if (SETTLED_STATUSES.has(initialStatus)) {
    window.location.href = resultUrl;
    return;
  }

  // ---- Upload bukti transfer -------------------------------------------

  proofFile.addEventListener('change', () => {
    const file = proofFile.files[0];
    if (!file) {
      uploadProofBtn.disabled = true;
      return;
    }
    if (file.size > MAX_FILE_BYTES) {
      proofHint.textContent = 'File terlalu besar, maksimal 5MB.';
      proofHint.style.color = 'var(--danger)';
      uploadProofBtn.disabled = true;
      return;
    }
    proofHint.textContent = file.name;
    proofHint.style.color = '';
    uploadProofBtn.disabled = false;
  });

  function fileToBase64(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result.split(',')[1]);
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  }

  uploadProofBtn.addEventListener('click', async () => {
    const file = proofFile.files[0];
    if (!file) return;

    uploadProofBtn.disabled = true;
    uploadProofBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Mengunggah…';

    try {
      const base64 = await fileToBase64(file);
      const res = await fetch(uploadProofUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          claim_id: claimId,
          proof_base64: base64,
          proof_filename: file.name,
        }),
      });

      const data = await res.json();

      if (!res.ok || !data.ok) {
        window.zenimeToast(data.message || 'Gagal mengunggah bukti. Coba lagi.', { icon: 'fa-triangle-exclamation' });
        uploadProofBtn.disabled = false;
        uploadProofBtn.innerHTML = '<i class="fa-solid fa-upload"></i> Kirim Bukti Transfer';
        return;
      }

      proofSubmitted = true;
      proofSection.style.display = 'none';
      proofDoneNotice.style.display = 'block';
      setPillState('waiting', 'Menunggu verifikasi admin');
    } catch (err) {
      window.zenimeToast('Koneksi bermasalah. Periksa internet dan coba lagi.', { icon: 'fa-triangle-exclamation' });
      uploadProofBtn.disabled = false;
      uploadProofBtn.innerHTML = '<i class="fa-solid fa-upload"></i> Kirim Bukti Transfer';
    }
  });

  // ---- Polling status (reuse endpoint yang sama dipakai flow Sakurupiah) ----

  async function pollOnce() {
    if (inFlight) return;
    inFlight = true;

    try {
      const res = await fetch(statusUrl, { headers: { Accept: 'application/json' } });
      if (!res.ok) throw new Error('status check failed');

      const data = await res.json();
      const status = (data.status || '').toLowerCase();

      if (status === 'paid' || status === 'berhasil') {
        setPillState('ok', 'Premium diaktifkan');
        clearInterval(pollTimer);
        window.setTimeout(() => {
          window.location.href = resultUrl;
        }, 900);
        return;
      }

      if (status === 'expired' || status === 'failed' || status === 'gagal') {
        setPillState('bad', 'Klaim kedaluwarsa/gagal');
        clearInterval(pollTimer);
        window.setTimeout(() => {
          window.location.href = resultUrl;
        }, 900);
        return;
      }

      if (!proofSubmitted) {
        setPillState('waiting', 'Menunggu bukti transfer');
      }
    } catch (err) {
      // Gangguan jaringan sesaat, coba lagi siklus berikutnya.
    } finally {
      inFlight = false;
    }
  }

  pollOnce();
  pollTimer = setInterval(pollOnce, 6000);

  window.addEventListener('beforeunload', () => clearInterval(pollTimer));
})();
