/* app-core.js — حراسات عامة للتطبيق: الأخطاء، التمرير، منع النسخ، الحضور اللحظي */
(function () {
  'use strict';

  /* 1) حارس الأخطاء: أي خطأ في سكربت لا يوقف باقي الصفحة */
  window.addEventListener('error', function (e) {
    try { console.warn('[app] script error:', e && (e.message || e)); } catch (_) {}
  }, true);
  window.addEventListener('unhandledrejection', function (e) {
    try { console.warn('[app] promise error:', e && e.reason); } catch (_) {}
  });
  document.documentElement.classList.add('js-on');

  /* 2) روح الواجهة الموحّدة خارج لوحة الأدمن */
  (function () {
    var p = location.pathname || '';
    if (p.indexOf('/admin') !== 0) {
      document.documentElement.classList.add('ap-polish');
      document.addEventListener('DOMContentLoaded', function () {
        if (document.body) document.body.classList.add('ap-polish');
      });
    }
  })();

  /* 3) حارس التمرير: يفك القفل لو اتقفل بالغلط من غير مودال مفتوح */
  function unlockScroll() {
    try {
      if (document.querySelector('.is-open, .modal.is-open, .th-modal.is-open, [data-lock="1"]')) return;
      var h = document.documentElement, b = document.body;
      if (h && h.style.overflow) h.style.overflow = '';
      if (b && b.style.overflow) b.style.overflow = '';
      if (b && b.style.position === 'fixed') b.style.position = '';
    } catch (_) {}
  }
  document.addEventListener('DOMContentLoaded', unlockScroll);
  window.addEventListener('pageshow', unlockScroll);
  setInterval(unlockScroll, 1500);

  /* 4) منع النسخ خارج حقول الكتابة */
  function isEditable(t) {
    if (!t) return false;
    var tag = (t.tagName || '').toLowerCase();
    return tag === 'input' || tag === 'textarea' || t.isContentEditable === true;
  }
  function stopIfNotEditable(e) {
    if (isEditable(e.target)) return true;
    e.preventDefault();
    return false;
  }
  ['contextmenu', 'copy', 'cut', 'dragstart', 'selectstart'].forEach(function (evt) {
    document.addEventListener(evt, stopIfNotEditable);
  });
  document.addEventListener('keydown', function (e) {
    var k = (e.key || '').toLowerCase();
    if (!isEditable(e.target) && (e.ctrlKey || e.metaKey) &&
        (k === 'c' || k === 'x' || k === 'a' || k === 's' || k === 'p' || k === 'u')) {
      e.preventDefault();
      return false;
    }
  });

  /* 5) الحضور اللحظي */
  function startPresence() {
    if (!document.body || document.body.dataset.noPing) return;
    var doPing = function () {
      try {
        fetch('/me/ping', { method: 'POST', headers: { 'X-Requested-With': 'fetch' }, keepalive: true });
      } catch (_) {}
    };
    doPing();
    setInterval(function () { if (!document.hidden) doPing(); }, 15000);
    document.addEventListener('visibilitychange', function () { if (!document.hidden) doPing(); });
    window.addEventListener('focus', doPing);
    window.addEventListener('pagehide', doPing);
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', startPresence);
  } else {
    startPresence();
  }
})();
