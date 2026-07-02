/* ============================================================
   ChatHelpers — مشتركة بين الدردشة الفردية والجماعية
   ============================================================ */
window.ChatHelpers = (function(){
  function escape(s){ var d=document.createElement('div'); d.textContent=s||''; return d.innerHTML; }

  function pad(n){ return n<10 ? '0'+n : ''+n; }

  function fmtTime(iso){
    var d = new Date(iso); if (isNaN(d)) return '';
    return d.toLocaleTimeString('ar-EG', {hour:'2-digit', minute:'2-digit'});
  }

  function dayKey(iso){
    var d = new Date(iso); if (isNaN(d)) return '';
    return d.getFullYear()+'-'+pad(d.getMonth()+1)+'-'+pad(d.getDate());
  }

  function dayLabel(iso){
    var d = new Date(iso); if (isNaN(d)) return '';
    var now = new Date();
    var today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    var that = new Date(d.getFullYear(), d.getMonth(), d.getDate());
    var diff = Math.round((today - that) / 86400000);
    if (diff === 0) return 'اليوم';
    if (diff === 1) return 'أمس';
    if (diff > 1 && diff < 7) return d.toLocaleDateString('ar-EG', {weekday:'long'});
    return d.toLocaleDateString('ar-EG', {year:'numeric', month:'long', day:'numeric'});
  }

  function fmtSec(s){ var m=Math.floor(s/60), x=s%60; return m+':'+(x<10?'0':'')+x; }

  // مشغل صوت بسيط زي واتساب
  function audioPlayerHTML(src, id){
    return '<div class="wa-audio2" data-src="'+src+'">'+
             '<button type="button" class="wa-a-play" aria-label="تشغيل">'+
               '<svg class="ic-play" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>'+
               '<svg class="ic-pause" viewBox="0 0 24 24" fill="currentColor"><path d="M6 5h4v14H6zM14 5h4v14h-4z"/></svg>'+
             '</button>'+
             '<div class="wa-a-mid">'+
               '<div class="wa-a-wave"><div class="wa-a-progress"></div></div>'+
               '<div class="wa-a-time">0:00</div>'+
             '</div>'+
           '</div>';
  }

  function bindAudio(root){
    (root || document).querySelectorAll('.wa-audio2:not([data-bound])').forEach(function(box){
      box.dataset.bound = '1';
      var src = box.dataset.src;
      var audio = new Audio();
      audio.preload = 'metadata';
      audio.src = src;
      var btn = box.querySelector('.wa-a-play');
      var prog = box.querySelector('.wa-a-progress');
      var timeEl = box.querySelector('.wa-a-time');
      var duration = 0;

      audio.addEventListener('loadedmetadata', function(){
        duration = isFinite(audio.duration) ? audio.duration : 0;
        if (duration) timeEl.textContent = fmtSec(Math.floor(duration));
      });
      audio.addEventListener('timeupdate', function(){
        if (!duration && isFinite(audio.duration)) duration = audio.duration;
        var t = audio.currentTime;
        if (duration > 0) prog.style.width = ((t/duration)*100).toFixed(1)+'%';
        timeEl.textContent = fmtSec(Math.floor(duration - t > 0 ? (duration - t) : t));
      });
      audio.addEventListener('ended', function(){
        box.classList.remove('is-playing');
        prog.style.width = '0%';
        timeEl.textContent = duration ? fmtSec(Math.floor(duration)) : '0:00';
      });
      audio.addEventListener('error', function(){
        timeEl.textContent = '⚠';
      });
      btn.addEventListener('click', function(){
        // أوقف باقي الأصوات
        document.querySelectorAll('.wa-audio2.is-playing').forEach(function(o){
          if (o !== box) { o.classList.remove('is-playing'); var a = o._audio; if (a) a.pause(); }
        });
        if (audio.paused) {
          audio.play().then(function(){ box.classList.add('is-playing'); })
            .catch(function(){ alert('المتصفح ما يقدرش يشغّل الصوت'); });
        } else {
          audio.pause();
          box.classList.remove('is-playing');
        }
      });
      box._audio = audio;
    });
  }

  // التسجيل الصوتي
  function attachRecorder(opts){
    var micBtn = opts.micBtn;
    var composer = opts.composer;
    var onSend = opts.onSend;

    // أنشئ شريط التسجيل لو مش موجود
    var bar = document.getElementById('recBar');
    if (!bar) return;
    var recTime = document.getElementById('recTime');
    var recCancel = document.getElementById('recCancel');
    var recSend = document.getElementById('recSend');

    var mediaRec=null, chunks=[], stream=null, startTs=0, tickId=null, cancelled=false, mimeUsed='audio/webm';
    var isRecording=false, isStopping=false, isSending=false, sentOnce=false;

    function start(){
      if (isRecording || isStopping || isSending) return; // امنع بدء تسجيل مزدوج
      if (!navigator.mediaDevices || !window.MediaRecorder) {
        alert('المتصفح ما يدعمش التسجيل');
        return;
      }
      isRecording = true;
      navigator.mediaDevices.getUserMedia({audio:true}).then(function(s){
        stream = s; chunks = []; cancelled = false; sentOnce = false;
        var mime = '';
        var candidates = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/mpeg', 'audio/ogg'];
        for (var i=0;i<candidates.length;i++){
          if (MediaRecorder.isTypeSupported(candidates[i])){ mime = candidates[i]; break; }
        }
        try {
          mediaRec = mime ? new MediaRecorder(s, {mimeType:mime}) : new MediaRecorder(s);
        } catch(e) {
          mediaRec = new MediaRecorder(s);
        }
        mimeUsed = mediaRec.mimeType || mime || 'audio/webm';
        mediaRec.ondataavailable = function(e){ if (e.data && e.data.size) chunks.push(e.data); };
        mediaRec.onstop = function(){
          try { stream.getTracks().forEach(function(t){ t.stop(); }); } catch(e){}
          isRecording = false; isStopping = false;
          if (cancelled || !chunks.length) { chunks = []; return; }
          if (sentOnce) { chunks = []; return; } // امنع إرسال مكرر
          sentOnce = true;
          var blob = new Blob(chunks, {type: mimeUsed});
          chunks = [];
          if (blob.size < 1000) { alert('التسجيل قصير جدًا'); return; }
          isSending = true;
          try { onSend(blob, mimeUsed, function(){ isSending = false; }); }
          catch(e){ isSending = false; }
        };
        mediaRec.start();
        startTs = Date.now();
        bar.hidden = false;
        bar.classList.add('is-active');
        if (composer) composer.style.display = 'none';
        recTime.textContent = '0:00';
        tickId = setInterval(function(){
          recTime.textContent = fmtSec(Math.floor((Date.now()-startTs)/1000));
        }, 250);
      }).catch(function(){
        isRecording = false;
        alert('فعّل صلاحية الميكروفون من إعدادات المتصفح');
      });
    }

    function stop(send){
      if (isStopping) return;                 // امنع الاستدعاء المزدوج
      if (!isRecording && !mediaRec) return;
      isStopping = true;
      cancelled = !send;
      if (mediaRec && mediaRec.state !== 'inactive') {
        try { mediaRec.stop(); } catch(e){}
      } else if (stream) {
        try { stream.getTracks().forEach(function(t){ t.stop(); }); } catch(e){}
        isRecording = false; isStopping = false;
      }
      clearInterval(tickId);
      bar.hidden = true;
      bar.classList.remove('is-active');
      if (composer) composer.style.display = '';
      recTime.textContent = '0:00';
    }

    var lastMicTs = 0, lastSendTs = 0, lastCancelTs = 0;
    micBtn.addEventListener('click', function(e){
      var now = Date.now();
      if (now - lastMicTs < 400) { e.preventDefault(); return; }
      lastMicTs = now;
      start();
    });
    recCancel.addEventListener('click', function(e){
      var now = Date.now();
      if (now - lastCancelTs < 400) { e.preventDefault(); return; }
      lastCancelTs = now;
      stop(false);
    });
    recSend.addEventListener('click', function(e){
      var now = Date.now();
      if (now - lastSendTs < 500) { e.preventDefault(); return; }
      lastSendTs = now;
      recSend.disabled = true;
      stop(true);
      setTimeout(function(){ recSend.disabled = false; }, 800);
    });
  }

  // تحويل الروابط لروابط قابلة للضغط داخل نص الرسالة
  function linkify(text){
    var esc = escape(text || '');
    var re = /((https?:\/\/|www\.)[^\s<]+[^\s<.,!?:;\)"'])/gi;
    return esc.replace(re, function(u){
      var href = u.match(/^https?:\/\//i) ? u : 'https://' + u;
      return '<a href="'+href+'" target="_blank" rel="noopener nofollow" class="wa-link">'+u+'</a>';
    }).replace(/\n/g,'<br>');
  }

  // إظهار Toast بسيط
  function toast(msg){
    var t = document.createElement('div');
    t.className = 'wa-toast'; t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(function(){ t.classList.add('show'); }, 10);
    setTimeout(function(){ t.classList.remove('show'); setTimeout(function(){ t.remove(); }, 250); }, 1500);
  }

  // نسخ نص للحافظة
  function copyText(text){
    if (!text) return Promise.resolve(false);
    if (navigator.clipboard && window.isSecureContext){
      return navigator.clipboard.writeText(text).then(function(){ return true; }).catch(function(){ return false; });
    }
    try {
      var ta = document.createElement('textarea');
      ta.value = text; ta.style.position='fixed'; ta.style.opacity='0';
      document.body.appendChild(ta); ta.select();
      var ok = document.execCommand('copy'); ta.remove();
      return Promise.resolve(!!ok);
    } catch(e){ return Promise.resolve(false); }
  }

  // ضغط طويل / نقرة مزدوجة على الفقاعات لنسخ محتوى النص
  function bindCopy(root){
    (root || document).querySelectorAll('.wa-bubble:not([data-copybound])').forEach(function(b){
      b.dataset.copybound = '1';
      var timer = null, longPressed = false;
      function getText(){
        var t = b.querySelector('.wa-text');
        return t ? t.innerText : '';
      }
      function trigger(){
        var txt = getText();
        if (!txt) return;
        copyText(txt).then(function(ok){ toast(ok ? 'تم نسخ الرسالة ✓' : 'تعذّر النسخ'); });
      }
      b.addEventListener('touchstart', function(){
        longPressed = false;
        timer = setTimeout(function(){ longPressed = true; trigger(); }, 550);
      }, {passive:true});
      b.addEventListener('touchend', function(e){
        clearTimeout(timer);
        if (longPressed) { e.preventDefault(); }
      });
      b.addEventListener('touchmove', function(){ clearTimeout(timer); });
      b.addEventListener('dblclick', trigger);
      b.addEventListener('mousedown', function(e){
        if (e.button !== 0) return;
        timer = setTimeout(function(){ trigger(); }, 550);
      });
      b.addEventListener('mouseup', function(){ clearTimeout(timer); });
      b.addEventListener('mouseleave', function(){ clearTimeout(timer); });
    });
  }

  // ======== ضغط الصور قبل الرفع ========
  // يقلل حجم الصورة قدر الإمكان مع الحفاظ على جودة معقولة
  function compressImage(file, opts){
    opts = opts || {};
    var maxDim = opts.maxDim || 1280;      // أقصى بُعد (عرض/ارتفاع)
    var quality = opts.quality || 0.72;    // جودة JPEG
    var mime = opts.mime || 'image/jpeg';
    return new Promise(function(resolve, reject){
      if (!file || !file.type || file.type.indexOf('image/') !== 0) {
        return resolve(file);
      }
      // ملفات GIF نتركها كما هي (متحركة)
      if (file.type === 'image/gif') return resolve(file);
      var url = URL.createObjectURL(file);
      var img = new Image();
      img.onload = function(){
        try {
          var w = img.naturalWidth, h = img.naturalHeight;
          if (!w || !h) { URL.revokeObjectURL(url); return resolve(file); }
          var scale = Math.min(1, maxDim / Math.max(w, h));
          var nw = Math.max(1, Math.round(w * scale));
          var nh = Math.max(1, Math.round(h * scale));
          var canvas = document.createElement('canvas');
          canvas.width = nw; canvas.height = nh;
          var ctx = canvas.getContext('2d');
          ctx.drawImage(img, 0, 0, nw, nh);
          URL.revokeObjectURL(url);
          canvas.toBlob(function(blob){
            if (!blob) return resolve(file);
            // لو الأصل أصغر من الناتج، سيبه كما هو
            if (blob.size >= file.size) return resolve(file);
            var name = (file.name || 'image').replace(/\.[^.]+$/, '') + '.jpg';
            try {
              var out = new File([blob], name, {type: mime, lastModified: Date.now()});
              resolve(out);
            } catch(e){
              blob.name = name; blob.lastModified = Date.now();
              resolve(blob);
            }
          }, mime, quality);
        } catch(e){ URL.revokeObjectURL(url); resolve(file); }
      };
      img.onerror = function(){ URL.revokeObjectURL(url); resolve(file); };
      img.src = url;
    });
  }

  // يضغط ملف داخل <input type=file> ثم يستدعي callback (أو يقدّم form تلقائيًا)
  function attachImageAutoCompress(input, opts){
    if (!input || input.dataset.compressBound) return;
    input.dataset.compressBound = '1';
    var onDone = (opts && opts.onDone) || null;
    var autoSubmit = opts && opts.autoSubmitForm;
    input.addEventListener('change', function(){
      var f = input.files && input.files[0];
      if (!f) return;
      compressImage(f, opts).then(function(nf){
        try {
          var dt = new DataTransfer();
          dt.items.add(nf);
          input.files = dt.files;
        } catch(e){}
        if (onDone) onDone(nf);
        if (autoSubmit) {
          var form = autoSubmit === true ? input.form : document.getElementById(autoSubmit);
          if (form) form.submit();
        }
      });
    });
  }

  return {
    escape: escape,
    linkify: linkify,
    fmtTime: fmtTime,
    fmtSec: fmtSec,
    dayKey: dayKey,
    dayLabel: dayLabel,
    audioPlayerHTML: audioPlayerHTML,
    bindAudio: bindAudio,
    bindCopy: bindCopy,
    copyText: copyText,
    toast: toast,
    attachRecorder: attachRecorder,
    compressImage: compressImage,
    attachImageAutoCompress: attachImageAutoCompress
  };
})();
