/* reveal-v8.js — دخول العناصر واحد ورا التاني بالجافاسكربت (Web Animations API)
   مش متأثر بإعداد "تقليل الحركة" في WebView، وبيشتغل على كل الصفحات + الشريط الجانبي. */
(function () {
  'use strict';
  if (window.__REVEAL_V8) return;
  window.__REVEAL_V8 = true;

  var EASE = 'cubic-bezier(.22,1,.36,1)';

  function canAnimate(el) {
    return el && typeof el.animate === 'function';
  }

  function stagger(nodes, opts) {
    opts = opts || {};
    var dur = opts.duration || 320;
    var step = opts.step || 45;
    var x = opts.x || 0;
    var y = opts.y == null ? 12 : opts.y;
    var i = 0;
    Array.prototype.forEach.call(nodes, function (el) {
      if (!canAnimate(el)) return;
      var delay = i * step;
      i++;
      try {
        el.animate(
          [
            { opacity: 0, transform: 'translate3d(' + x + 'px,' + y + 'px,0)' },
            { opacity: 1, transform: 'none' }
          ],
          { duration: dur, delay: delay, easing: EASE, fill: 'both' }
        );
      } catch (e) {}
    });
  }

  /* ---------- 1) محتوى الصفحة يدخل عنصر ورا عنصر ---------- */
  function revealPage() {
    var roots = document.querySelectorAll('.container, .wa-wrap > .wa-body, .tg-list');
    var done = false;
    Array.prototype.forEach.call(roots, function (root) {
      var kids = [];
      Array.prototype.forEach.call(root.children, function (c) {
        var cs = window.getComputedStyle(c);
        if (cs.display === 'none' || cs.position === 'fixed') return;
        kids.push(c);
      });
      if (!kids.length) return;
      done = true;
      stagger(kids, { step: 45, duration: 320, y: 12 });
    });
    if (!done) {
      var main = document.querySelector('main') || document.body;
      stagger(main.children, { step: 40, duration: 300, y: 10 });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', revealPage);
  } else {
    revealPage();
  }
  window.addEventListener('pageshow', function (e) {
    if (e.persisted) revealPage();
  });

  /* ---------- 2) الشريط الجانبي: العناصر تدخل من اليمين واحدة ورا التانية ---------- */
  function revealSidebar(side) {
    var groups = [];
    var header = side.querySelector('.sidebar-header');
    if (header) groups.push(header);
    Array.prototype.forEach.call(
      side.querySelectorAll('.sidebar-nav > *, .sidebar-section-title, .sidebar-workers > *'),
      function (el) { groups.push(el); }
    );
    if (!groups.length) return;
    stagger(groups, { step: 38, duration: 340, x: 26, y: 0 });
  }

  function watchSidebar() {
    var side = document.getElementById('appSidebar');
    if (!side || typeof MutationObserver === 'undefined') return;
    var wasOpen = side.classList.contains('is-open');
    if (wasOpen) revealSidebar(side);
    new MutationObserver(function () {
      var isOpen = side.classList.contains('is-open');
      if (isOpen && !wasOpen) revealSidebar(side);
      wasOpen = isOpen;
    }).observe(side, { attributes: true, attributeFilter: ['class'] });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', watchSidebar);
  } else {
    watchSidebar();
  }
})();
