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

  // ---- Konfirmasi + cegah klik ganda pada approve/tolak -------------------
  document.addEventListener('submit', (e) => {
    const form = e.target.closest('.adm-form');
    if (!form) return;
    const msg = (form.dataset.confirm || '').replace(/\\n/g, '\n');
    if (msg && !window.confirm(msg)) {
      e.preventDefault();
      return;
    }
    // Disable semua tombol aksi di baris ini setelah event submit selesai.
    setTimeout(() => {
      form.closest('.adm-claim').querySelectorAll('button').forEach((b) => { b.disabled = true; });
      const btn = form.querySelector('button[type="submit"]');
      if (btn) btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin" aria-hidden="true"></i> Memproses…';
    }, 0);
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
