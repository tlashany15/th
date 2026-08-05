/* ==========================================================================
   recite-v20.js — قسم «القراءة بالصوت»
   • اختيار القارئ + السورة + طريقة التشغيل (مرة / تكرار / المصحف كامل)
   • الصوت يكمّل والشاشة مقفولة (MediaSession + عنصر صوت واحد ثابت)
   • بيحفظ مكانك: القارئ + السورة + الثانية اللي وقفت عندها
   ========================================================================== */
(function () {
  'use strict';

  var RECITERS = [
    { id: 'basit',   name: 'عبد الباسط عبد الصمد', base: 'https://server7.mp3quran.net/basit/' },
    { id: 'afs',     name: 'مشاري العفاسي',        base: 'https://server8.mp3quran.net/afs/' },
    { id: 'minsh',   name: 'محمد صديق المنشاوي',   base: 'https://server10.mp3quran.net/minsh/' },
    { id: 'husr',    name: 'محمود خليل الحصري',    base: 'https://server13.mp3quran.net/husr/' },
    { id: 'maher',   name: 'ماهر المعيقلي',        base: 'https://server12.mp3quran.net/maher/' },
    { id: 'yasser',  name: 'ياسر الدوسري',         base: 'https://server11.mp3quran.net/yasser/' },
    { id: 'sds',     name: 'عبد الرحمن السديس',    base: 'https://server11.mp3quran.net/sds/' },
    { id: 's_gmd',   name: 'سعد الغامدي',          base: 'https://server7.mp3quran.net/s_gmd/' },
    { id: 'balilah', name: 'بندر بليلة',           base: 'https://server6.mp3quran.net/balilah/' },
    { id: 'ayyub',   name: 'محمد أيوب',            base: 'https://server8.mp3quran.net/ayyub/' }
  ];

  var NAMES = ["الفاتحة","البقرة","آل عمران","النساء","المائدة","الأنعام","الأعراف","الأنفال","التوبة","يونس","هود","يوسف","الرعد","إبراهيم","الحجر","النحل","الإسراء","الكهف","مريم","طه","الأنبياء","الحج","المؤمنون","النور","الفرقان","الشعراء","النمل","القصص","العنكبوت","الروم","لقمان","السجدة","الأحزاب","سبأ","فاطر","يس","الصافات","ص","الزمر","غافر","فصلت","الشورى","الزخرف","الدخان","الجاثية","الأحقاف","محمد","الفتح","الحجرات","ق","الذاريات","الطور","النجم","القمر","الرحمن","الواقعة","الحديد","المجادلة","الحشر","الممتحنة","الصف","الجمعة","المنافقون","التغابن","الطلاق","التحريم","الملك","القلم","الحاقة","المعارج","نوح","الجن","المزمل","المدثر","القيامة","الإنسان","المرسلات","النبأ","النازعات","عبس","التكوير","الانفطار","المطففين","الانشقاق","البروج","الطارق","الأعلى","الغاشية","الفجر","البلد","الشمس","الليل","الضحى","الشرح","التين","العلق","القدر","البينة","الزلزلة","العاديات","القارعة","التكاثر","العصر","الهمزة","الفيل","قريش","الماعون","الكوثر","الكافرون","النصر","المسد","الإخلاص","الفلق","الناس"];
  var AYAS = [7,286,200,176,120,165,206,75,129,109,123,111,43,52,99,128,111,110,98,135,112,78,118,64,77,227,93,88,69,60,34,30,73,54,45,83,182,88,75,85,54,53,89,59,37,35,38,29,18,45,60,49,62,55,78,96,29,22,24,13,14,11,11,18,12,12,30,52,52,44,28,28,20,56,40,31,50,40,46,42,29,19,36,25,22,17,19,26,30,20,15,21,11,8,8,19,5,8,8,11,11,8,3,9,5,4,7,3,6,3,5,4,5,6];
  var PLACE = ["مكية","مدنية","مدنية","مدنية","مدنية","مكية","مكية","مدنية","مدنية","مكية","مكية","مكية","مدنية","مكية","مكية","مكية","مكية","مكية","مكية","مكية","مكية","مدنية","مكية","مدنية","مكية","مكية","مكية","مكية","مكية","مكية","مكية","مكية","مدنية","مكية","مكية","مكية","مكية","مكية","مكية","مكية","مكية","مكية","مكية","مكية","مكية","مكية","مدنية","مدنية","مدنية","مكية","مكية","مكية","مكية","مكية","مدنية","مكية","مدنية","مدنية","مدنية","مدنية","مدنية","مدنية","مدنية","مدنية","مدنية","مدنية","مكية","مكية","مكية","مكية","مكية","مكية","مكية","مكية","مكية","مدنية","مكية","مكية","مكية","مكية","مكية","مكية","مكية","مكية","مكية","مكية","مكية","مكية","مكية","مكية","مكية","مكية","مكية","مكية","مكية","مكية","مكية","مدنية","مدنية","مكية","مكية","مكية","مكية","مكية","مكية","مكية","مكية","مكية","مكية","مدنية","مكية","مكية","مكية","مكية"];

  var LS = { rec: 'rc.reciter', mode: 'rc.mode', surah: 'rc.surah', pos: 'rc.pos' };

  function lsGet(k, d) { try { var v = localStorage.getItem(k); return v === null ? d : v; } catch (e) { return d; } }
  function lsSet(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }
  function pad3(n) { return ('00' + n).slice(-3); }
  function fmt(t) {
    t = Math.max(0, Math.floor(t || 0));
    var m = Math.floor(t / 60), s = t % 60;
    return m + ':' + (s < 10 ? '0' : '') + s;
  }

  var root, audio, listEl, playerEl, seekEl, seeking = false;
  var mode = lsGet(LS.mode, 'all');
  var recId = lsGet(LS.rec, RECITERS[0].id);
  var cur = 0; // رقم السورة (1..114) — 0 يعني مفيش

  function reciter() {
    for (var i = 0; i < RECITERS.length; i++) if (RECITERS[i].id === recId) return RECITERS[i];
    return RECITERS[0];
  }
  function srcOf(s) { return reciter().base + pad3(s) + '.mp3'; }

  function icPlay() { return '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M8 5.5v13l11-6.5z"/></svg>'; }
  function icPause() { return '<svg viewBox="0 0 24 24" fill="currentColor"><rect x="7" y="5.5" width="3.6" height="13" rx="1.2"/><rect x="13.4" y="5.5" width="3.6" height="13" rx="1.2"/></svg>'; }
  function icWave() { return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M5 10v4M9 7v10M13 9v6M17 11v2M21 10v4"/></svg>'; }

  /* ================= القرّاء ================= */
  function paintRecs() {
    var wrap = document.getElementById('rcRecs');
    wrap.innerHTML = RECITERS.slice(0, 5).map(function (r) {
      return '<button type="button" class="rc-rec' + (r.id === recId ? ' is-on' : '') + '" data-r="' + r.id + '">' + esc(r.name) + '</button>';
    }).join('');
    var r = reciter();
    if (RECITERS.slice(0, 5).indexOf(r) === -1) {
      wrap.insertAdjacentHTML('afterbegin', '<button type="button" class="rc-rec is-on" data-r="' + r.id + '">' + esc(r.name) + '</button>');
    }
  }

  function openAllRecs() {
    var ov = document.createElement('div');
    ov.className = 'rc-ov';
    ov.innerHTML =
      '<div class="rc-sh" role="dialog" aria-label="كل القرّاء">' +
        '<div class="rc-sh-bar"></div><div class="rc-sh-h">اختار القارئ</div>' +
        '<div class="rc-sh-b">' + RECITERS.map(function (r) {
          return '<button type="button" class="rc-item' + (r.id === recId ? ' is-on' : '') + '" data-r="' + r.id + '">' +
            '<span class="rc-item-n">' + icWave() + '</span>' +
            '<span class="rc-item-b"><b>' + esc(r.name) + '</b><small>تلاوة مرتّلة — المصحف كامل</small></span>' +
            (r.id === recId ? '<span class="rc-item-p">✓</span>' : '') + '</button>';
        }).join('') + '</div>' +
      '</div>';
    document.body.appendChild(ov);
    requestAnimationFrame(function () { ov.classList.add('is-open'); });
    function close() { ov.classList.remove('is-open'); setTimeout(function () { ov.parentNode && ov.remove(); }, 260); }
    ov.addEventListener('click', function (e) {
      if (e.target === ov) return close();
      var b = e.target.closest('[data-r]');
      if (!b) return;
      setReciter(b.getAttribute('data-r'));
      close();
    });
  }

  function setReciter(id) {
    recId = id; lsSet(LS.rec, id);
    paintRecs();
    if (cur) {
      var at = audio.currentTime || 0;
      var was = !audio.paused;
      audio.src = srcOf(cur);
      audio.currentTime = 0;
      try { audio.currentTime = at; } catch (e) {}
      if (was) audio.play().catch(function () {});
      paintNow();
    }
  }

  /* ================= السور ================= */
  function paintList(q) {
    q = (q || '').trim();
    var html = '';
    for (var i = 0; i < NAMES.length; i++) {
      if (q && NAMES[i].indexOf(q) === -1) continue;
      var s = i + 1;
      html += '<button type="button" class="rc-item' + (s === cur ? ' is-on' : '') + '" data-s="' + s + '">' +
        '<span class="rc-item-n">' + s + '</span>' +
        '<span class="rc-item-b"><b>سورة ' + esc(NAMES[i]) + '</b><small>' + esc(PLACE[i]) + ' · ' + AYAS[i] + ' آية</small></span>' +
        '<span class="rc-item-p">' + (s === cur ? icWave() : icPlay()) + '</span></button>';
    }
    listEl.innerHTML = html || '<div class="rc-empty">مفيش نتائج بالاسم ده</div>';
  }

  /* ================= التشغيل ================= */
  function play(s, at) {
    s = Math.min(114, Math.max(1, parseInt(s, 10) || 1));
    var same = (s === cur);
    cur = s;
    lsSet(LS.surah, s);
    playerEl.hidden = false;
    if (!same || !audio.src) {
      audio.src = srcOf(s);
      audio.load();
    }
    if (at) { try { audio.currentTime = at; } catch (e) {} }
    audio.play().catch(function () {});
    paintNow();
    paintList(document.getElementById('rcSearch').value);
  }

  function paintNow() {
    if (!cur) return;
    document.getElementById('rcNowT').textContent = 'سورة ' + NAMES[cur - 1];
    document.getElementById('rcNowS').textContent = reciter().name;
    document.getElementById('rcHeadSub').textContent = 'سورة ' + NAMES[cur - 1] + ' · ' + reciter().name;
    document.getElementById('rcModeTxt').textContent =
      mode === 'one' ? 'السورة مرة واحدة' : (mode === 'repeat' ? 'تكرار السورة' : 'المصحف كامل بالتتابع');
    setPlayIcon();
    media();
  }

  function setPlayIcon() {
    var b = document.getElementById('rcPlay');
    if (b) b.innerHTML = (audio && !audio.paused) ? icPause() : icPlay();
  }

  function ended() {
    if (mode === 'repeat') { play(cur, 0); return; }
    if (mode === 'all' && cur < 114) { play(cur + 1, 0); return; }
    setPlayIcon();
  }

  /* ================= الشاشة المقفولة (MediaSession) ================= */
  function media() {
    if (!('mediaSession' in navigator)) return;
    try {
      navigator.mediaSession.metadata = new window.MediaMetadata({
        title: 'سورة ' + NAMES[cur - 1],
        artist: reciter().name,
        album: 'القرآن الكريم — فريق التحصين'
      });
      navigator.mediaSession.setActionHandler('play', function () { audio.play().catch(function () {}); });
      navigator.mediaSession.setActionHandler('pause', function () { audio.pause(); });
      navigator.mediaSession.setActionHandler('previoustrack', function () { if (cur > 1) play(cur - 1, 0); });
      navigator.mediaSession.setActionHandler('nexttrack', function () { if (cur < 114) play(cur + 1, 0); });
      navigator.mediaSession.setActionHandler('seekbackward', function () { audio.currentTime = Math.max(0, audio.currentTime - 15); });
      navigator.mediaSession.setActionHandler('seekforward', function () { audio.currentTime = audio.currentTime + 15; });
      navigator.mediaSession.setActionHandler('stop', function () { audio.pause(); });
    } catch (e) {}
  }
  function mediaState() {
    if (!('mediaSession' in navigator)) return;
    try {
      navigator.mediaSession.playbackState = audio.paused ? 'paused' : 'playing';
      if (audio.duration && isFinite(audio.duration) && navigator.mediaSession.setPositionState) {
        navigator.mediaSession.setPositionState({
          duration: audio.duration,
          position: Math.min(audio.currentTime, audio.duration),
          playbackRate: audio.playbackRate || 1
        });
      }
    } catch (e) {}
  }

  /* ================= التشغيل الأولي ================= */
  function boot() {
    root = document.getElementById('rcRoot');
    if (!root) return;
    audio = document.getElementById('rcAudio');
    listEl = document.getElementById('rcList');
    playerEl = document.getElementById('rcPlayer');
    seekEl = document.getElementById('rcSeek');

    paintRecs();
    paintList('');
    document.getElementById('rcOpts').querySelectorAll('.rc-opt').forEach(function (b) {
      b.classList.toggle('is-on', b.getAttribute('data-mode') === mode);
    });

    document.getElementById('rcBack').addEventListener('click', function () {
      var back = root.getAttribute('data-back') || '/muslim';
      if (history.length > 1) history.back(); else location.href = back;
    });

    document.getElementById('rcRecs').addEventListener('click', function (e) {
      var b = e.target.closest('[data-r]');
      if (b) setReciter(b.getAttribute('data-r'));
    });
    document.getElementById('rcAllRec').addEventListener('click', openAllRecs);

    document.getElementById('rcOpts').addEventListener('click', function (e) {
      var b = e.target.closest('[data-mode]');
      if (!b) return;
      mode = b.getAttribute('data-mode');
      lsSet(LS.mode, mode);
      this.querySelectorAll('.rc-opt').forEach(function (x) { x.classList.toggle('is-on', x === b); });
      audio.loop = false;
      if (cur) paintNow();
    });

    listEl.addEventListener('click', function (e) {
      var b = e.target.closest('[data-s]');
      if (!b) return;
      play(b.getAttribute('data-s'), 0);
    });

    document.getElementById('rcSearch').addEventListener('input', function () { paintList(this.value); });

    document.getElementById('rcPlayAll').addEventListener('click', function () {
      mode = 'all'; lsSet(LS.mode, mode);
      document.getElementById('rcOpts').querySelectorAll('.rc-opt').forEach(function (x) {
        x.classList.toggle('is-on', x.getAttribute('data-mode') === 'all');
      });
      play(1, 0);
    });

    document.getElementById('rcResume').addEventListener('click', function () {
      var s = parseInt(lsGet(LS.surah, '1'), 10) || 1;
      var at = parseFloat(lsGet(LS.pos, '0')) || 0;
      play(s, at);
    });

    document.getElementById('rcPlay').addEventListener('click', function () {
      if (!cur) { play(parseInt(lsGet(LS.surah, '1'), 10) || 1, parseFloat(lsGet(LS.pos, '0')) || 0); return; }
      if (audio.paused) audio.play().catch(function () {}); else audio.pause();
    });
    document.getElementById('rcPrev').addEventListener('click', function () { if (cur > 1) play(cur - 1, 0); });
    document.getElementById('rcNext').addEventListener('click', function () { if (cur < 114) play(cur + 1, 0); });
    document.getElementById('rcBack15').addEventListener('click', function () { audio.currentTime = Math.max(0, audio.currentTime - 15); });
    document.getElementById('rcFwd15').addEventListener('click', function () { audio.currentTime = audio.currentTime + 15; });
    document.getElementById('rcStop').addEventListener('click', function () {
      audio.pause(); playerEl.hidden = true;
    });

    seekEl.addEventListener('input', function () { seeking = true; });
    seekEl.addEventListener('change', function () {
      seeking = false;
      if (audio.duration && isFinite(audio.duration)) audio.currentTime = (this.value / 1000) * audio.duration;
    });

    audio.addEventListener('play', function () { setPlayIcon(); mediaState(); });
    audio.addEventListener('pause', function () { setPlayIcon(); mediaState(); });
    audio.addEventListener('ended', ended);
    audio.addEventListener('loadedmetadata', function () {
      document.getElementById('rcDur').textContent = fmt(audio.duration);
      mediaState();
    });
    audio.addEventListener('timeupdate', function () {
      document.getElementById('rcCur').textContent = fmt(audio.currentTime);
      if (!seeking && audio.duration && isFinite(audio.duration)) {
        seekEl.value = Math.round((audio.currentTime / audio.duration) * 1000);
      }
      if (cur) lsSet(LS.pos, Math.floor(audio.currentTime));
      if (Math.floor(audio.currentTime) % 5 === 0) mediaState();
    });
    audio.addEventListener('error', function () {
      if (!cur) return;
      var t = document.getElementById('rcNowS');
      if (t) t.textContent = 'التلاوة محتاجة إنترنت — حاول تاني';
    });

    /* لو الصفحة اتقفلت أو رجعت — الصوت يفضل شغال ومنقفلوش */
    document.addEventListener('visibilitychange', function () { mediaState(); });

    /* افتح على آخر سورة كنت واقف فيها (بدون تشغيل تلقائي) */
    var qs = new URLSearchParams(location.search);
    var qSurah = parseInt(qs.get('surah') || '0', 10);
    var lastS = qSurah || parseInt(lsGet(LS.surah, '0'), 10) || 0;
    if (lastS) {
      cur = Math.min(114, Math.max(1, lastS));
      playerEl.hidden = false;
      audio.src = srcOf(cur);
      var at = qSurah ? 0 : (parseFloat(lsGet(LS.pos, '0')) || 0);
      audio.addEventListener('loadedmetadata', function once() {
        audio.removeEventListener('loadedmetadata', once);
        if (at) { try { audio.currentTime = at; } catch (e) {} }
      });
      audio.load();
      paintNow();
      paintList('');
      if (qSurah) play(cur, 0);
    }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
