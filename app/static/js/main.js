// PGC front-end — app-like helpers
(function () {
  // Class option cards
  document.querySelectorAll('.class-option').forEach(function (el) {
    el.addEventListener('click', function () {
      document.querySelectorAll('.class-option').forEach(function (x) {
        x.classList.remove('selected');
      });
      el.classList.add('selected');
    });
  });

  // Active bottom-nav by path (backup if server class missing)
  try {
    var path = window.location.pathname.replace(/\/$/, '') || '/';
    document.querySelectorAll('.bottom-nav a').forEach(function (a) {
      var href = a.getAttribute('href') || '';
      if (href === path || (href !== '/' && path.indexOf(href) === 0)) {
        a.classList.add('active');
      }
    });
  } catch (e) {}

  // Register service worker (PWA)
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', function () {
      navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(function () {});
    });
  }

  // Optional: install prompt capture
  var deferredPrompt = null;
  window.addEventListener('beforeinstallprompt', function (e) {
    e.preventDefault();
    deferredPrompt = e;
    var btn = document.getElementById('pwa-install');
    if (btn) btn.hidden = false;
  });
  document.addEventListener('click', function (ev) {
    var t = ev.target.closest && ev.target.closest('#pwa-install');
    if (!t || !deferredPrompt) return;
    deferredPrompt.prompt();
    deferredPrompt.userChoice.finally(function () {
      deferredPrompt = null;
      t.hidden = true;
    });
  });
})();
