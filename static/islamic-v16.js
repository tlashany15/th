/* islamic-v16.js — رفيق المسلم (مواقيت الصلاة + العد التنازلي لرمضان
   + مناسبات المسلمين + ورد اليوم من المصحف) — يشتغل بدون إنترنت */
(function () {
  var HOST_ID = 'islamicWidget';
  var host = null;

  /* ============ أدوات رياضية ============ */
  var DEG = Math.PI / 180;
  function dsin(d){ return Math.sin(d * DEG); }
  function dcos(d){ return Math.cos(d * DEG); }
  function dtan(d){ return Math.tan(d * DEG); }
  function darcsin(x){ return Math.asin(x) / DEG; }
  function darccos(x){ return Math.acos(x) / DEG; }
  function darctan2(y, x){ return Math.atan2(y, x) / DEG; }
  function darccot(x){ return Math.atan2(1, x) / DEG; }
  function fixAngle(a){ a = a - 360 * Math.floor(a / 360); return a < 0 ? a + 360 : a; }
  function fixHour(a){ a = a - 24 * Math.floor(a / 24); return a < 0 ? a + 24 : a; }

  function julian(y, m, d){
    if (m <= 2) { y -= 1; m += 12; }
    var A = Math.floor(y / 100);
    var B = 2 - A + Math.floor(A / 4);
    return Math.floor(365.25 * (y + 4716)) + Math.floor(30.6001 * (m + 1)) + d + B - 1524.5;
  }
  function sunPosition(jd){
    var D = jd - 2451545.0;
    var g = fixAngle(357.529 + 0.98560028 * D);
    var q = fixAngle(280.459 + 0.98564736 * D);
    var L = fixAngle(q + 1.915 * dsin(g) + 0.020 * dsin(2 * g));
    var e = 23.439 - 0.00000036 * D;
    var RA = fixHour(darctan2(dcos(e) * dsin(L), dcos(L)) / 15);
    return { decl: darcsin(dsin(e) * dsin(L)), eqt: q / 15 - RA };
  }

  /* ============ حساب المواقيت (الهيئة المصرية العامة للمساحة) ============ */
  function prayerTimes(date, lat, lng, tz){
    var jd = julian(date.getFullYear(), date.getMonth() + 1, date.getDate()) - lng / (15 * 24);
    function midDay(t){ return fixHour(12 - sunPosition(jd + t).eqt); }
    function angleTime(angle, t, ccw){
      var decl = sunPosition(jd + t).decl;
      var x = (-dsin(angle) - dsin(decl) * dsin(lat)) / (dcos(decl) * dcos(lat));
      if (x > 1) x = 1; if (x < -1) x = -1;
      var v = darccos(x) / 15;
      return midDay(t) + (ccw ? -v : v);
    }
    function asr(t){
      var decl = sunPosition(jd + t).decl;
      var angle = -darccot(1 + dtan(Math.abs(lat - decl)));
      return angleTime(angle, t, false);
    }
    var t = {
      fajr:    angleTime(19.5, 5 / 24, true),
      sunrise: angleTime(0.833, 6 / 24, true),
      dhuhr:   midDay(12 / 24) + 1 / 60,
      asr:     asr(13 / 24),
      maghrib: angleTime(0.833, 18 / 24, false),
      isha:    angleTime(17.5, 18 / 24, false)
    };
    var out = {};
    for (var k in t) out[k] = fixHour(t[k] + tz - lng / 15);
    return out;
  }

  function hoursToDate(base, h){
    var d = new Date(base.getFullYear(), base.getMonth(), base.getDate());
    d.setSeconds(Math.round(h * 3600));
    return d;
  }
  function fmtTime(d){
    try {
      return d.toLocaleTimeString('ar-EG', { hour: '2-digit', minute: '2-digit', hour12: true });
    } catch (_) {
      var h = d.getHours(), m = d.getMinutes();
      var s = h >= 12 ? 'م' : 'ص'; h = h % 12 || 12;
      return h + ':' + (m < 10 ? '0' : '') + m + ' ' + s;
    }
  }
  function pad(n){ return (n < 10 ? '0' : '') + n; }

  /* ============ التاريخ الهجري ============ */
  var hijriFmt = null;
  try {
    hijriFmt = new Intl.DateTimeFormat('en-u-ca-islamic-umalqura-nu-latn', {
      day: 'numeric', month: 'numeric', year: 'numeric', timeZone: 'UTC'
    });
  } catch (_) { hijriFmt = null; }

  var HMONTHS = ['محرّم','صفر','ربيع الأول','ربيع الآخر','جمادى الأولى','جمادى الآخرة',
                 'رجب','شعبان','رمضان','شوّال','ذو القعدة','ذو الحجة'];

  function toHijri(date){
    if (!hijriFmt) return null;
    var utc = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate(), 12));
    var parts = hijriFmt.formatToParts(utc);
    var o = {};
    parts.forEach(function (p){ if (p.type !== 'literal') o[p.type] = p.value; });
    var y = parseInt(String(o.year).replace(/\D/g, ''), 10);
    var m = parseInt(o.month, 10);
    var d = parseInt(o.day, 10);
    if (!y || !m || !d) return null;
    return { y: y, m: m, d: d };
  }
  function hijriText(h){
    if (!h) return '';
    return h.d + ' ' + HMONTHS[h.m - 1] + ' ' + h.y + 'هـ';
  }

  var DAY = 86400000;
  function addDays(date, n){
    var d = new Date(date.getFullYear(), date.getMonth(), date.getDate());
    d.setTime(d.getTime() + n * DAY);
    return d;
  }

  /* المناسبات: [شهر هجري, يوم, الاسم, نوع الأيقونة] */
  var EVENTS = [
    [1, 1,  'رأس السنة الهجرية', 'star'],
    [1, 10, 'يوم عاشوراء', 'moon'],
    [3, 12, 'المولد النبوي الشريف', 'star'],
    [7, 27, 'الإسراء والمعراج', 'moon'],
    [8, 15, 'ليلة النصف من شعبان', 'moon'],
    [9, 1,  'أول رمضان', 'moon'],
    [9, 27, 'ليلة القدر (المرجَّحة)', 'star'],
    [10, 1, 'عيد الفطر المبارك', 'gift'],
    [12, 9, 'يوم عرفة', 'star'],
    [12, 10,'عيد الأضحى المبارك', 'gift']
  ];

  /* مسح 400 يوم قدّام لبناء خريطة هجرية */
  function scanCalendar(today){
    var map = [];
    for (var i = 0; i <= 400; i++){
      var d = addDays(today, i);
      var h = toHijri(d);
      if (!h) return null;
      map.push({ i: i, date: d, h: h });
    }
    return map;
  }
  function findNext(map, month, day){
    for (var i = 0; i < map.length; i++){
      if (map[i].h.m === month && map[i].h.d === day) return map[i];
    }
    return null;
  }

  /* ============ ورد اليوم ============ */
  function todayPage(date){
    var n = Math.floor(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()) / DAY);
    return ((n * 13) % 604) + 1;
  }

  /* ============ الأيقونات ============ */
  var IC = {
    mosque: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3c2.4 1.7 3.6 3.3 3.6 5 0 1.2-.7 2-1.6 2.6h-4C9.1 10 8.4 9.2 8.4 8c0-1.7 1.2-3.3 3.6-5z"/><path d="M4 21v-7.2c0-1 .6-1.7 1.6-2M20 21v-7.2c0-1-.6-1.7-1.6-2"/><path d="M6.5 21v-6a5.5 5.5 0 0 1 11 0v6"/><path d="M3 21h18"/></svg>',
    moon:   '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5z"/></svg>',
    star:   '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3.5l2.6 5.4 5.9.8-4.3 4.1 1 5.9-5.2-2.8-5.2 2.8 1-5.9L3.5 9.7l5.9-.8z"/></svg>',
    gift:   '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="8.5" width="18" height="12" rx="2"/><path d="M3 12.5h18M12 8.5v12"/><path d="M12 8.5S10.5 4 8 4a2 2 0 0 0 0 4.5zM12 8.5S13.5 4 16 4a2 2 0 0 1 0 4.5z"/></svg>',
    book:   '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M4 4.5h5.5A2.5 2.5 0 0 1 12 7v13a2 2 0 0 0-2-2H4z"/><path d="M20 4.5h-5.5A2.5 2.5 0 0 0 12 7v13a2 2 0 0 1 2-2h6z"/></svg>',
    ext:    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 4h6v6M20 4l-8.5 8.5"/><path d="M18 14v5a1.5 1.5 0 0 1-1.5 1.5h-11A1.5 1.5 0 0 1 4 19V8a1.5 1.5 0 0 1 1.5-1.5H10"/></svg>'
  };

  /* ============ الرسم ============ */
  var PRAYERS = [
    ['fajr', 'الفجر'], ['sunrise', 'الشروق'], ['dhuhr', 'الظهر'],
    ['asr', 'العصر'], ['maghrib', 'المغرب'], ['isha', 'العشاء']
  ];

  var state = {
    lat: 30.5525, lng: 31.0094, city: 'المنوفية'
  };
  var tickTimer = null;

  function esc(s){ return String(s).replace(/[&<>"]/g, function(c){
    return ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;' })[c]; }); }

  function render(){
    if (!host) return;
    var now = new Date();
    var tz = -now.getTimezoneOffset() / 60;
    var times = prayerTimes(now, state.lat, state.lng, tz);
    var list = PRAYERS.map(function (p){
      return { key: p[0], name: p[1], date: hoursToDate(now, times[p[0]]) };
    });

    /* الصلاة القادمة */
    var next = null;
    for (var i = 0; i < list.length; i++){
      if (list[i].date.getTime() > now.getTime()) { next = list[i]; break; }
    }
    if (!next){
      var tmr = addDays(now, 1);
      var t2 = prayerTimes(tmr, state.lat, state.lng, tz);
      next = { key: 'fajr', name: 'الفجر', date: hoursToDate(tmr, t2.fajr), tomorrow: true };
    }

    var h = toHijri(now);
    var map = scanCalendar(now);

    /* رمضان */
    var ramHtml = '';
    if (map){
      var ram = findNext(map, 9, 1);
      var inRamadan = h && h.m === 9;
      if (inRamadan){
        var pct = Math.round((h.d / 30) * 100);
        ramHtml =
          '<div class="isl-card isl-ram">' +
          '<div class="isl-glow"></div>' +
          '<div class="isl-head"><h3 class="isl-title">' + IC.moon + '<span>رمضان كريم</span></h3>' +
          '<span class="isl-chip">' + esc(hijriText(h)) + '</span></div>' +
          '<div class="isl-ram-num">' + h.d + '</div>' +
          '<div class="isl-ram-sub">اليوم ' + h.d + ' من رمضان — باقي ' + Math.max(0, 30 - h.d) + ' يوم على العيد</div>' +
          '<div class="isl-bar"><i data-w="' + pct + '"></i></div>' +
          '</div>';
      } else if (ram){
        var days = ram.i;
        var pct2 = Math.max(4, Math.round((1 - days / 355) * 100));
        ramHtml =
          '<div class="isl-card isl-ram">' +
          '<div class="isl-glow"></div>' +
          '<div class="isl-head"><h3 class="isl-title">' + IC.moon + '<span>العد التنازلي لرمضان</span></h3>' +
          '<span class="isl-chip">' + esc(hijriText(h)) + '</span></div>' +
          '<div class="isl-ram-num">' + days + '</div>' +
          '<div class="isl-ram-sub">' + (days === 0 ? 'رمضان بدأ — كل سنة وأنت طيب' : 'يوم باقي على رمضان') + '</div>' +
          '<div class="isl-ram-date">أول رمضان ' + (ram.h.y) + 'هـ يوافق ' +
            esc(ram.date.toLocaleDateString('ar-EG', { weekday:'long', day:'numeric', month:'long', year:'numeric' })) + '</div>' +
          '<div class="isl-bar"><i data-w="' + pct2 + '"></i></div>' +
          '</div>';
      }
    }

    /* المناسبات */
    var evHtml = '';
    if (map){
      var evs = [];
      EVENTS.forEach(function (e){
        var hit = findNext(map, e[0], e[1]);
        if (hit) evs.push({ n: e[2], ic: e[3], i: hit.i, date: hit.date, h: hit.h });
      });
      evs.sort(function (a, b){ return a.i - b.i; });
      evs = evs.slice(0, 4);
      evHtml =
        '<div class="isl-card">' +
        '<div class="isl-head"><h3 class="isl-title">' + IC.star + '<span>مناسبات قادمة</span></h3>' +
        '<span class="isl-chip">أقرب ' + evs.length + '</span></div>' +
        '<ul class="isl-list">' +
        evs.map(function (e, idx){
          return '<li class="isl-ev' + (e.i === 0 ? ' is-today' : '') + '" style="--i:' + idx + '">' +
            '<span class="isl-ev-ic">' + (IC[e.ic] || IC.star) + '</span>' +
            '<span class="isl-ev-b"><span class="isl-ev-n">' + esc(e.n) + '</span>' +
            '<span class="isl-ev-d">' + esc(e.date.toLocaleDateString('ar-EG', { weekday:'long', day:'numeric', month:'long' })) +
            ' · ' + esc(hijriText(e.h)) + '</span></span>' +
            '<span class="isl-ev-c">' + (e.i === 0 ? 'النهاردة' : 'بعد ' + e.i + ' يوم') + '</span>' +
            '</li>';
        }).join('') +
        '</ul></div>';
    }

    /* ورد اليوم */
    var page = todayPage(now);
    var juz = Math.min(30, Math.floor((page - 1) / 20.14) + 1);
    var quranHtml =
      '<div class="isl-card">' +
      '<div class="isl-head"><h3 class="isl-title">' + IC.book + '<span>ورد اليوم من المصحف</span></h3>' +
      '<span class="isl-chip">الجزء ' + juz + '</span></div>' +
      '<div class="isl-quran">' +
      '<div class="isl-page"><div><b>' + page + '</b><span>صفحة</span></div></div>' +
      '<div class="isl-q-b">' +
      '<div class="isl-q-t">اقرأ صفحة ' + page + ' النهاردة</div>' +
      '<div class="isl-q-s">صفحة واحدة كل يوم تخلّيك تختم المصحف بإذن الله — والقراءة راحة للقلب.</div>' +
      '</div></div>' +
      '<button type="button" class="isl-q-link" id="islRead" data-page="' + page + '">' + IC.book + ' اقرأ الصفحة</button>' +
      '</div>';

    /* مواقيت الصلاة */
    var prayersHtml =
      '<div class="isl-card">' +
      '<div class="isl-glow"></div>' +
      '<div class="isl-head"><h3 class="isl-title">' + IC.mosque + '<span>مواقيت الصلاة</span></h3>' +
      '<span class="isl-chip">' + esc(now.toLocaleDateString('ar-EG', { weekday:'long' })) + '</span></div>' +
      '<div class="isl-next">' +
      '<div><div class="isl-next-lbl">الصلاة القادمة</div>' +
      '<div class="isl-next-name">' + esc(next.name) + (next.tomorrow ? ' (بكرة)' : '') + '</div>' +
      '<div class="isl-next-time">' + esc(fmtTime(next.date)) + '</div></div>' +
      '<div class="isl-next-cd" id="islCd" data-ts="' + next.date.getTime() + '">--:--:--<small>باقي على الأذان</small></div>' +
      '</div>' +
      '<div class="isl-prayers">' +
      list.map(function (p){
        var cls = p.date.getTime() < now.getTime() ? ' is-past' : '';
        if (p.key === next.key && !next.tomorrow) cls = ' is-now';
        return '<div class="isl-p' + cls + '"><div class="isl-p-n">' + p.name + '</div>' +
               '<div class="isl-p-t">' + esc(fmtTime(p.date)) + '</div></div>';
      }).join('') +
      '</div>' +
      '<div class="isl-loc"><span>المواقيت حسب محافظة ' + esc(state.city) + '</span></div>' +
      '</div>';

    host.className = 'isl-wrap v2-fade';
    host.innerHTML = prayersHtml + ramHtml + evHtml + quranHtml;

    /* شرائط التقدّم */
    requestAnimationFrame(function (){
      host.querySelectorAll('.isl-bar i').forEach(function (b){
        b.style.width = (b.getAttribute('data-w') || 0) + '%';
      });
    });

    var readBtn = document.getElementById('islRead');
    if (readBtn) readBtn.addEventListener('click', function(){ openMushaf(page); });

    startTick();
  }

  function startTick(){
    if (tickTimer) clearInterval(tickTimer);
    tickTimer = setInterval(function (){
      var el = document.getElementById('islCd');
      if (!el) { clearInterval(tickTimer); return; }
      var diff = parseInt(el.getAttribute('data-ts'), 10) - Date.now();
      if (diff <= 0) { render(); return; }
      var s = Math.floor(diff / 1000);
      var hh = Math.floor(s / 3600), mm = Math.floor((s % 3600) / 60), ss = s % 60;
      el.firstChild.nodeValue = pad(hh) + ':' + pad(mm) + ':' + pad(ss);
    }, 1000);
  }


  /* ============ قارئ المصحف داخل التطبيق ============ */
  var SURAHS = ['الفاتحة','البقرة','آل عمران','النساء','المائدة','الأنعام','الأعراف','الأنفال','التوبة','يونس','هود','يوسف','الرعد','إبراهيم','الحجر','النحل','الإسراء','الكهف','مريم','طه','الأنبياء','الحج','المؤمنون','النور','الفرقان','الشعراء','النمل','القصص','العنكبوت','الروم','لقمان','السجدة','الأحزاب','سبأ','فاطر','يس','الصافات','ص','الزمر','غافر','فصلت','الشورى','الزخرف','الدخان','الجاثية','الأحقاف','محمد','الفتح','الحجرات','ق','الذاريات','الطور','النجم','القمر','الرحمن','الواقعة','الحديد','المجادلة','الحشر','الممتحنة','الصف','الجمعة','المنافقون','التغابن','الطلاق','التحريم','الملك','القلم','الحاقة','المعارج','نوح','الجن','المزمل','المدثر','القيامة','الإنسان','المرسلات','النبأ','النازعات','عبس','التكوير','الانفطار','المطففين','الانشقاق','البروج','الطارق','الأعلى','الغاشية','الفجر','البلد','الشمس','الليل','الضحى','الشرح','التين','العلق','القدر','البينة','الزلزلة','العاديات','القارعة','التكاثر','العصر','الهمزة','الفيل','قريش','الماعون','الكوثر','الكافرون','النصر','المسد','الإخلاص','الفلق','الناس'];

  var mushafCache = {};

  function openMushaf(page){
    var ov = document.getElementById('islMushaf');
    if (ov) ov.remove();
    ov = document.createElement('div');
    ov.id = 'islMushaf';
    ov.className = 'isl-ov';
    ov.innerHTML =
      '<div class="isl-sheet" role="dialog" aria-label="ورد اليوم">' +
        '<div class="isl-sheet-bar"></div>' +
        '<div class="isl-sheet-head">' +
          '<div class="isl-sheet-t">' + IC.book + '<span>صفحة <b class="isl-sheet-p">' + page + '</b></span></div>' +
          '<button type="button" class="isl-sheet-x" aria-label="إغلاق">' +
            '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18"/></svg>' +
          '</button>' +
        '</div>' +
        '<div class="isl-sheet-body"><div class="isl-load"><i></i><i></i><i></i></div></div>' +
        '<div class="isl-sheet-foot">' +
          '<button type="button" class="isl-nav" data-d="-1">الصفحة السابقة</button>' +
          '<button type="button" class="isl-nav isl-nav-p" data-d="1">الصفحة التالية</button>' +
        '</div>' +
      '</div>';
    document.body.appendChild(ov);
    document.body.classList.add('isl-lock');
    requestAnimationFrame(function(){ ov.classList.add('is-open'); });

    function close(){
      ov.classList.remove('is-open');
      document.body.classList.remove('isl-lock');
      setTimeout(function(){ if (ov.parentNode) ov.remove(); }, 260);
    }
    ov.addEventListener('click', function(e){ if (e.target === ov) close(); });
    ov.querySelector('.isl-sheet-x').addEventListener('click', close);

    var cur = page;
    ov.querySelectorAll('.isl-nav').forEach(function(b){
      b.addEventListener('click', function(){
        var n = cur + parseInt(b.getAttribute('data-d'), 10);
        if (n < 1) n = 1; if (n > 604) n = 604;
        if (n === cur) return;
        cur = n;
        ov.querySelector('.isl-sheet-p').textContent = n;
        loadPage(n);
      });
    });

    function loadPage(n){
      var body = ov.querySelector('.isl-sheet-body');
      body.scrollTop = 0;
      if (mushafCache[n]) { paint(body, mushafCache[n], n); return; }
      body.innerHTML = '<div class="isl-load"><i></i><i></i><i></i></div>';
      fetch('https://api.quran.com/api/v4/verses/by_page/' + n +
            '?fields=text_uthmani&per_page=all&words=false')
        .then(function(r){ if (!r.ok) throw new Error('net'); return r.json(); })
        .then(function(j){
          var vs = (j && j.verses) || [];
          if (!vs.length) throw new Error('empty');
          mushafCache[n] = vs;
          paint(body, vs, n);
        })
        .catch(function(){
          body.innerHTML = '<div class="isl-err"><p>تعذّر تحميل الصفحة — اتأكد من الاتصال بالإنترنت.</p>' +
            '<button type="button" class="isl-retry">إعادة المحاولة</button></div>';
          var rb = body.querySelector('.isl-retry');
          if (rb) rb.addEventListener('click', function(){ loadPage(n); });
        });
    }

    function paint(body, vs, n){
      var out = '';
      var lastSura = null;
      var buf = [];

      function flush(){
        if (!buf.length) return;
        out += '<p class="isl-ayat">' + buf.join(' ') + '</p>';
        buf = [];
      }

      vs.forEach(function(v){
        var parts = String(v.verse_key).split(':');
        var sura = parseInt(parts[0], 10);
        var num = parts[1];
        if (sura !== lastSura){
          flush();
          if (num === '1' || lastSura !== null){
            out += '<div class="isl-sura">' +
                     '<span class="isl-sura-o"></span>' +
                     '<span class="isl-sura-n">سورة ' + esc(SURAHS[sura - 1] || '') + '</span>' +
                     '<span class="isl-sura-o"></span>' +
                   '</div>';
          }
          if (num === '1' && sura !== 1 && sura !== 9){
            out += '<div class="isl-bism">بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ</div>';
          }
          lastSura = sura;
        }
        buf.push('<span class="isl-aya">' + esc(cleanUthmani(v.text_uthmani)) +
                 '<span class="isl-aya-n">' + toArabicNum(num) + '</span></span>');
      });
      flush();

      body.innerHTML = '<div class="isl-mushaf v2-fade">' + out +
        '<div class="isl-mushaf-f">صفحة ' + n + ' من 604</div></div>';
    }

    loadPage(cur);
  }

  /* تنظيف نص المصحف من الرموز اللي مش موجودة في الخطوط (بتظهر علامات استفهام) */
  function cleanUthmani(t){
    return String(t)
      .replace(/[\u06DD\uFDFD]/g, '')
      .replace(/[\u2000-\u200A\u202F\u205F\u3000]/g, ' ')
      .replace(/\s{2,}/g, ' ')
      .trim();
  }

  function toArabicNum(s){
    var ar = '٠١٢٣٤٥٦٧٨٩';
    return String(s).replace(/\d/g, function(d){ return ar[+d]; });
  }

  function init(){
    host = document.getElementById(HOST_ID);
    if (!host) return;
    render();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
