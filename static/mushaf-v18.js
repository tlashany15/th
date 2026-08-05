/* ==========================================================================
   mushaf-v18.js — قارئ المصحف الكامل
   • تصفّح 604 صفحة زي المصحف بالظبط
   • علامة على آخر صفحة وقفت فيها + متابعة تلقائية
   • فهرس السور والأجزاء + الانتقال لصفحة
   • وضع ورقي/ليلي + تكبير الخط + تخزين الصفحات للعمل بدون نت
   ========================================================================== */
(function () {
  'use strict';

var SURAH_NAMES = ["الفاتحة", "البقرة", "آل عمران", "النساء", "المائدة", "الأنعام", "الأعراف", "الأنفال", "التوبة", "يونس", "هود", "يوسف", "الرعد", "ابراهيم", "الحجر", "النحل", "الإسراء", "الكهف", "مريم", "طه", "الأنبياء", "الحج", "المؤمنون", "النور", "الفرقان", "الشعراء", "النمل", "القصص", "العنكبوت", "الروم", "لقمان", "السجدة", "الأحزاب", "سبإ", "فاطر", "يس", "الصافات", "ص", "الزمر", "غافر", "فصلت", "الشورى", "الزخرف", "الدخان", "الجاثية", "الأحقاف", "محمد", "الفتح", "الحجرات", "ق", "الذاريات", "الطور", "النجم", "القمر", "الرحمن", "الواقعة", "الحديد", "المجادلة", "الحشر", "الممتحنة", "الصف", "الجمعة", "المنافقون", "التغابن", "الطلاق", "التحريم", "الملك", "القلم", "الحاقة", "المعارج", "نوح", "الجن", "المزمل", "المدثر", "القيامة", "الانسان", "المرسلات", "النبإ", "النازعات", "عبس", "التكوير", "الإنفطار", "المطففين", "الإنشقاق", "البروج", "الطارق", "الأعلى", "الغاشية", "الفجر", "البلد", "الشمس", "الليل", "الضحى", "الشرح", "التين", "العلق", "القدر", "البينة", "الزلزلة", "العاديات", "القارعة", "التكاثر", "العصر", "الهمزة", "الفيل", "قريش", "الماعون", "الكوثر", "الكافرون", "النصر", "المسد", "الإخلاص", "الفلق", "الناس"];
var SURAH_PAGES = [1, 2, 50, 77, 106, 128, 151, 177, 187, 208, 221, 235, 249, 255, 262, 267, 282, 293, 305, 312, 322, 332, 342, 350, 359, 367, 377, 385, 396, 404, 411, 415, 418, 428, 434, 440, 446, 453, 458, 467, 477, 483, 489, 496, 499, 502, 507, 511, 515, 518, 520, 523, 526, 528, 531, 534, 537, 542, 545, 549, 551, 553, 554, 556, 558, 560, 562, 564, 566, 568, 570, 572, 574, 575, 577, 578, 580, 582, 583, 585, 586, 587, 587, 589, 590, 591, 591, 592, 593, 594, 595, 595, 596, 596, 597, 597, 598, 598, 599, 599, 600, 600, 601, 601, 601, 602, 602, 602, 603, 603, 603, 604, 604, 604];
var SURAH_AYAS = [7, 286, 200, 176, 120, 165, 206, 75, 129, 109, 123, 111, 43, 52, 99, 128, 111, 110, 98, 135, 112, 78, 118, 64, 77, 227, 93, 88, 69, 60, 34, 30, 73, 54, 45, 83, 182, 88, 75, 85, 54, 53, 89, 59, 37, 35, 38, 29, 18, 45, 60, 49, 62, 55, 78, 96, 29, 22, 24, 13, 14, 11, 11, 18, 12, 12, 30, 52, 52, 44, 28, 28, 20, 56, 40, 31, 50, 40, 46, 42, 29, 19, 36, 25, 22, 17, 19, 26, 30, 20, 15, 21, 11, 8, 8, 19, 5, 8, 8, 11, 11, 8, 3, 9, 5, 4, 7, 3, 6, 3, 5, 4, 5, 6];
var SURAH_PLACE = ["مكية", "مدنية", "مدنية", "مدنية", "مدنية", "مكية", "مكية", "مدنية", "مدنية", "مكية", "مكية", "مكية", "مدنية", "مكية", "مكية", "مكية", "مكية", "مكية", "مكية", "مكية", "مكية", "مدنية", "مكية", "مدنية", "مكية", "مكية", "مكية", "مكية", "مكية", "مكية", "مكية", "مكية", "مدنية", "مكية", "مكية", "مكية", "مكية", "مكية", "مكية", "مكية", "مكية", "مكية", "مكية", "مكية", "مكية", "مكية", "مدنية", "مدنية", "مدنية", "مكية", "مكية", "مكية", "مكية", "مكية", "مدنية", "مكية", "مدنية", "مدنية", "مدنية", "مدنية", "مدنية", "مدنية", "مدنية", "مدنية", "مدنية", "مدنية", "مكية", "مكية", "مكية", "مكية", "مكية", "مكية", "مكية", "مكية", "مكية", "مدنية", "مكية", "مكية", "مكية", "مكية", "مكية", "مكية", "مكية", "مكية", "مكية", "مكية", "مكية", "مكية", "مكية", "مكية", "مكية", "مكية", "مكية", "مكية", "مكية", "مكية", "مكية", "مدنية", "مدنية", "مكية", "مكية", "مكية", "مكية", "مكية", "مكية", "مكية", "مكية", "مكية", "مكية", "مدنية", "مكية", "مكية", "مكية", "مكية"];
var JUZ_PAGES = [1, 22, 42, 62, 82, 102, 121, 142, 162, 182, 201, 222, 242, 262, 282, 302, 322, 342, 362, 382, 402, 422, 442, 462, 482, 502, 522, 542, 562, 582];

  var MAX_PAGE = 604;
  var LS = {
    last:  'mushaf.lastPage',
    mark:  'mushaf.bookmark',
    fs:    'mushaf.fontSize',
    paper: 'mushaf.paper'
  };

  function lsGet(k, d){ try { var v = localStorage.getItem(k); return v === null ? d : v; } catch(e){ return d; } }
  function lsSet(k, v){ try { localStorage.setItem(k, v); } catch(e){} }

  function clampPage(n){ n = parseInt(n, 10); if (!n || n < 1) n = 1; if (n > MAX_PAGE) n = MAX_PAGE; return n; }
  function esc(s){ return String(s == null ? '' : s).replace(/[&<>"]/g, function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
  function arNum(n){ return String(n).replace(/\d/g, function(d){ return '٠١٢٣٤٥٦٧٨٩'[+d]; }); }

  function juzOfPage(p){
    var j = 1;
    for (var i = 0; i < JUZ_PAGES.length; i++) if (p >= JUZ_PAGES[i]) j = i + 1;
    return j;
  }
  function surahOfPage(p){
    var s = 0;
    for (var i = 0; i < SURAH_PAGES.length; i++) if (p >= SURAH_PAGES[i]) s = i;
    return s; // index
  }

  var IC = {
    back:  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"><path d="M15.5 19.5L8 12l7.5-7.5"/></svg>',
    mark:  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M6.5 3.5h11a1.5 1.5 0 0 1 1.5 1.5v15.2l-7-4.2-7 4.2V5a1.5 1.5 0 0 1 1.5-1.5z"/></svg>',
    markOn:'<svg viewBox="0 0 24 24" fill="currentColor"><path d="M6.5 3.5h11A1.5 1.5 0 0 1 19 5v15.2l-7-4.2-7 4.2V5a1.5 1.5 0 0 1 1.5-1.5z"/></svg>',
    aa:    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 19l5.5-14L14 19M4.8 14.5h7.4M15.5 19l3.2-8 3.3 8M16.6 16.6h4.2"/></svg>',
    sun:   '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M19.1 4.9l-1.4 1.4M6.3 17.7l-1.4 1.4"/></svg>',
    moon:  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>',
    prev:  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 5l7 7-7 7"/></svg>',
    next:  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 5l-7 7 7 7"/></svg>',
    search:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.2-4.2"/></svg>'
  };

  var root, bodyEl, titleEl, subEl, markBtn, prevBtn, nextBtn, jumpBtn;
  var cur = 1;
  var cache = {};
  var reqId = 0;

  /* ============ التخزين المؤقت للصفحات ============ */
  function cacheGet(p){
    if (cache[p]) return cache[p];
    try {
      var raw = localStorage.getItem('mushaf.p.' + p);
      if (raw) { cache[p] = JSON.parse(raw); return cache[p]; }
    } catch(e){}
    return null;
  }
  function cachePut(p, ayahs){
    cache[p] = ayahs;
    try { localStorage.setItem('mushaf.p.' + p, JSON.stringify(ayahs)); } catch(e){}
  }

  function fetchPage(p){
    var hit = cacheGet(p);
    if (hit) return Promise.resolve(hit);
    return fetch('https://api.alquran.cloud/v1/page/' + p + '/quran-uthmani')
      .then(function(r){ if (!r.ok) throw new Error('net'); return r.json(); })
      .then(function(j){
        var ay = (j && j.data && j.data.ayahs) || [];
        if (!ay.length) throw new Error('empty');
        var slim = ay.map(function(a){
          return { t: a.text, n: a.numberInSurah, s: a.surah.number };
        });
        cachePut(p, slim);
        return slim;
      });
  }

  /* ============ الرسم ============ */

  var DIA = /[\u064B-\u0652\u0670\u06D6-\u06ED\u0640\u06DF\u06E0]/;
  var BASM_LETTERS = 'بسماللهالرحمنالرحيم';

  function stripBasmala(t){
    var i = 0, k = 0;
    for (; i < t.length && k < BASM_LETTERS.length; i++){
      var ch = t.charAt(i);
      if (/[\s\uFEFF]/.test(ch)) continue;
      if (DIA.test(ch)) continue;
      if (ch === '\u0671' || ch === '\u0623' || ch === '\u0625') ch = '\u0627';
      if (ch === BASM_LETTERS.charAt(k)) k++;
      else return t;
    }
    if (k < BASM_LETTERS.length) return t;
    return t.slice(i).replace(/^[\s\u064B-\u0652\u0670]+/, '').trim();
  }

  function cleanAyah(a){
    var t = String(a.t || '').replace(/^\uFEFF/, '');
    if (a.n === 1 && a.s !== 1 && a.s !== 9) t = stripBasmala(t);
    return t;
  }

  function surahHeadHTML(si){
    return '<div class="qr-surah" id="qrS' + (si + 1) + '" data-si="' + si + '"><span>سورة ' + esc(SURAH_NAMES[si]) + '</span>' +
           '<i>' + esc(SURAH_PLACE[si]) + ' · ' + SURAH_AYAS[si] + ' آية</i></div>';
  }

  function pageHTML(p, ayahs){
    var html = '', lastSurah = -1, open = false;
    ayahs.forEach(function(a){
      if (a.s !== lastSurah){
        if (open) html += '</div>';
        lastSurah = a.s;
        if (a.n === 1){
          html += surahHeadHTML(a.s - 1);
          if (a.s !== 1 && a.s !== 9) html += '<div class="qr-basmala">﷽</div>';
        }
        html += '<div class="qr-text">'; open = true;
      }
      html += '<span class="qr-aya" data-k="' + a.s + ':' + a.n + '">' + esc(cleanAyah(a)) +
              ' <span class="qr-num">﴿' + arNum(a.n) + '﴾</span></span> ';
    });
    if (open) html += '</div>';
    html += '<div class="qr-pagenum">صفحة ' + arNum(p) + ' من ٦٠٤</div>';
    return html;
  }

  function setHeader(p){
    var si = surahOfPage(p);
    titleEl.textContent = 'سورة ' + SURAH_NAMES[si];
    subEl.textContent = 'الجزء ' + juzOfPage(p) + ' · صفحة ' + p;
    var mark = parseInt(lsGet(LS.mark, '0'), 10);
    markBtn.innerHTML = (mark === p) ? IC.markOn : IC.mark;
    markBtn.classList.toggle('is-on', mark === p);
    prevBtn.disabled = (p <= 1);
    nextBtn.disabled = (p >= MAX_PAGE);
    jumpBtn.textContent = 'صفحة ' + p;
    syncMarkBar(p);
  }

  /* شريط «ارجع لعلامتك» — يظهر بس لما تكون حاطط علامة على صفحة تانية */
  function syncMarkBar(p){
    var bar = document.getElementById('qrMarkBar');
    if (!bar) return;
    var mark = parseInt(lsGet(LS.mark, '0'), 10) || 0;
    if (!mark || mark === p){ bar.hidden = true; return; }
    bar.hidden = false;
    bar.querySelector('#qrMarkGo').innerHTML =
      IC.markOn + '<span>ارجع لعلامتك · صفحة ' + mark + ' (سورة ' + esc(SURAH_NAMES[surahOfPage(mark)]) + ')</span>';
  }

  function show(p, opts){
    opts = opts || {};
    p = clampPage(p);
    cur = p;
    lsSet(LS.last, p);
    setHeader(p);
    try { history.replaceState(null, '', '?page=' + p); } catch(e){}

    var sheet = document.getElementById('qrSheet');
    var my = ++reqId;
    var cached = cacheGet(p);
    if (!cached) sheet.innerHTML = '<div class="qr-load"><i></i><i></i><i></i></div>';

    fetchPage(p).then(function(ayahs){
      if (my !== reqId) return;
      sheet.innerHTML = pageHTML(p, ayahs);
      sheet.classList.remove('qr-anim'); void sheet.offsetWidth; sheet.classList.add('qr-anim');
      bodyEl.scrollTop = 0;
      focusTarget(opts);
      // تحميل مسبق للصفحة اللي بعدها
      if (p < MAX_PAGE) setTimeout(function(){ fetchPage(p + 1).catch(function(){}); }, 400);
    }).catch(function(){
      if (my !== reqId) return;
      sheet.innerHTML = '<div class="qr-err"><b>تعذّر تحميل الصفحة</b>' +
        '<span>اتأكد من الاتصال بالإنترنت وحاول تاني. الصفحات اللي فتحتها قبل كده بتشتغل من غير نت.</span>' +
        '<div><button type="button" class="qr-retry" id="qrRetry">إعادة المحاولة</button></div></div>';
      var r = document.getElementById('qrRetry');
      if (r) r.addEventListener('click', function(){ show(p, opts); });
    });
  }

  /* ينزّل الشاشة على بداية السورة اللي المستخدم اختارها ويعلّمها لثانيتين */
  function focusTarget(opts){
    var el = null;
    if (opts.surah != null) el = document.getElementById('qrS' + (opts.surah + 1));
    if (!el && opts.mark) el = document.querySelector('.qr-aya.is-mark');
    if (!el) return;
    setTimeout(function(){
      var top = el.offsetTop - 12;
      try { bodyEl.scrollTo({ top: Math.max(0, top), behavior: 'smooth' }); }
      catch(e){ bodyEl.scrollTop = Math.max(0, top); }
      el.classList.add('is-target');
      setTimeout(function(){ el.classList.remove('is-target'); }, 2400);
    }, 60);
  }

  function toast(msg){
    var t = document.getElementById('qrToast');
    if (!t){ t = document.createElement('div'); t.id = 'qrToast'; t.className = 'qr-toast'; document.body.appendChild(t); }
    t.textContent = msg;
    requestAnimationFrame(function(){ t.classList.add('is-on'); });
    clearTimeout(t._h);
    t._h = setTimeout(function(){ t.classList.remove('is-on'); }, 1800);
  }

  /* ============ شيت الفهرس ============ */
  function openIndex(){
    var ov = document.createElement('div');
    ov.className = 'qr-ov' + (root.classList.contains('is-paper') ? ' is-paper' : '');
    ov.innerHTML =
      '<div class="qr-sh" role="dialog" aria-label="فهرس المصحف">' +
        '<div class="qr-sh-bar"></div>' +
        '<div class="qr-tabs">' +
          '<button type="button" class="qr-tab is-on" data-t="surah">السور</button>' +
          '<button type="button" class="qr-tab" data-t="juz">الأجزاء</button>' +
          '<button type="button" class="qr-tab" data-t="go">انتقال</button>' +
        '</div>' +
        '<div class="qr-search" id="qrSearchWrap">' + IC.search +
          '<input type="search" id="qrSearch" placeholder="دوّر على اسم السورة…">' +
        '</div>' +
        '<div class="qr-sh-body" id="qrShBody"></div>' +
      '</div>';
    document.body.appendChild(ov);
    requestAnimationFrame(function(){ ov.classList.add('is-open'); });

    function close(){
      ov.classList.remove('is-open');
      setTimeout(function(){ if (ov.parentNode) ov.remove(); }, 260);
    }
    ov.addEventListener('click', function(e){ if (e.target === ov) close(); });

    var body = ov.querySelector('#qrShBody');
    var searchWrap = ov.querySelector('#qrSearchWrap');
    var tab = 'surah';

    function renderSurahs(q){
      q = (q || '').trim();
      var html = '';
      var mark = parseInt(lsGet(LS.mark, '0'), 10);
      if (mark && !q){
        html += '<button type="button" class="qr-item" data-p="' + mark + '" data-mark="1">' +
                '<span class="qr-item-n">' + IC.markOn + '</span>' +
                '<span class="qr-item-b"><b>علامتك المحفوظة</b><small>سورة ' + esc(SURAH_NAMES[surahOfPage(mark)]) + '</small></span>' +
                '<span class="qr-item-p">صفحة ' + mark + '</span></button>';
      }
      SURAH_NAMES.forEach(function(n, i){
        if (q && n.indexOf(q) === -1) return;
        var p = SURAH_PAGES[i];
        html += '<button type="button" class="qr-item' + (surahOfPage(cur) === i ? ' is-cur' : '') + '" data-p="' + p + '" data-s="' + i + '">' +
                '<span class="qr-item-n">' + arNum(i + 1) + '</span>' +
                '<span class="qr-item-b"><b>سورة ' + esc(n) + '</b><small>' + esc(SURAH_PLACE[i]) + ' · ' + SURAH_AYAS[i] + ' آية</small></span>' +
                '<span class="qr-item-p">صفحة ' + p + '</span></button>';
      });
      body.innerHTML = html || '<div class="qr-err"><b>مفيش نتائج</b></div>';
    }

    function renderJuz(){
      var html = '';
      JUZ_PAGES.forEach(function(p, i){
        html += '<button type="button" class="qr-item' + (juzOfPage(cur) === i + 1 ? ' is-cur' : '') + '" data-p="' + p + '">' +
                '<span class="qr-item-n">' + arNum(i + 1) + '</span>' +
                '<span class="qr-item-b"><b>الجزء ' + arNum(i + 1) + '</b><small>يبدأ من سورة ' + esc(SURAH_NAMES[surahOfPage(p)]) + '</small></span>' +
                '<span class="qr-item-p">صفحة ' + p + '</span></button>';
      });
      body.innerHTML = html;
    }

    function renderGo(){
      body.innerHTML =
        '<div class="qr-go"><input type="number" min="1" max="604" id="qrGoIn" placeholder="رقم الصفحة (1 - 604)" value="' + cur + '">' +
        '<button type="button" id="qrGoBtn">افتح</button></div>' +
        '<button type="button" class="qr-item" data-p="1"><span class="qr-item-n">١</span>' +
        '<span class="qr-item-b"><b>ابدأ من أول المصحف</b><small>سورة الفاتحة</small></span>' +
        '<span class="qr-item-p">صفحة 1</span></button>';
      var go = body.querySelector('#qrGoBtn');
      var inp = body.querySelector('#qrGoIn');
      go.addEventListener('click', function(){ show(inp.value); close(); });
      inp.addEventListener('keydown', function(e){ if (e.key === 'Enter'){ show(inp.value); close(); } });
    }

    ov.querySelectorAll('.qr-tab').forEach(function(b){
      b.addEventListener('click', function(){
        ov.querySelectorAll('.qr-tab').forEach(function(x){ x.classList.remove('is-on'); });
        b.classList.add('is-on');
        tab = b.getAttribute('data-t');
        searchWrap.style.display = (tab === 'surah') ? '' : 'none';
        if (tab === 'surah') renderSurahs(ov.querySelector('#qrSearch').value);
        else if (tab === 'juz') renderJuz();
        else renderGo();
      });
    });

    ov.querySelector('#qrSearch').addEventListener('input', function(){
      if (tab === 'surah') renderSurahs(this.value);
    });

    body.addEventListener('click', function(e){
      var b = e.target.closest && e.target.closest('.qr-item');
      if (!b || !b.getAttribute('data-p')) return;
      var si = b.getAttribute('data-s');
      var isMark = b.getAttribute('data-mark') === '1';
      show(b.getAttribute('data-p'), si != null ? { surah: parseInt(si, 10) } : (isMark ? { mark: true } : {}));
      close();
    });

    renderSurahs('');
  }

  /* ============ التشغيل ============ */
  function init(){
    root = document.getElementById('musReader');
    if (!root) return;

    var paper = lsGet(LS.paper, '0') === '1';
    var fs = parseInt(lsGet(LS.fs, '23'), 10) || 23;
    root.classList.toggle('is-paper', paper);
    root.style.setProperty('--q-fs', fs + 'px');

    root.innerHTML =
      '<header class="qr-head">' +
        '<button type="button" class="qr-ico" id="qrBack" aria-label="رجوع">' + IC.back + '</button>' +
        '<div class="qr-title"><b id="qrTitle">المصحف</b><small id="qrSub">جارِ التحميل…</small></div>' +
        '<button type="button" class="qr-ico" id="qrMark" aria-label="علامة">' + IC.mark + '</button>' +
        '<button type="button" class="qr-ico" id="qrFont" aria-label="حجم الخط">' + IC.aa + '</button>' +
        '<button type="button" class="qr-ico" id="qrTheme" aria-label="الوضع">' + (paper ? IC.moon : IC.sun) + '</button>' +
      '</header>' +
      '<div class="qr-markbar" id="qrMarkBar" hidden>' +
        '<button type="button" class="qr-markgo" id="qrMarkGo"></button>' +
        '<button type="button" class="qr-markx" id="qrMarkX" aria-label="إخفاء">✕</button>' +
      '</div>' +
      '<main class="qr-body" id="qrBody">' +
        '<section class="qr-sheet"><div class="qr-sheet-in" id="qrSheet">' +
          '<div class="qr-load"><i></i><i></i><i></i></div>' +
        '</div></section>' +
      '</main>' +
      '<footer class="qr-foot">' +
        '<button type="button" class="qr-nav" id="qrPrev">' + IC.prev + ' السابقة</button>' +
        '<button type="button" class="qr-jump" id="qrJump">الفهرس</button>' +
        '<button type="button" class="qr-nav" id="qrNext">التالية ' + IC.next + '</button>' +
      '</footer>';

    bodyEl  = document.getElementById('qrBody');
    titleEl = document.getElementById('qrTitle');
    subEl   = document.getElementById('qrSub');
    markBtn = document.getElementById('qrMark');
    prevBtn = document.getElementById('qrPrev');
    nextBtn = document.getElementById('qrNext');
    jumpBtn = document.getElementById('qrJump');

    document.getElementById('qrBack').addEventListener('click', function(){
      var back = root.getAttribute('data-back') || '/muslim';
      if (window.AppBack) AppBack.go(back); else location.replace(back);
    });

    prevBtn.addEventListener('click', function(){ if (cur > 1) show(cur - 1); });
    nextBtn.addEventListener('click', function(){ if (cur < MAX_PAGE) show(cur + 1); });
    jumpBtn.addEventListener('click', openIndex);

    document.getElementById('qrMarkGo').addEventListener('click', function(){
      var mark = parseInt(lsGet(LS.mark, '0'), 10) || 0;
      if (mark) show(mark, { mark: true });
    });
    document.getElementById('qrMarkX').addEventListener('click', function(){
      document.getElementById('qrMarkBar').hidden = true;
    });

    markBtn.addEventListener('click', function(){
      var mark = parseInt(lsGet(LS.mark, '0'), 10);
      if (mark === cur){ lsSet(LS.mark, '0'); toast('تم مسح العلامة'); }
      else { lsSet(LS.mark, cur); toast('اتحطّت علامة على صفحة ' + cur); }
      setHeader(cur);
    });

    document.getElementById('qrFont').addEventListener('click', function(){
      var v = parseInt(lsGet(LS.fs, '23'), 10) || 23;
      v = v >= 31 ? 19 : v + 3;
      lsSet(LS.fs, v);
      root.style.setProperty('--q-fs', v + 'px');
      toast('حجم الخط: ' + v);
    });

    document.getElementById('qrTheme').addEventListener('click', function(){
      var on = !root.classList.contains('is-paper');
      root.classList.toggle('is-paper', on);
      lsSet(LS.paper, on ? '1' : '0');
      this.innerHTML = on ? IC.moon : IC.sun;
    });

    /* تقليب بالسحب */
    var sx = 0, sy = 0, t0 = 0;
    bodyEl.addEventListener('touchstart', function(e){
      sx = e.touches[0].clientX; sy = e.touches[0].clientY; t0 = Date.now();
    }, { passive:true });
    bodyEl.addEventListener('touchend', function(e){
      var dx = e.changedTouches[0].clientX - sx;
      var dy = e.changedTouches[0].clientY - sy;
      if (Date.now() - t0 > 700) return;
      if (Math.abs(dx) < 60 || Math.abs(dx) < Math.abs(dy) * 1.6) return;
      if (dx < 0 && cur < MAX_PAGE) show(cur + 1);
      else if (dx > 0 && cur > 1) show(cur - 1);
    }, { passive:true });

    document.addEventListener('keydown', function(e){
      if (e.key === 'ArrowLeft' && cur < MAX_PAGE) show(cur + 1);
      if (e.key === 'ArrowRight' && cur > 1) show(cur - 1);
    });

    /* الصفحة اللي هنفتح عليها */
    var qp = new URLSearchParams(location.search).get('page');
    var start = qp ? clampPage(qp) : clampPage(lsGet(LS.last, '1'));
    show(start);
    if (!qp && start > 1) toast('كمّلنا من آخر صفحة وقفت فيها (' + start + ')');
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
