/**
 * Zenime Store — logika halaman "Top Up ZCoin dari Luar Negeri" (manual/QRIS pribadi).
 * Sama seperti bayar-manual.js tapi buat ZCoin: /api/coin-packages &
 * submit ke /api/coin-manual-payment/create.
 */

(function () {
  const CODE_PATTERN = /^ZN-[A-Z0-9]{6}$/;

  const form = document.getElementById('coinManualCheckoutForm');
  if (!form) return;

  const codeInput = document.getElementById('zenimeCode');
  const codeStatus = document.getElementById('codeStatus');
  const codeStatusMsg = document.getElementById('codeStatusMsg');
  const packagesList = document.getElementById('packagesList');
  const selectedPackageIdInput = document.getElementById('selectedPackageId');
  const submitBtn = document.getElementById('submitManualCheckout');

  const summaryCode = document.getElementById('summaryCode');
  const summaryPackage = document.getElementById('summaryPackage');
  const summaryCoin = document.getElementById('summaryCoin');
  const summaryTotal = document.getElementById('summaryTotal');

  let selectedPackage = null;
  let codeIsValidFormat = false;

  const prefillCode = form.dataset.prefillCode || '';
  const prefillPackageId = form.dataset.prefillPackageId || '';

  function formatNumber(value) {
    return Number(value).toLocaleString('id-ID');
  }

  function formatRupiah(value) {
    return 'Rp ' + formatNumber(value);
  }

  function totalCoin(pkg) {
    return (pkg.coin_amount || 0) + (pkg.bonus_coin || 0);
  }

  function updateSubmitState() {
    submitBtn.disabled = !(codeIsValidFormat && !!selectedPackage);
  }

  function updateSummary() {
    summaryCode.textContent = codeInput.value.trim() || '—';
    if (selectedPackage) {
      summaryPackage.textContent = selectedPackage.label;
      summaryCoin.textContent = formatNumber(totalCoin(selectedPackage)) + ' ZCoin';
      summaryTotal.textContent = formatRupiah(selectedPackage.price);
    } else {
      summaryPackage.textContent = '—';
      summaryCoin.textContent = '—';
      summaryTotal.textContent = 'Rp 0';
    }
  }

  codeInput.addEventListener('input', () => {
    const value = codeInput.value.toUpperCase();
    codeInput.value = value;
    const trimmed = value.trim();

    if (trimmed.length === 0) {
      codeInput.classList.remove('is-invalid');
      codeStatus.classList.remove('is-visible', 'is-ok', 'is-bad');
      codeIsValidFormat = false;
    } else if (CODE_PATTERN.test(trimmed)) {
      codeInput.classList.remove('is-invalid');
      codeStatus.classList.add('is-visible', 'is-ok');
      codeStatus.classList.remove('is-bad');
      codeStatus.querySelector('i').className = 'fa-solid fa-circle-check';
      codeStatusMsg.textContent = 'Format kode valid';
      codeIsValidFormat = true;
    } else {
      codeInput.classList.add('is-invalid');
      codeStatus.classList.add('is-visible', 'is-bad');
      codeStatus.classList.remove('is-ok');
      codeStatus.querySelector('i').className = 'fa-solid fa-triangle-exclamation';
      codeStatusMsg.textContent = 'Format harus ZN- diikuti 6 huruf/angka';
      codeIsValidFormat = false;
    }

    updateSummary();
    updateSubmitState();
  });

  function renderPackages(list) {
    packagesList.innerHTML = '';

    if (!list.length) {
      packagesList.innerHTML = '<p style="color:var(--text-muted); font-size:14px;">Paket ZCoin sedang tidak tersedia. Coba beberapa saat lagi.</p>';
      return;
    }

    list.forEach((pkg) => {
      const card = document.createElement('button');
      card.type = 'button';
      card.className = 'package-card';
      card.setAttribute('data-package-id', pkg.id);

      const bonusLine = pkg.bonus_coin > 0
        ? `<div class="package-card__duration" style="color:var(--accent); font-size:12px;">${formatNumber(pkg.coin_amount)} + bonus ${formatNumber(pkg.bonus_coin)}</div>`
        : '';

      card.innerHTML = `
        <span class="package-card__radio"></span>
        <div class="package-card__duration">${formatNumber(totalCoin(pkg))} ZCoin</div>
        ${bonusLine}
        <div class="package-card__price">${formatRupiah(pkg.price)}</div>
      `;

      card.addEventListener('click', () => {
        selectedPackage = pkg;
        selectedPackageIdInput.value = pkg.id;

        document.querySelectorAll('.package-card').forEach((el) => el.classList.remove('is-selected'));
        card.classList.add('is-selected');

        updateSummary();
        updateSubmitState();
      });

      packagesList.appendChild(card);
    });

    if (prefillPackageId) {
      const match = packagesList.querySelector(`[data-package-id="${prefillPackageId}"]`);
      if (match) match.click();
    }
  }

  async function loadPackages() {
    try {
      const res = await fetch('/api/coin-packages');
      if (!res.ok) throw new Error('Gagal memuat paket');
      const data = await res.json();
      renderPackages(data.packages || []);
    } catch (err) {
      packagesList.innerHTML = `
        <div class="field-error is-visible" style="display:flex;">
          <i class="fa-solid fa-triangle-exclamation"></i>
          <span>Gagal memuat daftar paket. Muat ulang halaman ini.</span>
        </div>`;
    }
  }

  loadPackages();

  if (prefillCode) {
    codeInput.value = prefillCode;
    codeInput.dispatchEvent(new Event('input'));
  }

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!codeIsValidFormat || !selectedPackage) return;

    submitBtn.disabled = true;
    submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Membuat klaim…';

    try {
      const res = await fetch('/api/coin-manual-payment/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          zenime_code: codeInput.value.trim(),
          package_id: selectedPackage.id,
        }),
      });

      const data = await res.json();

      if (!res.ok || !data.ok) {
        const message = data.message || 'Gagal membuat klaim. Coba lagi.';
        if (data.field === 'zenime_code') {
          codeInput.classList.add('is-invalid');
          codeStatus.classList.add('is-visible', 'is-bad');
          codeStatus.classList.remove('is-ok');
          codeStatus.querySelector('i').className = 'fa-solid fa-triangle-exclamation';
          codeStatusMsg.textContent = message;
        }
        window.zenimeToast(message, { icon: 'fa-triangle-exclamation' });
        return;
      }

      window.location.href = data.redirect_url;
    } catch (err) {
      window.zenimeToast('Koneksi bermasalah. Periksa internet dan coba lagi.', { icon: 'fa-triangle-exclamation' });
    } finally {
      submitBtn.disabled = false;
      submitBtn.innerHTML = '<i class="fa-solid fa-qrcode"></i> Lanjut ke QRIS';
      updateSubmitState();
    }
  });
})();
