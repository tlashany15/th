/* ==========================================================================
   muslim-v20.js — صفحة «مسلم» مرتّبة
   • الأيقونات الصغيرة بتفتح شيتات (سبحة / أذكار / أدعية / رقية / ختمة)
   • مفيش كروت طويلة تحت بعضها — كل حاجة جوّه شيت صغير
   ========================================================================== */
(function () {
  'use strict';


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

  var DUAS = [
    'اللَّهُمَّ إِنِّي أَسْأَلُكَ الْعَفْوَ وَالْعَافِيَةَ فِي دِينِي وَدُنْيَايَ وَأَهْلِي وَمَالِي',
    'رَبَّنَا آتِنَا فِي الدُّنْيَا حَسَنَةً وَفِي الآخِرَةِ حَسَنَةً وَقِنَا عَذَابَ النَّارِ',
    'اللَّهُمَّ اهْدِنِي وَسَدِّدْنِي، وَاجْعَلْ لِي مِنْ كُلِّ هَمٍّ فَرَجًا وَمِنْ كُلِّ ضِيقٍ مَخْرَجًا',
    'اللَّهُمَّ إِنِّي أَعُوذُ بِكَ مِنَ الْهَمِّ وَالْحَزَنِ، وَالْعَجْزِ وَالْكَسَلِ، وَالْبُخْلِ وَالْجُبْنِ',
    'اللَّهُمَّ ارْزُقْنِي رِزْقًا حَلَالًا طَيِّبًا وَاسِعًا مِنْ حَيْثُ لَا أَحْتَسِب',
    'اللَّهُمَّ اغْفِرْ لِوَالِدَيَّ وَارْحَمْهُمَا كَمَا رَبَّيَانِي صَغِيرًا',
    'رَبِّ اشْرَحْ لِي صَدْرِي وَيَسِّرْ لِي أَمْرِي',
    'اللَّهُمَّ أَحْسِنْ خَاتِمَتِي وَتَوَفَّنِي وَأَنْتَ رَاضٍ عَنِّي'
  ];

  var RUQYA = [
    'أَعُوذُ بِاللهِ مِنَ الشَّيْطَانِ الرَّجِيمِ',
    'الفاتحة: الْحَمْدُ لِلَّهِ رَبِّ الْعَالَمِينَ … إِيَّاكَ نَعْبُدُ وَإِيَّاكَ نَسْتَعِينُ (اقرأها كاملة ٧ مرّات)',
    'آية الكرسي: اللَّهُ لَا إِلَهَ إِلَّا هُوَ الْحَيُّ الْقَيُّومُ … وَهُوَ الْعَلِيُّ الْعَظِيمُ (٣ مرّات)',
    'سورة الإخلاص والفلق والناس (٣ مرّات لكل واحدة)',
    'أَعُوذُ بِكَلِمَاتِ اللهِ التَّامَّاتِ مِنْ كُلِّ شَيْطَانٍ وَهَامَّةٍ وَمِنْ كُلِّ عَيْنٍ لَامَّةٍ (٣ مرّات)',
    'بِسْمِ اللهِ أَرْقِي نَفْسِي مِنْ كُلِّ شَرٍّ، اللهُ يَشْفِينِي وَيُعَافِينِي (٧ مرّات)'
  ];

  function lsGet(k, d) { try { var v = localStorage.getItem(k); return v === null ? d : v; } catch (e) { return d; } }
  function lsSet(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }
  function buzz(ms) { try { navigator.vibrate && navigator.vibrate(ms || 8); } catch (e) {} }
  function todayKey() { return new Date().toISOString().slice(0, 10); }

  function toast(msg) {
    var t = document.getElementById('ms20Toast');
    if (!t) { t = document.createElement('div'); t.id = 'ms20Toast'; t.className = 'ms20-toast'; document.body.appendChild(t); }
    t.textContent = msg;
    requestAnimationFrame(function () { t.classList.add('is-on'); });
    clearTimeout(t._h);
    t._h = setTimeout(function () { t.classList.remove('is-on'); }, 1700);
  }

  /* ================= شيت عام ================= */
  function sheet(title, bodyHTML, ready) {
    var ov = document.createElement('div');
    ov.className = 'ms20-ov';
    ov.innerHTML =
      '<div class="ms20-sh" role="dialog" aria-label="' + esc(title) + '">' +
        '<div class="ms20-sh-bar"></div>' +
        '<div class="ms20-sh-h"><b>' + esc(title) + '</b><button type="button" class="ms20-sh-x" aria-label="إغلاق">✕</button></div>' +
        '<div class="ms20-sh-b">' + bodyHTML + '</div>' +
      '</div>';
    document.body.appendChild(ov);
    requestAnimationFrame(function () { ov.classList.add('is-open'); });
    var untrap = null;
    var closed = false;
    function close() {
      if (closed) return;
      closed = true;
      untrap && untrap();
      ov.classList.remove('is-open');
      setTimeout(function () { ov.parentNode && ov.remove(); }, 260);
    }
    if (window.AppBack) untrap = AppBack.trap(close, ov);
    ov.addEventListener('click', function (e) {
      if (e.target === ov || (e.target.closest && e.target.closest('.ms20-sh-x'))) close();
    });
    ready && ready(ov, close);
    return close;
  }

  /* ================= الأذكار ================= */
  function openAzkar(mode) {
    var title = mode === 'e' ? 'أذكار المساء' : 'أذكار الصباح';
    var html = '<div class="ms20-list" id="ms20AzkList"></div><div class="ms20-bar"><i id="ms20AzkFill"></i></div><div class="ms20-note" id="ms20AzkNote"></div>';
    sheet(title, html, function (ov) {
      var list = ov.querySelector('#ms20AzkList');
      var fill = ov.querySelector('#ms20AzkFill');
      var note = ov.querySelector('#ms20AzkNote');
      var data = mode === 'e' ? AZKAR_E : AZKAR_M;
      function key(i) { return 'azk.' + mode + '.' + todayKey() + '.' + i; }
      function paint() {
        var done = 0;
        list.innerHTML = data.map(function (z, i) {
          var v = parseInt(lsGet(key(i), '0'), 10) || 0;
          var ok = v >= z.c;
          if (ok) done++;
          return '<button type="button" class="ms20-item' + (ok ? ' is-done' : '') + '" data-i="' + i + '">' +
            '<span class="ms20-item-t">' + esc(z.t) + '</span>' +
            '<span class="ms20-item-c">' + (ok ? 'تمّ' : v + ' / ' + z.c) + '</span></button>';
        }).join('');
        fill.style.width = Math.round((done / data.length) * 100) + '%';
        note.textContent = done === data.length
          ? 'ما شاء الله — خلّصت ' + title + ' النهاردة ✦'
          : 'خلّصت ' + done + ' من ' + data.length + ' — كمّل، فاضل شوية.';
      }
      list.addEventListener('click', function (e) {
        var b = e.target.closest('[data-i]');
        if (!b) return;
        var i = +b.getAttribute('data-i');
        var v = (parseInt(lsGet(key(i), '0'), 10) || 0) + 1;
        if (v > data[i].c) v = 0;
        lsSet(key(i), v);
        buzz(v >= data[i].c ? [14, 30, 14] : 7);
        paint();
      });
      paint();
    });
  }

  /* ================= أدعية / رقية ================= */
  function openTextList(title, arr, note) {
    var html = '<div class="ms20-list">' + arr.map(function (t) {
      return '<div class="ms20-item"><span class="ms20-item-t">' + esc(t) + '</span></div>';
    }).join('') + '</div>' + (note ? '<div class="ms20-note">' + esc(note) + '</div>' : '');
    sheet(title, html);
  }

  /* ================= التشغيل ================= */
  function boot() {
    var page = document.querySelector('.mus-page');
    if (!page) return;

    /* شارة آخر صفحة على أيقونة المصحف */
    var res = document.getElementById('musResume');
    var link = document.getElementById('musMushafLink');
    var last = parseInt(lsGet('mushaf.lastPage', '0'), 10) || 0;
    var mark = parseInt(lsGet('mushaf.bookmark', '0'), 10) || 0;
    var p = mark || last;
    if (res && p > 1) {
      res.hidden = false;
      res.textContent = p;
      if (link) link.href = link.href.split('?')[0] + '?page=' + p;
    }

    page.addEventListener('click', function (e) {
      var b = e.target.closest('[data-sheet]');
      if (!b) return;
      buzz(6);
      var k = b.getAttribute('data-sheet');
      if (k === 'azkar-m') openAzkar('m');
      else if (k === 'azkar-e') openAzkar('e');
      else if (k === 'duas') openTextList('أدعية مختارة', DUAS);
      else if (k === 'ruqya') openTextList('الرقية الشرعية', RUQYA, 'اقرأها على نفسك صباحًا ومساءً.');
    });
  }


  /* ---- نقل الكروت المساعدة (رمضان/المناسبات/آية اليوم) لتحت شبكة الأيقونات ---- */
  function relayoutWidget() {
    var w = document.getElementById('islamicWidget');
    var tiles = document.querySelector('.ms20-tiles');
    if (!w || !tiles) return;
    var cards = w.querySelectorAll(':scope > .isl-card');
    if (cards.length < 2) return;
    var box = document.getElementById('ms20Extra');
    if (!box) {
      box = document.createElement('div');
      box.id = 'ms20Extra';
      box.className = 'ms20-extra';
      tiles.parentNode.insertBefore(box, tiles.nextSibling);
    }
    for (var i = 1; i < cards.length; i++) box.appendChild(cards[i]);
  }

  function watchWidget() {
    var w = document.getElementById('islamicWidget');
    if (!w) return;
    relayoutWidget();
    var mo = new MutationObserver(function () { relayoutWidget(); });
    mo.observe(w, { childList: true });
    setTimeout(relayoutWidget, 1200);
    setTimeout(relayoutWidget, 3000);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', function(){ watchWidget(); });
  else watchWidget();

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
