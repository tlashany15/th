/* ==========================================================================
   mushaf-v19.js — طبقة تطوير فوق قارئ المصحف (mushaf-v18)
   ------------------------------------------------------------------
   • شريط تقدّم القراءة + نسبة الختمة (604 صفحة)
   • اضغط على أي آية → لوحة الآية: تفسير الميسّر، تلاوة الآية،
     نسخ، مشاركة، تعليم الآية (علامة على الآية نفسها)
   • مشغّل تلاوة للصفحة كلها (تشغيل/إيقاف + انتقال تلقائي للصفحة اللي بعدها)
   • كل حاجة بتتخزن محليًا وبتشتغل جوه أي WebView من غير أي مكتبات
   ========================================================================== */
(function () {
  'use strict';

  var RECITERS = [
    { id: 'ar.alafasy',        name: 'مشاري العفاسي',  cdn: 'Alafasy_128kbps' },
    { id: 'ar.abdulbasit',     name: 'عبد الباسط',     cdn: 'Abdul_Basit_Murattal_192kbps' },
    { id: 'ar.minshawi',       name: 'المنشاوي',        cdn: 'Minshawy_Murattal_128kbps' },
    { id: 'ar.husary',         name: 'الحصري',          cdn: 'Husary_128kbps' }
  ];
  var LS = {
    reciter: 'mushaf.reciter',
    ayaMark: 'mushaf.ayaMark',
    read:    'mushaf.readPages'
  };

  function lsGet(k, d) { try { var v = localStorage.getItem(k); return v === null ? d : v; } catch (e) { return d; } }
  function lsSet(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }
  function pad3(n) { return ('00' + n).slice(-3); }
  function toast(msg) {
    var t = document.getElementById('qrToast');
    if (!t) { t = document.createElement('div'); t.id = 'qrToast'; t.className = 'qr-toast'; document.body.appendChild(t); }
    t.textContent = msg;
    requestAnimationFrame(function () { t.classList.add('is-on'); });
    clearTimeout(t._h);
    t._h = setTimeout(function () { t.classList.remove('is-on'); }, 1800);
  }
  function buzz(ms) { try { navigator.vibrate && navigator.vibrate(ms || 8); } catch (e) {} }

  var root, audio, curPage = 0, playing = false, queue = [], qi = 0;

  function reciter() {
    var id = lsGet(LS.reciter, RECITERS[0].id);
    for (var i = 0; i < RECITERS.length; i++) if (RECITERS[i].id === id) return RECITERS[i];
    return RECITERS[0];
  }
  function ayaUrl(surah, aya) {
    return 'https://everyayah.com/data/' + reciter().cdn + '/' + pad3(surah) + pad3(aya) + '.mp3';
  }

  /* ================= 1) شريط التقدّم + الختمة ================= */
  function readSet() {
    try { return JSON.parse(lsGet(LS.read, '[]')) || []; } catch (e) { return []; }
  }
  function markRead(p) {
    var a = readSet();
    if (a.indexOf(p) === -1) { a.push(p); if (a.length > 604) a = a.slice(-604); lsSet(LS.read, JSON.stringify(a)); }
  }
  function buildProgress() {
    if (document.getElementById('qr19Prog')) return;
    var head = root.querySelector('.qr-head') || root.firstElementChild;
    if (!head) return;
    var bar = document.createElement('div');
    bar.id = 'qr19Prog';
    bar.className = 'qr19-prog';
    bar.innerHTML = '<i id="qr19ProgFill"></i><span id="qr19ProgTxt"></span>';
    head.insertAdjacentElement('afterend', bar);
  }
  function syncProgress(p) {
    var fill = document.getElementById('qr19ProgFill');
    var txt = document.getElementById('qr19ProgTxt');
    if (!fill || !txt) return;
    var pct = Math.round((p / 604) * 100);
    fill.style.width = pct + '%';
    var done = readSet().length;
    txt.textContent = 'صفحة ' + p + ' من 604 · ' + pct + '٪ · قرأت ' + done + ' صفحة من الختمة';
  }

  /* ================= 2) مشغّل تلاوة الصفحة ================= */
  function buildPlayer() {
    if (document.getElementById('qr19Bar')) return;
    var bar = document.createElement('div');
    bar.id = 'qr19Bar';
    bar.className = 'qr19-bar';
    bar.innerHTML =
      '<button type="button" class="qr19-play" id="qr19Play" aria-label="تشغيل تلاوة الصفحة">' + icPlay() + '</button>' +
      '<div class="qr19-bar-b"><b id="qr19BarT">تلاوة الصفحة</b><small id="qr19BarS">' + esc(reciter().name) + '</small></div>' +
      '<button type="button" class="qr19-rec" id="qr19Rec" aria-label="تغيير القارئ">' +
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v10.5"/><path d="M8.5 6.5A5 5 0 0 0 12 15a5 5 0 0 0 3.5-8.5"/><path d="M5 12a7 7 0 0 0 14 0"/><path d="M9 21h6"/></svg>' +
      '</button>';
    document.body.appendChild(bar);

    document.getElementById('qr19Play').addEventListener('click', function () {
      playing ? stopPlay() : startPlay();
    });
    document.getElementById('qr19Rec').addEventListener('click', openReciters);
  }
  function icPlay() {
    return '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M8 5.5v13l11-6.5z"/></svg>';
  }
  function icPause() {
    return '<svg viewBox="0 0 24 24" fill="currentColor"><rect x="7" y="5.5" width="3.6" height="13" rx="1.2"/><rect x="13.4" y="5.5" width="3.6" height="13" rx="1.2"/></svg>';
  }
  function setPlayIcon() {
    var b = document.getElementById('qr19Play');
    if (b) b.innerHTML = playing ? icPause() : icPlay();
    var bar = document.getElementById('qr19Bar');
    if (bar) bar.classList.toggle('is-playing', playing);
  }

  function pageAyahs() {
    return [].slice.call(document.querySelectorAll('#qrSheet .qr-aya')).map(function (el) {
      var k = (el.getAttribute('data-k') || '').split(':');
      return { el: el, s: parseInt(k[0], 10), n: parseInt(k[1], 10) };
    }).filter(function (a) { return a.s && a.n; });
  }

  function ensureAudio() {
    if (!audio) {
      audio = new Audio();
      audio.preload = 'auto';
      audio.addEventListener('ended', function () { next(); });
      audio.addEventListener('error', function () { if (playing) next(); });
    }
    return audio;
  }

  function startPlay(fromIdx) {
    queue = pageAyahs();
    if (!queue.length) { toast('استنى لحد ما الصفحة تحمّل'); return; }
    qi = fromIdx || 0;
    playing = true;
    setPlayIcon();
    playCurrent();
  }
  function playCurrent() {
    var a = queue[qi];
    if (!a) { stopPlay(); return; }
    document.querySelectorAll('.qr-aya.is-playing').forEach(function (e) { e.classList.remove('is-playing'); });
    a.el.classList.add('is-playing');
    try { a.el.scrollIntoView({ block: 'center', behavior: 'smooth' }); } catch (e) {}
    var t = document.getElementById('qr19BarT');
    if (t) t.textContent = 'آية ' + a.n + ' · تلاوة';
    var au = ensureAudio();
    au.src = ayaUrl(a.s, a.n);
    au.play().catch(function () { stopPlay(); toast('التلاوة محتاجة إنترنت'); });
  }
  function next() {
    if (!playing) return;
    qi++;
    if (qi >= queue.length) {
      // انتقال تلقائي للصفحة اللي بعدها
      var nb = document.getElementById('qrNext') || root.querySelector('.qr-next');
      if (nb && !nb.disabled) {
        nb.click();
        setTimeout(function () { if (playing) startPlay(0); }, 900);
        return;
      }
      stopPlay();
      return;
    }
    playCurrent();
  }
  function stopPlay() {
    playing = false;
    setPlayIcon();
    try { audio && audio.pause(); } catch (e) {}
    document.querySelectorAll('.qr-aya.is-playing').forEach(function (e) { e.classList.remove('is-playing'); });
    var t = document.getElementById('qr19BarT');
    if (t) t.textContent = 'تلاوة الصفحة';
  }

  function openReciters() {
    sheet('اختار القارئ', RECITERS.map(function (r) {
      var on = r.id === reciter().id;
      return '<button type="button" class="qr19-item' + (on ? ' is-on' : '') + '" data-r="' + r.id + '">' +
        '<span class="qr19-item-b"><b>' + esc(r.name) + '</b><small>تلاوة مرتّلة</small></span>' +
        (on ? '<span class="qr19-tick">✓</span>' : '') + '</button>';
    }).join(''), function (ov, close) {
      ov.addEventListener('click', function (e) {
        var b = e.target.closest('[data-r]');
        if (!b) return;
        lsSet(LS.reciter, b.getAttribute('data-r'));
        var s = document.getElementById('qr19BarS');
        if (s) s.textContent = reciter().name;
        if (playing) { stopPlay(); }
        toast('القارئ: ' + reciter().name);
        close();
      });
    });
  }

  /* ================= 3) لوحة الآية (تفسير + أدوات) ================= */
  var tafsirCache = {};
  function fetchTafsir(s, n) {
    var key = s + ':' + n;
    if (tafsirCache[key]) return Promise.resolve(tafsirCache[key]);
    var stored = lsGet('mushaf.tf.' + key, null);
    if (stored) { tafsirCache[key] = stored; return Promise.resolve(stored); }
    return fetch('https://api.alquran.cloud/v1/ayah/' + s + ':' + n + '/ar.muyassar')
      .then(function (r) { return r.json(); })
      .then(function (j) {
        var t = (j && j.data && j.data.text) || '';
        if (!t) throw new Error('empty');
        tafsirCache[key] = t;
        lsSet('mushaf.tf.' + key, t);
        return t;
      });
  }

  function openAyah(el) {
    var k = (el.getAttribute('data-k') || '').split(':');
    var s = parseInt(k[0], 10), n = parseInt(k[1], 10);
    if (!s || !n) return;
    var text = (el.textContent || '').replace(/﴿[^﴾]*﴾/g, '').trim();
    var sname = (root.querySelector('.qr-title') || {}).textContent || '';
    var marked = lsGet(LS.ayaMark, '') === (s + ':' + n);

    var html =
      '<div class="qr19-aya-txt">' + esc(text) + '</div>' +
      '<div class="qr19-aya-meta">' + esc(sname) + ' · آية ' + n + '</div>' +
      '<div class="qr19-acts">' +
        '<button type="button" class="qr19-act" data-a="play">' + icPlay() + '<span>تلاوة</span></button>' +
        '<button type="button" class="qr19-act" data-a="copy">' +
          '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="11" height="11" rx="2.4"/><path d="M15 5.5A2.5 2.5 0 0 0 12.5 3H6.5A2.5 2.5 0 0 0 4 5.5v6A2.5 2.5 0 0 0 6.5 14"/></svg><span>نسخ</span></button>' +
        '<button type="button" class="qr19-act" data-a="share">' +
          '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M12 16V4m0 0l-4 4m4-4l4 4"/><path d="M5 14v4.5A1.5 1.5 0 0 0 6.5 20h11a1.5 1.5 0 0 0 1.5-1.5V14"/></svg><span>مشاركة</span></button>' +
        '<button type="button" class="qr19-act' + (marked ? ' is-on' : '') + '" data-a="mark">' +
          '<svg viewBox="0 0 24 24" fill="' + (marked ? 'currentColor' : 'none') + '" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M6.5 3.5h11A1.5 1.5 0 0 1 19 5v15.2l-7-4.2-7 4.2V5a1.5 1.5 0 0 1 1.5-1.5z"/></svg><span>علّم الآية</span></button>' +
      '</div>' +
      '<div class="qr19-tf" id="qr19Tf"><div class="qr19-tf-h">التفسير الميسّر</div><div class="qr19-tf-b"><span class="qr19-dots"><i></i><i></i><i></i></span></div></div>';

    sheet('الآية ' + n, html, function (ov, close) {
      fetchTafsir(s, n).then(function (t) {
        var b = ov.querySelector('.qr19-tf-b');
        if (b) b.textContent = t;
      }).catch(function () {
        var b = ov.querySelector('.qr19-tf-b');
        if (b) b.textContent = 'التفسير محتاج إنترنت — حاول تاني بعد شوية.';
      });

      ov.addEventListener('click', function (e) {
        var b = e.target.closest('[data-a]');
        if (!b) return;
        var a = b.getAttribute('data-a');
        if (a === 'copy') {
          copy(text + '\n(' + sname + ' - آية ' + n + ')');
          toast('تم نسخ الآية');
          close();
        } else if (a === 'share') {
          var payload = text + '\n(' + sname + ' - آية ' + n + ')';
          if (navigator.share) navigator.share({ text: payload }).catch(function () {});
          else { copy(payload); toast('تم النسخ — إبعتها لأي حد'); }
          close();
        } else if (a === 'mark') {
          var key = s + ':' + n;
          if (lsGet(LS.ayaMark, '') === key) { lsSet(LS.ayaMark, ''); toast('تم شيل علامة الآية'); }
          else { lsSet(LS.ayaMark, key); toast('تم تعليم الآية'); }
          paintAyaMark();
          close();
        } else if (a === 'play') {
          close();
          var list = pageAyahs();
          for (var i = 0; i < list.length; i++) {
            if (list[i].s === s && list[i].n === n) { startPlay(i); break; }
          }
        }
      });
    });
  }

  function copy(t) {
    try { navigator.clipboard.writeText(t); }
    catch (e) {
      var ta = document.createElement('textarea');
      ta.value = t; document.body.appendChild(ta); ta.select();
      try { document.execCommand('copy'); } catch (_) {}
      ta.remove();
    }
  }

  function paintAyaMark() {
    var key = lsGet(LS.ayaMark, '');
    document.querySelectorAll('#qrSheet .qr-aya').forEach(function (el) {
      el.classList.toggle('is-aya-mark', !!key && el.getAttribute('data-k') === key);
    });
  }

  /* ================= شيت عام ================= */
  function sheet(title, bodyHTML, ready) {
    var ov = document.createElement('div');
    ov.className = 'qr-ov qr19-ov' + (root && root.classList.contains('is-paper') ? ' is-paper' : '');
    ov.innerHTML =
      '<div class="qr-sh qr19-sh" role="dialog" aria-label="' + esc(title) + '">' +
        '<div class="qr-sh-bar"></div>' +
        '<div class="qr19-sh-h">' + esc(title) + '</div>' +
        '<div class="qr19-sh-b">' + bodyHTML + '</div>' +
      '</div>';
    document.body.appendChild(ov);
    requestAnimationFrame(function () { ov.classList.add('is-open'); });
    function close() {
      ov.classList.remove('is-open');
      setTimeout(function () { ov.parentNode && ov.remove(); }, 260);
    }
    ov.addEventListener('click', function (e) { if (e.target === ov) close(); });
    ready && ready(ov, close);
    return close;
  }

  /* ================= التشغيل ================= */
  function currentPage() {
    var m = /[?&]page=(\d+)/.exec(location.search);
    if (m) return parseInt(m[1], 10);
    return parseInt(lsGet('mushaf.lastPage', '1'), 10) || 1;
  }

  function boot() {
    root = document.getElementById('musReader');
    if (!root) return;

    buildProgress();
    buildPlayer();

    // اضغط على آية → لوحة الآية
    document.addEventListener('click', function (e) {
      var a = e.target.closest('#qrSheet .qr-aya');
      if (!a) return;
      buzz(6);
      openAyah(a);
    });

    // راقب تغيّر الصفحة (الـ v18 بيعيد رسم #qrSheet)
    var mo = new MutationObserver(function () {
      var p = currentPage();
      if (p !== curPage) {
        curPage = p;
        markRead(p);
        syncProgress(p);
      }
      paintAyaMark();
    });
    mo.observe(root, { childList: true, subtree: true });

    curPage = currentPage();
    markRead(curPage);
    syncProgress(curPage);
    setTimeout(paintAyaMark, 600);

    window.addEventListener('beforeunload', stopPlay);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
