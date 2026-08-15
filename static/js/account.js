/* ==========================================================================
   account-v19.js — لمسات صفحة «حسابي» + «المحفظة»
   • مؤشّر قوة كلمة السر
   • رفع الصورة فورًا مع ضغط تلقائي (بيستخدم ChatHelpers لو موجود)
   • تنسيق أرقام المحفظة + حركة عدّ للرصيد
   ========================================================================== */
(function () {
  'use strict';

  function boot() {
    /* ---------- قوة كلمة السر ---------- */
    var pw = document.querySelector('input[name="new_password"]');
    if (pw) {
      var meter = document.createElement('div');
      meter.className = 'ac19-pw';
      meter.innerHTML = '<i></i>';
      pw.parentNode.insertAdjacentElement('afterend', meter);
      var fill = meter.querySelector('i');
      pw.addEventListener('input', function () {
        var v = pw.value || '';
        var score = 0;
        if (v.length >= 4) score++;
        if (v.length >= 8) score++;
        if (/[0-9]/.test(v)) score++;
        if (/[^\w\s]/.test(v) || /[A-Z]/.test(v)) score++;
        fill.style.width = (score / 4 * 100) + '%';
        meter.classList.toggle('is-mid', score === 2 || score === 3);
        meter.classList.toggle('is-ok', score >= 4);
      });
    }

    /* ---------- عدّ الرصيد في المحفظة ---------- */
    var val = document.getElementById('wl19Val');
    if (val) {
      var target = parseInt(val.getAttribute('data-v') || '0', 10) || 0;
      var t0 = null, dur = 700;
      function step(ts) {
        if (t0 === null) t0 = ts;
        var k = Math.min(1, (ts - t0) / dur);
        var e = 1 - Math.pow(1 - k, 3);
        val.firstChild.nodeValue = Math.round(target * e).toLocaleString('en-US');
        if (k < 1) requestAnimationFrame(step);
      }
      if (target) requestAnimationFrame(step);
    }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
