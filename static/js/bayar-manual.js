/**
 * Zenime Store — logika halaman "Bayar dari Luar Negeri" (manual/QRIS pribadi).
 * Sama seperti checkout.js tapi tanpa pilihan metode (selalu QRIS manual)
 * dan submit ke /api/manual-payment/create, bukan /payment/create.
 */

(function () {
  const CODE_PATTERN = /^ZN-[A-Z0-9]{6}$/;

  const form = document.getElementById('manualCheckoutForm');
  if (!form) return;

  const codeInput = document.getElementById('zenimeCode');
  const codeStatus = document.getElementById('codeStatus');
  const codeStatusMsg = document.getElementById('codeStatusMsg');
  const packagesList = document.getElementById('packagesList');
  const selectedPackageIdInput = document.getElementById('selectedPackageId');
  const submitBtn = document.getElementById('submitManualCheckout');

  const summaryCode = document.getElementById('summaryCode');
  const summaryPackage = document.getElementById('summaryPackage');
  const summaryDuration = document.getElementById('summaryDuration');
  const summaryTotal = document.getElementById('summaryTotal');

  let packages = [];
  let selectedPackage = null;
  let codeIsValidFormat = false;

  const prefillCode = form.dataset.prefillCode || '';
  const prefillPackageId = form.dataset.prefillPackageId || '';

  function formatRupiah(value) {
    return 'Rp ' + Number(value).toLocaleString('id-ID');
  }

  function updateSubmitState() {
    submitBtn.disabled = !(codeIsValidFormat && !!selectedPackage);
  }

  function updateSummary() {
    summaryCode.textContent = codeInput.value.trim() || '—';
    if (selectedPackage) {
      summaryPackage.textContent = selectedPackage.label;
      summaryDuration.textContent = selectedPackage.duration_text;
      summaryTotal.textContent = formatRupiah(selectedPackage.price);
    } else {
      summaryPackage.textContent = '—';
      summaryDuration.textContent = '—';
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
      packagesList.innerHTML = '<p style="color:var(--text-muted); font-size:14px;">Paket sedang tidak tersedia. Coba beberapa saat lagi.</p>';
      return;
    }

    list.forEach((pkg) => {
      const card = document.createElement('button');
      card.type = 'button';
      card.className = 'package-card';
      card.setAttribute('data-package-id', pkg.id);

      card.innerHTML = `
        ${pkg.badge ? `<span class="package-card__badge">${pkg.badge}</span>` : ''}
        <span class="package-card__radio"></span>
        <div class="package-card__duration">${pkg.label}</div>
        <div class="package-card__price">${formatRupiah(pkg.price)} <small>/ ${pkg.duration_text}</small></div>
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
      const res = await fetch('/api/packages');
      if (!res.ok) throw new Error('Gagal memuat paket');
      const data = await res.json();
      packages = data.packages || [];
      renderPackages(packages);
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
      const res = await fetch('/api/manual-payment/create', {
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
