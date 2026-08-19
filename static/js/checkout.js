/**
 * Zenime Store — logika halaman "Beli Premium".
 * - Ambil daftar paket dari GET /api/packages (bukan hardcode)
 * - Validasi format kode akun Zenime secara ringan di client
 * - Kelola pemilihan paket + ringkasan
 * - Submit checkout ke POST /payment/create, redirect ke halaman pembayaran
 */

(function () {
  const CODE_PATTERN = /^ZN-[A-Z0-9]{6}$/;

  const form = document.getElementById('checkoutForm');
  const codeInput = document.getElementById('zenimeCode');
  const codeStatus = document.getElementById('codeStatus');
  const codeStatusMsg = document.getElementById('codeStatusMsg');
  const packagesList = document.getElementById('packagesList');
  const selectedPackageIdInput = document.getElementById('selectedPackageId');
  const submitBtn = document.getElementById('submitCheckout');

  const summaryCode = document.getElementById('summaryCode');
  const summaryPackage = document.getElementById('summaryPackage');
  const summaryDuration = document.getElementById('summaryDuration');
  const summaryTotal = document.getElementById('summaryTotal');

  let packages = [];
  let selectedPackage = null;
  let codeIsValidFormat = false;

  function formatRupiah(value) {
    return 'Rp ' + Number(value).toLocaleString('id-ID');
  }

  function updateSubmitState() {
    const ready = codeIsValidFormat && !!selectedPackage;
    submitBtn.disabled = !ready;
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

  // ---- Validasi format kode akun -----------------------------------------

  codeInput.addEventListener('input', () => {
    let value = codeInput.value.toUpperCase();
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

  // ---- Render paket dari API ----------------------------------------------

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

  // ---- Submit checkout ------------------------------------------------------

  form.addEventListener('submit', async (e) => {
    e.preventDefault();

    if (!codeIsValidFormat || !selectedPackage) return;

    submitBtn.disabled = true;
    submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Membuat QRIS…';

    try {
      const res = await fetch('/payment/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          zenime_code: codeInput.value.trim(),
          package_id: selectedPackage.id,
        }),
      });

      const data = await res.json();

      if (!res.ok || !data.ok) {
        const message = data.message || 'Gagal membuat pembayaran. Coba lagi.';
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
      submitBtn.innerHTML = '<i class="fa-solid fa-qrcode"></i> Buat QRIS Pembayaran';
      updateSubmitState();
    }
  });
})();
