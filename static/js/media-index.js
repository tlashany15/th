/* ==========================================================================
   media-index-v19.js
   • تشغيل صفحة فهرس الصور (فلترة + عارض + تنزيل)
   • وكمان: يضيف زر «فهرس الصور» في هيدر الدردشة الخاصة والمجموعة تلقائيًا
   ========================================================================== */
(function () {
  'use strict';

  /* ============ 1) زر فهرس الصور في هيدر الدردشة ============ */
  function injectHeadButton() {
    var wrap = document.querySelector('.wa-wrap');
    var head = document.querySelector('.wa-head');
    if (!wrap || !head || head.querySelector('.wa-head-media')) return;

    var isGroup = wrap.classList.contains('wa-group');
    var otherId = wrap.getAttribute('data-other-id');
    var href = isGroup ? '/group/media' : (otherId ? '/chat/' + otherId + '/media' : null);
    if (!href) return;

    var a = document.createElement('a');
    a.className = 'wa-head-media';
    a.href = href;
    a.title = 'فهرس الصور';
    a.setAttribute('aria-label', 'فهرس الصور');
    a.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="16" rx="2.5"/><circle cx="8.8" cy="9.6" r="1.7"/><path d="M3.6 17.4l4.9-4.6 3.6 3.3 3-2.6 5.3 4.5"/></svg>';
    head.appendChild(a);
  }

  /* ============ 2) صفحة الفهرس ============ */
  function initIndexPage() {
    var page = document.querySelector('.mgx');
    if (!page) return;

    var grid = document.getElementById('mgxGrid');
    var scope = page.getAttribute('data-scope') || 'chat';

    /* --- الفلترة --- */
    var segs = [].slice.call(page.querySelectorAll('.mgx-seg'));
    segs.forEach(function (btn) {
      btn.addEventListener('click', function () {
        segs.forEach(function (b) { b.classList.toggle('is-on', b === btn); });
        var f = btn.getAttribute('data-filter');
        cells().forEach(function (c) {
          var mine = c.getAttribute('data-mine') === '1';
          c.hidden = (f === 'mine' && !mine) || (f === 'theirs' && mine);
        });
      });
    });

    /* --- حجم العرض (2 / 3 / 4 أعمدة) --- */
    var COLS = [3, 2, 4];
    var ci = 0;
    try { ci = Math.max(0, COLS.indexOf(parseInt(localStorage.getItem('media.cols') || '3', 10))); } catch (e) {}
    applyCols();
    var zoomBtn = document.getElementById('mgxZoom');
    if (zoomBtn) zoomBtn.addEventListener('click', function () {
      ci = (ci + 1) % COLS.length;
      applyCols();
      try { localStorage.setItem('media.cols', COLS[ci]); } catch (e) {}
    });
    function applyCols() { if (grid) grid.style.setProperty('--mgx-cols', COLS[ci]); }

    /* --- العارض --- */
    var lb = document.getElementById('mgxLb');
    if (!lb || !grid) return;
    var img = document.getElementById('mgxLbImg');
    var nameEl = document.getElementById('mgxLbName');
    var timeEl = document.getElementById('mgxLbTime');
    var posEl = document.getElementById('mgxLbPos');
    var dl = document.getElementById('mgxLbDl');
    var cur = 0;

    function cells() { return [].slice.call(grid.querySelectorAll('.mgx-cell')); }
    function visible() { return cells().filter(function (c) { return !c.hidden; }); }

    function show(i) {
      var list = visible();
      if (!list.length) return;
      cur = (i + list.length) % list.length;
      var c = list[cur];
      var id = c.getAttribute('data-id');
      img.src = '/media/' + scope + '/' + id;
      nameEl.textContent = c.getAttribute('data-sender') || '';
      timeEl.textContent = fmt(c.getAttribute('data-time'));
      posEl.textContent = (cur + 1) + ' / ' + list.length;
      dl.href = '/media/' + scope + '/' + id + '?dl=1';
      try { dl.download = 'صور تطبيق التحصين_' + id + '.jpg'; } catch (e) {}
    }

    function fmt(iso) {
      if (!iso) return '';
      var d = new Date(iso);
      if (isNaN(d)) return '';
      try {
        return d.toLocaleDateString('ar-EG', { day: 'numeric', month: 'long', year: 'numeric' }) +
               ' · ' + d.toLocaleTimeString('ar-EG', { hour: '2-digit', minute: '2-digit' });
      } catch (e) { return d.toLocaleString(); }
    }

    function open(i) { lb.hidden = false; document.body.style.overflow = 'hidden'; show(i); }
    function close() { lb.hidden = true; document.body.style.overflow = ''; img.src = ''; }

    grid.addEventListener('click', function (e) {
      var c = e.target.closest('.mgx-cell');
      if (!c) return;
      open(visible().indexOf(c));
    });
    document.getElementById('mgxClose').addEventListener('click', close);
    document.getElementById('mgxPrev').addEventListener('click', function () { show(cur - 1); });
    document.getElementById('mgxNext').addEventListener('click', function () { show(cur + 1); });
    lb.querySelector('.mgx-lb-stage').addEventListener('click', function (e) {
      if (e.target === e.currentTarget) close();
    });
    document.addEventListener('keydown', function (e) {
      if (lb.hidden) return;
      if (e.key === 'Escape') close();
      if (e.key === 'ArrowLeft') show(cur + 1);
      if (e.key === 'ArrowRight') show(cur - 1);
    });

    /* سحب أفقي للتنقل */
    var sx = 0;
    lb.addEventListener('touchstart', function (e) { sx = e.touches[0].clientX; }, { passive: true });
    lb.addEventListener('touchend', function (e) {
      var dx = (e.changedTouches[0].clientX - sx);
      if (Math.abs(dx) > 55) show(cur + (dx > 0 ? -1 : 1));
    }, { passive: true });
  }

  function boot() { injectHeadButton(); initIndexPage(); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
