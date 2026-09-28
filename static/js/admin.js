/**
 * Dashboard admin — filter, pencarian, urutan, umur klaim, lightbox bukti.
 * Semua bekerja di sisi browser pada daftar klaim yang sudah dimuat server.
 */
(function () {
  const list = document.getElementById('admClaims');
  if (!list) return;

  const rows = Array.from(list.querySelectorAll('.adm-claim'));
  const searchEl = document.getElementById('admSearch');
  const kindWrap = document.getElementById('admKind');
  const noProofBtn = document.getElementById('admNoProof');
  const sortEl = document.getElementById('admSort');
  const countEl = document.getElementById('admCount');
  const emptyEl = document.getElementById('admNoResult');
  const resetBtn = document.getElementById('admReset');
  const thead = document.querySelector('.adm-thead');

  const state = { q: '', kind: 'all', noProof: false, sort: 'oldest' };

  const ts = (row) => {
    const t = Date.parse(row.dataset.created);
    return Number.isNaN(t) ? 0 : t;
  };

  const sorters = {
    oldest: (a, b) => ts(a) - ts(b),
    newest: (a, b) => ts(b) - ts(a),
    amount: (a, b) => Number(b.dataset.amount) - Number(a.dataset.amount),
  };

  function apply() {
    const q = state.q.trim().toLowerCase();
    let shown = 0;

    rows.forEach((row) => {
      const okKind = state.kind === 'all' || row.dataset.kind === state.kind;
      const okProof = !state.noProof || row.dataset.proof === '0';
      const okText = !q || row.dataset.search.includes(q);
      const visible = okKind && okProof && okText;
      row.hidden = !visible;
      if (visible) shown += 1;
    });

    // Urutkan ulang DOM sesuai pilihan.
    rows.slice().sort(sorters[state.sort]).forEach((row) => list.appendChild(row));

    countEl.textContent = `Menampilkan ${shown} dari ${rows.length} klaim`;
    emptyEl.hidden = shown !== 0;
    list.hidden = shown === 0;
    if (thead) thead.hidden = shown === 0;
  }

  if (searchEl) {
    searchEl.addEventListener('input', () => { state.q = searchEl.value; apply(); });
  }

  if (kindWrap) {
    kindWrap.addEventListener('click', (e) => {
      const btn = e.target.closest('[data-kind]');
      if (!btn) return;
      state.kind = btn.dataset.kind;
      kindWrap.querySelectorAll('[data-kind]').forEach((b) => {
        const on = b === btn;
        b.classList.toggle('is-active', on);
        b.setAttribute('aria-pressed', String(on));
      });
      apply();
    });
  }

  if (noProofBtn) {
    noProofBtn.addEventListener('click', () => {
      state.noProof = !state.noProof;
      noProofBtn.classList.toggle('is-active', state.noProof);
      noProofBtn.setAttribute('aria-pressed', String(state.noProof));
      apply();
    });
  }

  if (sortEl) {
    sortEl.addEventListener('change', () => { state.sort = sortEl.value; apply(); });
  }

  if (resetBtn) {
    resetBtn.addEventListener('click', () => {
      state.q = ''; state.kind = 'all'; state.noProof = false; state.sort = 'oldest';
      if (searchEl) searchEl.value = '';
      if (sortEl) sortEl.value = 'oldest';
      if (noProofBtn) { noProofBtn.classList.remove('is-active'); noProofBtn.setAttribute('aria-pressed', 'false'); }
      if (kindWrap) {
        kindWrap.querySelectorAll('[data-kind]').forEach((b) => {
          const on = b.dataset.kind === 'all';
          b.classList.toggle('is-active', on);
          b.setAttribute('aria-pressed', String(on));
        });
      }
      apply();
    });
  }

  // ---- Umur klaim: teks + warna, diperbarui tiap menit --------------------
  function formatWait(ms) {
    const min = Math.floor(ms / 60000);
    if (min < 1) return 'Baru saja';
    if (min < 60) return `${min} mnt`;
    const h = Math.floor(min / 60);
    const m = min % 60;
    if (h < 24) return m ? `${h} j ${m} m` : `${h} j`;
    const d = Math.floor(h / 24);
    const hr = h % 24;
    return hr ? `${d} h ${hr} j` : `${d} h`;
  }

  function refreshAges() {
    const now = Date.now();
    rows.forEach((row) => {
      const el = row.querySelector('[data-age]');
      const t = Date.parse(row.dataset.created);
      if (!el || Number.isNaN(t)) return;
      const ms = Math.max(0, now - t);
      el.textContent = formatWait(ms);
      el.classList.remove('adm-age--ok', 'adm-age--warn', 'adm-age--danger');
      el.classList.add(ms >= 6 * 3600e3 ? 'adm-age--danger' : ms >= 2 * 3600e3 ? 'adm-age--warn' : 'adm-age--ok');
    });
  }
  refreshAges();
  setInterval(refreshAges, 60000);

  // ---- Dialog konfirmasi approve/tolak (pengganti window.confirm) --------
  const dlg = document.getElementById('admConfirm');
  const dlgEls = dlg && {
    icon: document.getElementById('admConfirmIcon'),
    title: document.getElementById('admConfirmTitle'),
    desc: document.getElementById('admConfirmDesc'),
    warn: document.getElementById('admConfirmWarn'),
    code: document.getElementById('admConfirmCode'),
    product: document.getElementById('admConfirmProduct'),
    amount: document.getElementById('admConfirmAmount'),
    ok: document.getElementById('admConfirmOk'),
    cancel: document.getElementById('admConfirmCancel'),
  };
  let dlgResolve = null;
  let dlgFocus = null;

  const COPY = {
    approve: {
      icon: 'fa-check', tone: 'ok', ok: 'Ya, approve',
      title: 'Approve klaim ini?',
      desc: (d) => `Ini langsung mengaktifkan ${d.kind}${d.kind === 'ZCoin' ? ' ke akun pengguna' : ''} dan tidak bisa dibatalkan.`,
    },
    reject: {
      icon: 'fa-xmark', tone: 'danger', ok: 'Ya, tolak',
      title: 'Tolak klaim ini?',
      desc: () => 'Klaim akan ditandai ditolak dan pengguna tidak menerima produknya.',
    },
  };

  function closeDialog(result) {
    if (dlg.hidden) return;
    dlg.hidden = true;
    document.body.classList.remove('adm-noscroll');
    document.removeEventListener('keydown', onDlgKey, true);
    if (dlgFocus && dlgFocus.focus) dlgFocus.focus();
    const done = dlgResolve; dlgResolve = null;
    if (done) done(result);
  }

  function onDlgKey(e) {
    if (e.key === 'Escape') { e.preventDefault(); closeDialog(false); return; }
    if (e.key !== 'Tab') return;
    // Kunci fokus di dalam dialog.
    const f = [dlgEls.cancel, dlgEls.ok];
    const i = f.indexOf(document.activeElement);
    if (e.shiftKey && i <= 0) { e.preventDefault(); f[f.length - 1].focus(); }
    else if (!e.shiftKey && i === f.length - 1) { e.preventDefault(); f[0].focus(); }
  }

  function askConfirm(form) {
    const d = form.dataset;
    const kind = COPY[d.action] || COPY.approve;
    const noProof = d.action === 'approve' && d.noproof === '1';

    dlgEls.icon.className = 'adm-modal__icon adm-modal__icon--' + (noProof ? 'warn' : kind.tone);
    dlgEls.icon.innerHTML = `<i class="fa-solid ${noProof ? 'fa-triangle-exclamation' : kind.icon}"></i>`;
    dlgEls.title.textContent = kind.title;
    dlgEls.desc.textContent = kind.desc(d);
    dlgEls.warn.hidden = !noProof;
    dlgEls.code.textContent = d.code || '-';
    dlgEls.product.textContent = d.product || '-';
    dlgEls.amount.textContent = d.amount || '-';
    dlgEls.ok.textContent = noProof ? 'Tetap approve' : kind.ok;
    dlgEls.ok.className = 'btn ' + (d.action === 'reject' ? 'btn-danger' : noProof ? 'btn-warn' : 'btn-primary');

    dlgFocus = document.activeElement;
    dlg.hidden = false;
    document.body.classList.add('adm-noscroll');
    document.addEventListener('keydown', onDlgKey, true);
    // Fokus awal ke "Batal" supaya Enter tidak sengaja menyetujui.
    dlgEls.cancel.focus();
    return new Promise((resolve) => { dlgResolve = resolve; });
  }

  if (dlg) {
    dlgEls.ok.addEventListener('click', () => closeDialog(true));
    dlgEls.cancel.addEventListener('click', () => closeDialog(false));
    dlg.addEventListener('click', (e) => { if (e.target === dlg) closeDialog(false); });
  }

  // ---- Submit approve/tolak: konfirmasi dulu, lalu cegah klik ganda -------
  function lockAndSubmit(form) {
    const row = form.closest('.adm-claim');
    const btn = form.querySelector('button[type="submit"]');
    if (btn) btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin" aria-hidden="true"></i> Memproses…';
    // form.submit() tidak memicu event submit lagi, jadi tidak ada loop.
    form.submit();
    // Nonaktifkan setelah submit berjalan (tombol disabled tidak ikut terkirim).
    setTimeout(() => row.querySelectorAll('button').forEach((b) => { b.disabled = true; }), 0);
  }

  document.addEventListener('submit', (e) => {
    const form = e.target.closest('.adm-form');
    if (!form) return;
    e.preventDefault();
    if (!dlg) { lockAndSubmit(form); return; }
    askConfirm(form).then((ok) => { if (ok) lockAndSubmit(form); });
  });

  // ---- Lightbox bukti transfer -------------------------------------------
  const box = document.getElementById('admLightbox');
  const boxImg = document.getElementById('admLightboxImg');
  const boxClose = document.getElementById('admLightboxClose');
  let lastFocus = null;

  function openBox(src, trigger) {
    lastFocus = trigger;
    boxImg.src = src;
    box.hidden = false;
    document.body.classList.add('adm-noscroll');
    boxClose.focus();
  }
  function closeBox() {
    box.hidden = true;
    boxImg.src = '';
    document.body.classList.remove('adm-noscroll');
    if (lastFocus) lastFocus.focus();
  }

  list.addEventListener('click', (e) => {
    const thumb = e.target.closest('.adm-thumb[data-full]');
    if (thumb) openBox(thumb.dataset.full, thumb);
  });
  if (box) {
    box.addEventListener('click', (e) => { if (e.target === box) closeBox(); });
    boxClose.addEventListener('click', closeBox);
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && !box.hidden) closeBox();
    });
  }

  apply();
})();
