/* instant-nav.js — تنقل أسرع بين الصفحات
 * - شريط تقدّم رفيع أعلى الصفحة أثناء التنقل
 * - Prefetch آمن: على الهوفر/اللمس فقط، ولروابط العرض (GET) المسموحة فقط
 *
 * مهم جدًا: قبل كده كان بيعمل prefetch لكل الروابط الظاهرة في الشاشة،
 * وده كان بيفتح روابط ليها تأثير على السيرفر (زي الدخول بحساب مستخدم آخر)
 * من غير ما المستخدم يضغط. دلوقتي فيه قايمة منع + منع أي رابط عليه
 * data-no-prefetch، وبرضه الـ prefetch بقى على نية المستخدم بس.
 */
(function () {
  'use strict';
  if (window.__INSTANT_NAV_READY) return;
  window.__INSTANT_NAV_READY = true;

  // ---------- Top progress bar ----------
  var bar = document.createElement('div');
  bar.className = 'inav-bar';
  bar.innerHTML = '<span class="inav-bar-fill"></span>';
  var progressT = 0;
  function startBar() {
    bar.classList.add('is-on');
    var fill = bar.firstElementChild;
    var pct = 8;
    clearInterval(progressT);
    fill.style.width = pct + '%';
    progressT = setInterval(function () {
      pct = Math.min(pct + (100 - pct) * 0.08, 92);
      fill.style.width = pct + '%';
    }, 180);
  }
  function endBar() {
    clearInterval(progressT);
    var fill = bar.firstElementChild;
    fill.style.width = '100%';
    setTimeout(function () {
      bar.classList.remove('is-on');
      fill.style.width = '0%';
    }, 240);
  }
  function attachBar() {
    if (!document.body || bar.parentNode) return;
    document.body.appendChild(bar);
  }
  if (document.body) attachBar();
  else document.addEventListener('DOMContentLoaded', attachBar);

  window.addEventListener('beforeunload', startBar);
  window.addEventListener('pageshow', endBar);
  document.addEventListener('DOMContentLoaded', endBar);

  document.addEventListener('submit', function (e) {
    if (e.defaultPrevented) return;
    startBar();
  }, true);

  // ---------- Prefetch آمن ----------
  // روابط ممنوع لمسها نهائيًا (ليها تأثير على السيرفر أو مش صفحات عرض)
  var BLOCKED = /\/(impersonate|unimpersonate|logout|login|register|delete|remove|clear|reset|settle|close|toggle|revert|migrate|export|import|api\/|static\/|uploads\/|media\/)/i;

  var prefetched = Object.create(null);
  function eligible(a) {
    if (!a || a.tagName !== 'A' || !a.href) return false;
    if (a.target && a.target !== '_self') return false;
    if (a.hasAttribute('download')) return false;
    if (a.dataset.noPrefetch === '1') return false;
    if (a.getAttribute('href').charAt(0) === '#') return false;
    var url;
    try { url = new URL(a.href, location.href); } catch (e) { return false; }
    if (url.origin !== location.origin) return false;
    if (url.protocol !== 'http:' && url.protocol !== 'https:') return false;
    if (url.pathname === location.pathname && url.search === location.search) return false;
    if (BLOCKED.test(url.pathname)) return false;
    return url.href;
  }
  function prefetch(href) {
    if (!href || prefetched[href]) return;
    prefetched[href] = 1;
    try {
      var l = document.createElement('link');
      l.rel = 'prefetch';
      l.as = 'document';
      l.href = href;
      document.head.appendChild(l);
    } catch (e) {}
  }
  var hoverT = 0;
  function onHover(e) {
    var a = e.target.closest && e.target.closest('a');
    var href = eligible(a);
    if (!href) return;
    clearTimeout(hoverT);
    hoverT = setTimeout(function () { prefetch(href); }, 60);
  }
  document.addEventListener('mouseover', onHover, { passive: true });
  document.addEventListener('touchstart', onHover, { passive: true });

  // ---------- شريط التقدّم عند الضغط ----------
  document.addEventListener('click', function (e) {
    if (e.defaultPrevented) return;
    if (e.button !== 0) return;
    if (e.metaKey || e.ctrlKey || e.altKey || e.shiftKey) return;
    var a = e.target.closest && e.target.closest('a');
    if (!a || !a.href) return;
    if (a.target && a.target !== '_self') return;
    if (a.getAttribute('href').charAt(0) === '#') return;
    var url;
    try { url = new URL(a.href, location.href); } catch (err) { return; }
    if (url.origin !== location.origin) return;
    startBar();
  }, true);

  window.addEventListener('pageshow', endBar);
})();
