/* ==========================================================================
   nav-back-v21.js — تكنيك رجوع موحّد وواضح لكل التطبيق
   • زر الرجوع في أي صفحة: data-app-back="/الرابط-البديل"
   • لو فيه شيت/نافذة مفتوحة: الرجوع يقفلها الأول (مايطلعش من الصفحة)
   • لو مفيش تاريخ داخلي للتطبيق: يروح للرابط البديل بـ replace
     (كده مايتكوّمش تاريخ ذهاب/رجوع ويحصل لغبطة)
   • بيمسح أي شيت متعلّقة لو الصفحة رجعت من كاش المتصفح (bfcache)
   ========================================================================== */
(function () {
  'use strict';
  if (window.AppBack) return;

  var OVERLAY_SEL = '.ms20-ov, .rc-ov, .isl-ov, .mu-ov';
  var stack = [];   // شيتات مفتوحة (الأحدث آخر واحد)

  function sameOriginRef() {
    try {
      if (!document.referrer) return false;
      return new URL(document.referrer).origin === location.origin;
    } catch (e) { return false; }
  }

  /* هل فيه صفحة تطبيق قبل دي نقدر نرجع لها؟ */
  function canGoBack() {
    return history.length > 1 && sameOriginRef();
  }

  /* قفل آخر شيت مفتوح — يرجّع true لو قفل حاجة */
  function closeTop() {
    while (stack.length) {
      var top = stack.pop();
      if (top && typeof top.close === 'function' && (!top.el || top.el.parentNode)) {
        try { top.close(); } catch (e) {}
        return true;
      }
    }
    var ov = document.querySelector(OVERLAY_SEL);
    if (ov) { ov.remove(); return true; }
    return false;
  }

  var AppBack = {
    /* الرجوع الأساسي */
    go: function (fallback) {
      if (closeTop()) return;
      var target = fallback || document.body.getAttribute('data-app-home') || '/';
      if (!canGoBack()) { location.replace(target); return; }
      var left = false;
      var onLeave = function () { left = true; };
      window.addEventListener('pagehide', onLeave, { once: true });
      window.addEventListener('popstate', onLeave, { once: true });
      history.back();
      setTimeout(function () {
        window.removeEventListener('pagehide', onLeave);
        if (!left) location.replace(target);
      }, 400);
    },

    /* تسجيل شيت/نافذة عشان زر الرجوع يقفلها بدل الخروج من الصفحة */
    trap: function (closeFn, el) {
      var item = { close: closeFn, el: el || null };
      stack.push(item);
      try { history.pushState({ appSheet: 1 }, ''); } catch (e) {}
      return function untrap() {
        var i = stack.indexOf(item);
        if (i > -1) stack.splice(i, 1);
      };
    },

    hasOverlay: function () { return stack.length > 0 || !!document.querySelector(OVERLAY_SEL); }
  };

  window.AppBack = AppBack;

  /* زر الرجوع الفيزيائي / إيماءة الرجوع */
  window.addEventListener('popstate', function () {
    if (stack.length) closeTop();
  });

  /* أي زر عليه data-app-back */
  document.addEventListener('click', function (e) {
    var b = e.target.closest && e.target.closest('[data-app-back]');
    if (!b) return;
    e.preventDefault();
    AppBack.go(b.getAttribute('data-app-back') || '');
  });

  /* روابط الرجوع العادية جوه التطبيق: نستخدم رجوع حقيقي بدل إضافة صفحة جديدة
     للتاريخ — كده فتح/رجوع/فتح/رجوع مايعملش لغبطة في زر رجوع الموبايل */
  var BACK_LINK_SEL = '.wa-back, .mgx-back, .qr-back, [data-back-link]';
  document.addEventListener('click', function (e) {
    if (e.defaultPrevented || e.button !== 0) return;
    if (e.metaKey || e.ctrlKey || e.altKey || e.shiftKey) return;
    var a = e.target.closest && e.target.closest(BACK_LINK_SEL);
    if (!a || a.tagName !== 'A' || !a.href) return;
    var url;
    try { url = new URL(a.href, location.href); } catch (err) { return; }
    if (url.origin !== location.origin) return;
    e.preventDefault();
    if (AppBack.hasOverlay()) { closeTop(); return; }
    try {
      if (sameOriginRef() && new URL(document.referrer).pathname === url.pathname) {
        history.back();
        return;
      }
    } catch (err) {}
    location.replace(url.href);
  });

  /* رجوع الصفحة من كاش المتصفح: نظّف أي شيت متعلّقة */
  window.addEventListener('pageshow', function (e) {
    if (!e.persisted) return;
    stack.length = 0;
    var list = document.querySelectorAll(OVERLAY_SEL);
    for (var i = 0; i < list.length; i++) list[i].remove();
    document.body.classList.remove('no-scroll', 'is-locked');
  });
})();
