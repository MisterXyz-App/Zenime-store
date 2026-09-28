/**
 * Zenime Store — utilitas global (toast, copy-to-clipboard).
 * Dipakai di semua halaman lewat base.html.
 */

(function () {
  const toastEl = document.getElementById('globalToast');
  const toastMsgEl = document.getElementById('globalToastMsg');
  let toastTimer = null;

  window.zenimeToast = function (message, { icon = 'fa-circle-info' } = {}) {
    if (!toastEl || !toastMsgEl) return;

    toastEl.querySelector('i').className = `fa-solid ${icon}`;
    toastMsgEl.textContent = message;
    toastEl.classList.add('is-visible');

    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
      toastEl.classList.remove('is-visible');
    }, 3400);
  };

  window.zenimeCopyToClipboard = async function (text) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (err) {
      // Fallback untuk browser/WebView lama
      const temp = document.createElement('textarea');
      temp.value = text;
      temp.style.position = 'fixed';
      temp.style.opacity = '0';
      document.body.appendChild(temp);
      temp.select();
      let ok = false;
      try {
        ok = document.execCommand('copy');
      } catch (e) {
        ok = false;
      }
      document.body.removeChild(temp);
      return ok;
    }
  };

  document.addEventListener('click', async (e) => {
    const btn = e.target.closest('.copy-btn');
    if (!btn) return;
    const value = btn.getAttribute('data-copy');
    if (!value) return;
    const ok = await window.zenimeCopyToClipboard(value);
    window.zenimeToast(ok ? 'Disalin ke clipboard' : 'Gagal menyalin', {
      icon: ok ? 'fa-circle-check' : 'fa-triangle-exclamation',
    });
  });

  // Toggle tema: default OLED (tanpa atribut data-theme, lihat :root di
  // style.css). Preferensi disimpan di localStorage dan dibaca lagi secara
  // sinkron di <head> (lihat base.html) supaya tidak ada flash saat reload.
  const THEME_KEY = 'zenime-theme';
  const themeToggle = document.getElementById('themeToggle');
  const metaThemeColor = document.getElementById('metaThemeColor');

  function applyThemeUI(isLight) {
    if (themeToggle) {
      const icon = themeToggle.querySelector('i');
      icon.className = isLight ? 'fa-solid fa-moon' : 'fa-solid fa-sun';
      themeToggle.setAttribute('aria-pressed', String(isLight));
      themeToggle.setAttribute('aria-label', isLight ? 'Ganti ke tema OLED' : 'Ganti ke tema terang');
    }
    if (metaThemeColor) {
      metaThemeColor.setAttribute('content', isLight ? '#ffffff' : '#000000');
    }
  }

  // Sinkronkan ikon toggle dengan tema yang sudah diterapkan lebih dulu
  applyThemeUI(document.documentElement.getAttribute('data-theme') === 'light');

  if (themeToggle) {
    themeToggle.addEventListener('click', () => {
      const isCurrentlyLight = document.documentElement.getAttribute('data-theme') === 'light';
      const next = isCurrentlyLight ? null : 'light';

      if (next) {
        document.documentElement.setAttribute('data-theme', next);
      } else {
        document.documentElement.removeAttribute('data-theme');
      }

      try {
        localStorage.setItem(THEME_KEY, next || 'dark');
      } catch (e) {
        /* localStorage tidak tersedia, tema tetap berubah untuk sesi ini */
      }

      applyThemeUI(!isCurrentlyLight);
    });
  }

  // Navigasi: garis bawah muncul setelah halaman discroll, dan menu tarik-turun
  // untuk layar kecil (tautan utama disembunyikan di bawah 900px).
  const nav = document.getElementById('siteNav');
  if (nav) {
    const onScroll = () => {
      nav.classList.toggle('is-scrolled', window.scrollY > 8);
    };
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });

    const toggle = document.getElementById('navToggle');
    const panel = document.getElementById('navPanel');

    if (toggle && panel) {
      const setOpen = (open) => {
        nav.classList.toggle('is-open', open);
        toggle.setAttribute('aria-expanded', String(open));
        toggle.setAttribute('aria-label', open ? 'Tutup menu' : 'Buka menu');
        toggle.querySelector('i').className = open ? 'fa-solid fa-xmark' : 'fa-solid fa-bars';
      };

      toggle.addEventListener('click', () => {
        setOpen(!nav.classList.contains('is-open'));
      });

      // Tutup menu setelah salah satu tautan diketuk
      panel.addEventListener('click', (e) => {
        if (e.target.closest('a')) setOpen(false);
      });

      document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && nav.classList.contains('is-open')) {
          setOpen(false);
          toggle.focus();
        }
      });

      // Kembali ke layout desktop: pastikan state menu ikut bersih
      window.matchMedia('(min-width: 901px)').addEventListener('change', (e) => {
        if (e.matches) setOpen(false);
      });
    }
  }
})();
