/* instant-nav.js — تنقل فوري بين الصفحات
 * - Preloads same-origin links on hover / touch / viewport (like Turbo/Quicklink)
 * - Adds a slim top progress bar during navigation
 * - Uses the View Transitions API for buttery page swaps where supported
 * Idempotent + safe on iOS Safari + no external deps.
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

  // Trigger bar on any navigation
  window.addEventListener('beforeunload', startBar);
  window.addEventListener('pageshow', endBar);
  document.addEventListener('DOMContentLoaded', endBar);

  // Any form submit shows the bar
  document.addEventListener('submit', function (e) {
    if (e.defaultPrevented) return;
    startBar();
  }, true);

  // ---------- Prefetch on hover / touch / viewport ----------
  var prefetched = Object.create(null);
  function isEligibleLink(a) {
    if (!a || a.tagName !== 'A') return false;
    if (!a.href) return false;
    if (a.target && a.target !== '_self') return false;
    if (a.hasAttribute('download')) return false;
    if (a.dataset.noPrefetch === '1') return false;
    var url;
    try { url = new URL(a.href, location.href); } catch (e) { return false; }
    if (url.origin !== location.origin) return false;
    if (url.pathname === location.pathname && url.search === location.search) return false;
    // skip file downloads, chat sends, POST endpoints
    if (/\/(logout|login|register|api\/|static\/|uploads\/|media\/)/.test(url.pathname)) return false;
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
  function onHover(e) {
    var a = e.target.closest && e.target.closest('a');
    var href = isEligibleLink(a);
    if (href) prefetch(href);
  }
  document.addEventListener('mouseover', onHover, { passive: true });
  document.addEventListener('touchstart', onHover, { passive: true });
  document.addEventListener('focusin', onHover);

  // Viewport-visible links (quicklink-style)
  if ('IntersectionObserver' in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (!en.isIntersecting) return;
        var href = isEligibleLink(en.target);
        if (href) prefetch(href);
        io.unobserve(en.target);
      });
    }, { rootMargin: '200px' });
    function scan() {
      document.querySelectorAll('a[href]').forEach(function (a) {
        if (a.dataset.__io === '1') return;
        a.dataset.__io = '1';
        io.observe(a);
      });
    }
    if (document.body) scan();
    else document.addEventListener('DOMContentLoaded', scan);
    new MutationObserver(scan).observe(document.documentElement, { childList: true, subtree: true });
  }

  // ---------- Click accelerator + View Transitions ----------
  document.addEventListener('click', function (e) {
    if (e.defaultPrevented) return;
    if (e.button !== 0) return;
    if (e.metaKey || e.ctrlKey || e.altKey || e.shiftKey) return;
    var a = e.target.closest && e.target.closest('a');
    var href = isEligibleLink(a);
    if (!href) return;
    startBar();
    if (document.startViewTransition) {
      e.preventDefault();
      document.startViewTransition(function () {
        location.href = href;
      });
    }
  }, true);
})();
