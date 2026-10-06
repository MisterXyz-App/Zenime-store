/**
 * Zenime Store — logika halaman "Dukung Kami" (donasi).
 * - Preset nominal + input manual (saling sinkron)
 * - Validasi ringan di client (minimal Rp 1.000)
 * - Submit ke POST /api/donation/create, redirect ke halaman pembayaran
 */

(function () {
  const form = document.getElementById('donationForm');
  if (!form) return;

  const MIN_AMOUNT = 1000;
  const MAX_AMOUNT = 10000000;

  const presetsWrap = document.getElementById('amountPresets');
  const amountInput = document.getElementById('donationAmount');
  const donorNameInput = document.getElementById('donorName');
  const donorMessageInput = document.getElementById('donorMessage');
  const donorCodeInput = document.getElementById('donorCode');
  const submitBtn = document.getElementById('submitDonation');

  const summaryName = document.getElementById('summaryName');
  const summaryTotal = document.getElementById('summaryTotal');

  const donationError = document.getElementById('donationError');
  const donationErrorMsg = document.getElementById('donationErrorMsg');

  function formatRupiah(value) {
    return 'Rp ' + Number(value || 0).toLocaleString('id-ID');
  }

  function currentAmount() {
    const digits = amountInput.value.replace(/[^0-9]/g, '');
    return digits ? parseInt(digits, 10) : 0;
  }

  function updateSummary() {
    summaryName.textContent = donorNameInput.value.trim() || 'Anonim';
    summaryTotal.textContent = formatRupiah(currentAmount());
  }

  function updateSubmitState() {
    const amount = currentAmount();
    submitBtn.disabled = !(amount >= MIN_AMOUNT && amount <= MAX_AMOUNT);
  }

  function hideError() {
    donationError.classList.remove('is-visible');
  }

  function showError(message) {
    donationErrorMsg.textContent = message;
    donationError.classList.add('is-visible');
  }

  function setActivePreset(amount) {
    const buttons = presetsWrap.querySelectorAll('.amount-preset');
    buttons.forEach((btn) => {
      btn.classList.toggle('is-active', Number(btn.dataset.amount) === amount);
    });
  }

  presetsWrap.addEventListener('click', (e) => {
    const btn = e.target.closest('.amount-preset');
    if (!btn) return;
    const amount = Number(btn.dataset.amount);
    amountInput.value = amount.toLocaleString('id-ID');
    setActivePreset(amount);
    hideError();
    updateSummary();
    updateSubmitState();
  });

  amountInput.addEventListener('input', () => {
    setActivePreset(currentAmount());
    hideError();
    updateSummary();
    updateSubmitState();
  });

  // Format jadi "10.000" pas user selesai ngetik, biar enak dibaca.
  amountInput.addEventListener('blur', () => {
    const amount = currentAmount();
    amountInput.value = amount ? amount.toLocaleString('id-ID') : '';
  });

  donorNameInput.addEventListener('input', updateSummary);

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    hideError();

    const amount = currentAmount();
    if (amount < MIN_AMOUNT) {
      showError('Nominal donasi minimal Rp 1.000.');
      return;
    }
    if (amount > MAX_AMOUNT) {
      showError('Nominal donasi maksimal Rp 10.000.000.');
      return;
    }

    submitBtn.disabled = true;
    submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Membuat pembayaran…';

    try {
      const res = await fetch('/api/donation/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          donor_name: donorNameInput.value.trim(),
          message: donorMessageInput.value.trim(),
          zenime_code: donorCodeInput ? donorCodeInput.value.trim() : '',
          amount,
        }),
      });

      const data = await res.json();

      if (!res.ok || !data.ok) {
        const message = data.message || 'Gagal membuat donasi. Coba lagi.';
        showError(message);
        window.zenimeToast(message, { icon: 'fa-triangle-exclamation' });
        return;
      }

      window.location.href = data.redirect_url;
    } catch (err) {
      const message = 'Koneksi bermasalah. Periksa internet dan coba lagi.';
      showError(message);
      window.zenimeToast(message, { icon: 'fa-triangle-exclamation' });
    } finally {
      submitBtn.disabled = false;
      submitBtn.innerHTML = '<i class="fa-solid fa-qrcode"></i> Lanjut Bayar';
      updateSubmitState();
    }
  });

  updateSummary();
  updateSubmitState();
})();
