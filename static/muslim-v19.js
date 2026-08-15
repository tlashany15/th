/* ==========================================================================
   muslim-v19.js — تطويرات صفحة «مسلم»
   ------------------------------------------------------------------
   • كارت الختمة: نسبة إنجازك في المصحف + متابعة من آخر صفحة
   • سبحة رقمية: عدّاد بأهداف (33 / 100 / 1000) + اهتزاز + تخزين + إجمالي اليوم
   • أذكار الصباح والمساء: كروت تتقلّب واحدة واحدة مع عدّاد التكرار
   • كل حاجة محلية 100% وبتشتغل من غير نت
   ========================================================================== */
(function () {
  'use strict';

  var TASBIH = [
    { t: 'سُبْحَانَ اللهِ', g: 33 },
    { t: 'الحَمْدُ لِلَّهِ', g: 33 },
    { t: 'اللهُ أَكْبَرُ', g: 34 },
    { t: 'لَا إِلَهَ إِلَّا اللهُ', g: 100 },
    { t: 'أَسْتَغْفِرُ اللهَ وَأَتُوبُ إِلَيْهِ', g: 100 },
    { t: 'سُبْحَانَ اللهِ وَبِحَمْدِهِ', g: 100 },
    { t: 'اللَّهُمَّ صَلِّ وَسَلِّمْ عَلَى نَبِيِّنَا مُحَمَّد', g: 100 }
  ];

  var AZKAR_M = [
    { t: 'أَصْبَحْنَا وَأَصْبَحَ المُلْكُ لِلَّهِ، وَالحَمْدُ لِلَّهِ، لَا إِلَهَ إِلَّا اللهُ وَحْدَهُ لَا شَرِيكَ لَهُ', c: 1 },
    { t: 'اللَّهُمَّ بِكَ أَصْبَحْنَا، وَبِكَ أَمْسَيْنَا، وَبِكَ نَحْيَا، وَبِكَ نَمُوتُ، وَإِلَيْكَ النُّشُورُ', c: 1 },
    { t: 'سُبْحَانَ اللهِ وَبِحَمْدِهِ', c: 100 },
    { t: 'بِسْمِ اللهِ الَّذِي لَا يَضُرُّ مَعَ اسْمِهِ شَيْءٌ فِي الأَرْضِ وَلَا فِي السَّمَاءِ وَهُوَ السَّمِيعُ العَلِيمُ', c: 3 },
    { t: 'رَضِيتُ بِاللهِ رَبًّا، وَبِالإِسْلَامِ دِينًا، وَبِمُحَمَّدٍ ﷺ نَبِيًّا', c: 3 },
    { t: 'حَسْبِيَ اللهُ لَا إِلَهَ إِلَّا هُوَ، عَلَيْهِ تَوَكَّلْتُ، وَهُوَ رَبُّ العَرْشِ العَظِيمِ', c: 7 }
  ];
  var AZKAR_E = [
    { t: 'أَمْسَيْنَا وَأَمْسَى المُلْكُ لِلَّهِ، وَالحَمْدُ لِلَّهِ، لَا إِلَهَ إِلَّا اللهُ وَحْدَهُ لَا شَرِيكَ لَهُ', c: 1 },
    { t: 'اللَّهُمَّ بِكَ أَمْسَيْنَا، وَبِكَ أَصْبَحْنَا، وَبِكَ نَحْيَا، وَبِكَ نَمُوتُ، وَإِلَيْكَ المَصِيرُ', c: 1 },
    { t: 'أَعُوذُ بِكَلِمَاتِ اللهِ التَّامَّاتِ مِنْ شَرِّ مَا خَلَقَ', c: 3 },
    { t: 'سُبْحَانَ اللهِ وَبِحَمْدِهِ عَدَدَ خَلْقِهِ وَرِضَا نَفْسِهِ وَزِنَةَ عَرْشِهِ وَمِدَادَ كَلِمَاتِهِ', c: 3 },
    { t: 'اللَّهُمَّ عَافِنِي فِي بَدَنِي، اللَّهُمَّ عَافِنِي فِي سَمْعِي، اللَّهُمَّ عَافِنِي فِي بَصَرِي', c: 3 },
    { t: 'أَسْتَغْفِرُ اللهَ وَأَتُوبُ إِلَيْهِ', c: 100 }
  ];

  function lsGet(k, d) { try { var v = localStorage.getItem(k); return v === null ? d : v; } catch (e) { return d; } }
  function lsSet(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }
  function buzz(ms) { try { navigator.vibrate && navigator.vibrate(ms || 10); } catch (e) {} }
  function todayKey() { return new Date().toISOString().slice(0, 10); }

  /* ================== كارت الختمة ================== */
  function khatmaCard() {
    var read = [];
    try { read = JSON.parse(lsGet('mushaf.readPages', '[]')) || []; } catch (e) {}
    var last = parseInt(lsGet('mushaf.lastPage', '0'), 10) || 0;
    var mark = parseInt(lsGet('mushaf.bookmark', '0'), 10) || 0;
    var pct = Math.min(100, Math.round((read.length / 604) * 100));
    var target = mark || last;

    return '' +
      '<section class="ms19-khatma">' +
        '<div class="ms19-khatma-top">' +
          '<div class="ms19-ring" style="--p:' + pct + '">' +
            '<b>' + pct + '<i>٪</i></b>' +
          '</div>' +
          '<div class="ms19-khatma-b">' +
            '<span class="ms19-tag">ختمتي</span>' +
            '<b>' + read.length + ' صفحة من 604</b>' +
            '<small>' + (target ? 'آخر وقفة عند صفحة ' + target : 'ابدأ أول صفحة النهاردة') + '</small>' +
          '</div>' +
        '</div>' +
        '<a class="ms19-khatma-go" href="/mushaf' + (target ? '?page=' + target : '') + '">' +
          (target ? 'كمّل قراءتك' : 'ابدأ القراءة') +
          '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 5l-7 7 7 7"/></svg>' +
        '</a>' +
      '</section>';
  }

  /* ================== السبحة ================== */
  function tasbihCard() {
    return '' +
      '<section class="ms19-card ms19-tas" id="ms19Tas">' +
        '<div class="ms19-card-h">' +
          '<span class="ms19-card-ic">' +
            '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><circle cx="12" cy="4.6" r="2.1"/><circle cx="17.6" cy="7.4" r="2.1"/><circle cx="19.4" cy="13.4" r="2.1"/><circle cx="4.6" cy="7.4" r="2.1"/><circle cx="4.6" cy="13.4" r="2.1"/><circle cx="12" cy="19.4" r="2.4"/></svg>' +
          '</span>' +
          '<div><b>السبحة</b><small>اضغط في أي مكان في الدايرة</small></div>' +
          '<button type="button" class="ms19-reset" id="ms19Reset" aria-label="تصفير">' +
            '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3.5 12a8.5 8.5 0 1 0 3-6.5"/><path d="M3 4v5h5"/></svg>' +
          '</button>' +
        '</div>' +
        '<div class="ms19-zikr" id="ms19Zikr"></div>' +
        '<button type="button" class="ms19-counter" id="ms19Count">' +
          '<svg class="ms19-counter-ring" viewBox="0 0 120 120" aria-hidden="true">' +
            '<circle cx="60" cy="60" r="52"></circle>' +
            '<circle cx="60" cy="60" r="52" id="ms19Arc"></circle>' +
          '</svg>' +
          '<span class="ms19-counter-n" id="ms19N">0</span>' +
          '<span class="ms19-counter-g" id="ms19G">/ 33</span>' +
        '</button>' +
        '<div class="ms19-tas-foot">' +
          '<button type="button" class="ms19-swap" id="ms19Prev">الذكر السابق</button>' +
          '<span id="ms19Total">إجمالي اليوم: 0</span>' +
          '<button type="button" class="ms19-swap" id="ms19Next">الذكر التالي</button>' +
        '</div>' +
      '</section>';
  }

  function initTasbih() {
    var idx = parseInt(lsGet('tas.idx', '0'), 10) || 0;
    var zEl = document.getElementById('ms19Zikr');
    var nEl = document.getElementById('ms19N');
    var gEl = document.getElementById('ms19G');
    var arc = document.getElementById('ms19Arc');
    var tEl = document.getElementById('ms19Total');
    if (!zEl) return;

    var CIRC = 2 * Math.PI * 52;
    arc.style.strokeDasharray = CIRC;

    function key() { return 'tas.n.' + idx; }
    function totalKey() { return 'tas.total.' + todayKey(); }
    function n() { return parseInt(lsGet(key(), '0'), 10) || 0; }
    function total() { return parseInt(lsGet(totalKey(), '0'), 10) || 0; }

    function paint() {
      var z = TASBIH[idx];
      zEl.textContent = z.t;
      var v = n();
      nEl.textContent = v;
      gEl.textContent = '/ ' + z.g;
      var p = Math.min(1, v / z.g);
      arc.style.strokeDashoffset = CIRC * (1 - p);
      arc.classList.toggle('is-done', v >= z.g);
      tEl.textContent = 'إجمالي اليوم: ' + total();
      lsSet('tas.idx', idx);
    }

    document.getElementById('ms19Count').addEventListener('click', function () {
      var z = TASBIH[idx];
      var v = n() + 1;
      lsSet(key(), v);
      lsSet(totalKey(), total() + 1);
      buzz(v % z.g === 0 ? [18, 40, 18] : 8);
      paint();
      if (v % z.g === 0) {
        var c = document.getElementById('ms19Count');
        c.classList.remove('is-pulse'); void c.offsetWidth; c.classList.add('is-pulse');
      }
    });
    document.getElementById('ms19Reset').addEventListener('click', function () {
      lsSet(key(), 0); buzz(14); paint();
    });
    document.getElementById('ms19Next').addEventListener('click', function () {
      idx = (idx + 1) % TASBIH.length; paint();
    });
    document.getElementById('ms19Prev').addEventListener('click', function () {
      idx = (idx - 1 + TASBIH.length) % TASBIH.length; paint();
    });
    paint();
  }

  /* ================== الأذكار ================== */
  function azkarCard() {
    var h = new Date().getHours();
    var evening = (h >= 15 || h < 4);
    return '' +
      '<section class="ms19-card ms19-azk" id="ms19Azk" data-mode="' + (evening ? 'e' : 'm') + '">' +
        '<div class="ms19-card-h">' +
          '<span class="ms19-card-ic ms19-card-ic-gold">' +
            '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6l1.4 1.4M17 17l1.4 1.4M18.4 5.6L17 7M7 17l-1.4 1.4"/><circle cx="12" cy="12" r="3.6"/></svg>' +
          '</span>' +
          '<div><b>أذكار الصباح والمساء</b><small>اضغط على الذكر لما تخلّصه</small></div>' +
        '</div>' +
        '<div class="ms19-azk-segs">' +
          '<button type="button" class="ms19-azk-seg' + (evening ? '' : ' is-on') + '" data-m="m">الصباح</button>' +
          '<button type="button" class="ms19-azk-seg' + (evening ? ' is-on' : '') + '" data-m="e">المساء</button>' +
        '</div>' +
        '<div class="ms19-azk-list" id="ms19AzkList"></div>' +
        '<div class="ms19-azk-bar"><i id="ms19AzkFill"></i></div>' +
        '<div class="ms19-azk-note" id="ms19AzkNote"></div>' +
      '</section>';
  }

  function initAzkar() {
    var wrap = document.getElementById('ms19Azk');
    if (!wrap) return;
    var list = document.getElementById('ms19AzkList');
    var fill = document.getElementById('ms19AzkFill');
    var note = document.getElementById('ms19AzkNote');
    var mode = wrap.getAttribute('data-mode');

    function data() { return mode === 'e' ? AZKAR_E : AZKAR_M; }
    function key(i) { return 'azk.' + mode + '.' + todayKey() + '.' + i; }

    function paint() {
      var d = data(), done = 0;
      list.innerHTML = d.map(function (z, i) {
        var v = parseInt(lsGet(key(i), '0'), 10) || 0;
        var ok = v >= z.c;
        if (ok) done++;
        return '<button type="button" class="ms19-azk-item' + (ok ? ' is-done' : '') + '" data-i="' + i + '">' +
          '<span class="ms19-azk-t">' + esc(z.t) + '</span>' +
          '<span class="ms19-azk-c">' + (ok ? 'تمّ' : v + ' / ' + z.c) + '</span>' +
        '</button>';
      }).join('');
      var pct = Math.round((done / d.length) * 100);
      fill.style.width = pct + '%';
      note.textContent = done === d.length
        ? 'ما شاء الله — خلّصت أذكار ' + (mode === 'e' ? 'المساء' : 'الصباح') + ' النهاردة ✦'
        : 'خلّصت ' + done + ' من ' + d.length + ' — كمّل، فاضل شوية.';
    }

    list.addEventListener('click', function (e) {
      var b = e.target.closest('[data-i]');
      if (!b) return;
      var i = +b.getAttribute('data-i');
      var z = data()[i];
      var v = (parseInt(lsGet(key(i), '0'), 10) || 0) + 1;
      if (v > z.c) v = 0;
      lsSet(key(i), v);
      buzz(v >= z.c ? [14, 30, 14] : 7);
      paint();
    });
    wrap.querySelectorAll('.ms19-azk-seg').forEach(function (s) {
      s.addEventListener('click', function () {
        mode = s.getAttribute('data-m');
        wrap.setAttribute('data-mode', mode);
        wrap.querySelectorAll('.ms19-azk-seg').forEach(function (x) { x.classList.toggle('is-on', x === s); });
        paint();
      });
    });
    paint();
  }

  /* ================== التركيب ================== */
  function boot() {
    var page = document.querySelector('.mus-page');
    if (!page) return;

    var mushafLink = document.getElementById('musMushafLink');
    var anchor = mushafLink || page.querySelector('.mus-dua');
    if (!anchor) return;

    var host = document.createElement('div');
    host.className = 'ms19-wrap';
    host.innerHTML = khatmaCard() + tasbihCard() + azkarCard();
    anchor.insertAdjacentElement('afterend', host);

    initTasbih();
    initAzkar();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
