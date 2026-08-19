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
})();
