/* motion-v6.js — أنيميشن انتقال بين الصفحات (دخول من اليمين/الشمال) */
(function () {
  'use strict';
  if (window.__MOTION_V6) return;
  window.__MOTION_V6 = true;

  var DIR_KEY = '__nav_dir_v6';
  var LEAVE_MS = 200;

  function body() { return document.body; }

  function playEnter() {
    var b = body();
    if (!b) return;
    var dir = 'fwd';
    try { dir = sessionStorage.getItem(DIR_KEY) || 'fwd'; } catch (e) {}
    b.classList.remove('pg-leave', 'pg-leave-back', 'pg-enter', 'pg-enter-back');
    b.classList.add(dir === 'back' ? 'pg-enter-back' : 'pg-enter');
    setTimeout(function () {
      b.classList.remove('pg-enter', 'pg-enter-back');
    }, 900);
  }

  function setDir(dir) {
    try { sessionStorage.setItem(DIR_KEY, dir); } catch (e) {}
  }

  if (document.readyState !== 'loading') playEnter();
  else document.addEventListener('DOMContentLoaded', playEnter);
  window.addEventListener('pageshow', function (e) { if (e.persisted) playEnter(); });

  window.addEventListener('popstate', function () { setDir('back'); });

  function isBackLink(a) {
    if (a.classList.contains('wa-back') || a.classList.contains('back-btn')) return true;
    var lbl = a.getAttribute('aria-label') || '';
    return lbl.indexOf('رجوع') >= 0;
  }

  document.addEventListener(
    'click',
    function (e) {
      if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      var a = e.target && e.target.closest ? e.target.closest('a[href]') : null;
      if (!a) return;
      if (a.target && a.target !== '_self') return;
      if (a.hasAttribute('download')) return;
      var raw = a.getAttribute('href') || '';
      if (!raw || raw.charAt(0) === '#' || /^(mailto:|tel:|javascript:)/i.test(raw)) return;
      var url;
      try { url = new URL(a.href, location.href); } catch (err) { return; }
      if (url.origin !== location.origin) return;
      if (url.href === location.href) return;

      var back = isBackLink(a);
      setDir(back ? 'back' : 'fwd');

      var b = body();
      if (!b) return;
      e.preventDefault();
      b.classList.add(back ? 'pg-leave-back' : 'pg-leave');
      setTimeout(function () { location.href = url.href; }, LEAVE_MS);
    },
    true
  );
})();
