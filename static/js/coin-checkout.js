/**
 * Zenime Store — logika halaman "Top Up ZCoin".
 * Sama persis strukturnya dengan checkout.js (premium), bedanya:
 * - paket gak ada "duration_text", tapi ada coin_amount + bonus_coin
 * - submit ke /coin-payment/create (bukan /payment/create)
 */

(function () {
  const CODE_PATTERN = /^ZN-[A-Z0-9]{6}$/;

  const form = document.getElementById('coinCheckoutForm');
  if (!form) return;

  const codeInput = document.getElementById('zenimeCode');
  const codeStatus = document.getElementById('codeStatus');
  const codeStatusMsg = document.getElementById('codeStatusMsg');
  const packagesList = document.getElementById('packagesList');
  const selectedPackageIdInput = document.getElementById('selectedPackageId');
  const methodsList = document.getElementById('methodsList');
  const selectedMethodInput = document.getElementById('selectedMethod');
  const submitBtn = document.getElementById('submitCheckout');

  const summaryCode = document.getElementById('summaryCode');
  const summaryPackage = document.getElementById('summaryPackage');
  const summaryCoin = document.getElementById('summaryCoin');
  const summaryTotal = document.getElementById('summaryTotal');

  let packages = [];
  let methods = [];
  let selectedPackage = null;
  let selectedMethod = null;
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
    const ready = codeIsValidFormat && !!selectedPackage && !!selectedMethod;
    submitBtn.disabled = !ready;
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

    // Auto-select paket yang dikirim dari app (query param package_id).
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

  // ---- Render metode pembayaran dari API (sama endpoint dengan Premium) ---

  function renderMethods(list) {
    methodsList.innerHTML = '';

    if (!list.length) {
      methodsList.innerHTML = '<p style="color:var(--text-muted); font-size:14px;">Metode pembayaran sedang tidak tersedia. Coba beberapa saat lagi.</p>';
      return;
    }

    const groups = [];
    const groupMap = {};
    list.forEach((m) => {
      if (!groupMap[m.group]) {
        groupMap[m.group] = [];
        groups.push(m.group);
      }
      groupMap[m.group].push(m);
    });

    groups.forEach((groupName) => {
      const label = document.createElement('div');
      label.className = 'method-group-label';
      label.textContent = groupName;
      methodsList.appendChild(label);

      const grid = document.createElement('div');
      grid.className = 'methods';

      groupMap[groupName].forEach((m) => {
        const card = document.createElement('button');
        card.type = 'button';
        card.className = 'method-card';
        card.setAttribute('data-method-code', m.code);
        card.innerHTML = `
          ${m.label}
          ${m.note ? `<span class="method-card__note">${m.note}</span>` : ''}
        `;

        card.addEventListener('click', () => {
          selectedMethod = m;
          selectedMethodInput.value = m.code;

          document.querySelectorAll('.method-card').forEach((el) => el.classList.remove('is-selected'));
          card.classList.add('is-selected');

          updateSubmitState();
        });

        grid.appendChild(card);
      });

      methodsList.appendChild(grid);
    });

    const defaultCard = methodsList.querySelector('[data-method-code="QRIS"]');
    if (defaultCard) defaultCard.click();
  }

  async function loadMethods() {
    try {
      const res = await fetch('/api/payment-methods');
      if (!res.ok) throw new Error('Gagal memuat metode pembayaran');
      const data = await res.json();
      methods = data.methods || [];
      renderMethods(methods);
    } catch (err) {
      methodsList.innerHTML = `
        <div class="field-error is-visible" style="display:flex;">
          <i class="fa-solid fa-triangle-exclamation"></i>
          <span>Gagal memuat metode pembayaran. Muat ulang halaman ini.</span>
        </div>`;
    }
  }

  loadPackages();
  loadMethods();

  if (prefillCode) {
    codeInput.value = prefillCode;
    codeInput.dispatchEvent(new Event('input'));
  }

  // ---- Submit checkout ------------------------------------------------------

  form.addEventListener('submit', async (e) => {
    e.preventDefault();

    if (!codeIsValidFormat || !selectedPackage || !selectedMethod) return;

    submitBtn.disabled = true;
    submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Membuat pembayaran…';

    try {
      const res = await fetch('/coin-payment/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          zenime_code: codeInput.value.trim(),
          package_id: selectedPackage.id,
          method: selectedMethod.code,
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
      submitBtn.innerHTML = '<i class="fa-solid fa-qrcode"></i> Buat Pembayaran';
      updateSubmitState();
    }
  });
})();
