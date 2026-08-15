/* ==========================================================================
   mushaf-v20.js — طبقة ترتيب فوق قارئ المصحف
   • الفهرس بيفتح مع المصحف أول ما تدخل
   • مشغّل التلاوة بقى جوّه الصفحة عشان زرار «الفهرس» يبان
   • زرار «استماع» ينقلك لقسم القراءة بالصوت على نفس السورة
   ========================================================================== */
(function () {
  'use strict';

  var SURAH_PAGES = [1,2,50,77,106,128,151,177,187,208,221,235,249,255,262,267,282,293,305,312,322,332,342,350,359,367,377,385,396,404,411,415,418,428,434,440,446,453,458,467,477,483,489,496,499,502,507,511,515,518,520,523,526,528,531,534,537,542,545,549,551,553,554,556,558,560,562,564,566,568,570,572,574,575,577,578,580,582,583,585,586,587,587,589,590,591,591,592,593,594,595,595,596,596,597,597,598,598,599,599,600,600,601,601,601,602,602,602,603,603,603,604,604,604];

  function surahOfPage(p) {
    var s = 1;
    for (var i = 0; i < SURAH_PAGES.length; i++) if (p >= SURAH_PAGES[i]) s = i + 1;
    return s;
  }
  function curPage() {
    var m = /[?&]page=(\d+)/.exec(location.search);
    if (m) return parseInt(m[1], 10);
    try { return parseInt(localStorage.getItem('mushaf.lastPage') || '1', 10) || 1; } catch (e) { return 1; }
  }

  function waitFor(sel, cb, tries) {
    tries = tries || 60;
    var el = document.querySelector(sel);
    if (el) return cb(el);
    if (tries <= 0) return;
    setTimeout(function () { waitFor(sel, cb, tries - 1); }, 100);
  }

  function boot() {
    var root = document.getElementById('musReader');
    if (!root) return;

    /* 1) المشغّل يدخل جوّه الصفحة فوق الفوتر مباشرة */
    waitFor('#qr19Bar', function (bar) {
      var foot = root.querySelector('.qr-foot');
      if (foot && bar.parentNode !== root) {
        root.insertBefore(bar, foot);
        bar.classList.add('is-inline');
      }
      /* 2) زرار استماع (قسم القراءة بالصوت) */
      if (!document.getElementById('qr20Listen')) {
        var b = document.createElement('button');
        b.type = 'button';
        b.id = 'qr20Listen';
        b.className = 'qr20-listen';
        b.setAttribute('aria-label', 'قسم القراءة بالصوت');
        b.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M4 14v-3a8 8 0 0 1 16 0v3"/><rect x="2.5" y="13" width="4.5" height="7" rx="2"/><rect x="17" y="13" width="4.5" height="7" rx="2"/></svg>';
        b.addEventListener('click', function () {
          location.href = '/muslim/recite?surah=' + surahOfPage(curPage());
        });
        bar.appendChild(b);
      }
    });

    /* 3) الفهرس يفتح مع المصحف */
    waitFor('#qrJump', function (jump) {
      var qs = new URLSearchParams(location.search);
      if (qs.get('index') === '0') return;
      setTimeout(function () {
        if (!document.querySelector('.qr-ov')) jump.click();
      }, 450);
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
