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
    // موجة صوت بأعمدة حقيقية بارتفاعات متغيّرة (seeded per src)
    var BAR_COUNT = 42;
    var seed = 0;
    for (var i=0;i<src.length;i++){ seed = (seed*31 + src.charCodeAt(i)) >>> 0; }
    function rnd(){ seed = (seed*1664525 + 1013904223) >>> 0; return (seed & 0xffff) / 0xffff; }
    var bars = '';
    for (var j=0;j<BAR_COUNT;j++){
      // منحنى ناعم: يعلى في النص ويقل في الأطراف
      var t = j/(BAR_COUNT-1);
      var envelope = 0.55 + 0.45*Math.sin(t*Math.PI);
      var h = Math.round((0.22 + rnd()*0.78) * envelope * 100);
      if (h < 14) h = 14;
      bars += '<i style="height:'+h+'%"></i>';
    }
    return '<div class="wa-audio2" data-src="'+src+'">'+
             '<button type="button" class="wa-a-play" aria-label="تشغيل">'+
               '<svg class="ic-play" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>'+
               '<svg class="ic-pause" viewBox="0 0 24 24" fill="currentColor"><path d="M6 5h4v14H6zM14 5h4v14h-4z"/></svg>'+
             '</button>'+
             '<div class="wa-a-mid">'+
               '<div class="wa-a-wave">'+
                 '<div class="wa-a-bars">'+bars+'</div>'+
                 '<div class="wa-a-bars wa-a-bars--fill" aria-hidden="true">'+bars+'</div>'+
                 '<span class="wa-a-thumb" aria-hidden="true"></span>'+
               '</div>'+
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
      var wave = box.querySelector('.wa-a-wave');
      var fill = box.querySelector('.wa-a-bars--fill');
      var timeEl = box.querySelector('.wa-a-time');
      var duration = 0;

      function setProgress(p){
        if (p < 0) p = 0; if (p > 1) p = 1;
        if (fill) fill.style.setProperty('--p', (p*100).toFixed(2)+'%');
      }
      setProgress(0);

      if (wave){
        wave.addEventListener('click', function(ev){
          if (!duration) return;
          var r = wave.getBoundingClientRect();
          var x = ev.clientX - r.left;
          var p = Math.max(0, Math.min(1, x / r.width));
          try { audio.currentTime = p * duration; setProgress(p); } catch(_){}
        });
      }

      audio.addEventListener('loadedmetadata', function(){
        duration = isFinite(audio.duration) ? audio.duration : 0;
        if (duration) timeEl.textContent = fmtSec(Math.floor(duration));
      });
      audio.addEventListener('timeupdate', function(){
        if (!duration && isFinite(audio.duration)) duration = audio.duration;
        var t = audio.currentTime;
        if (duration > 0) setProgress(t/duration);
        timeEl.textContent = fmtSec(Math.floor(duration - t > 0 ? (duration - t) : t));
      });
      audio.addEventListener('ended', function(){
        box.classList.remove('is-playing');
        setProgress(0);
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
            .catch(function(){ (window.appAlert||alert)('المتصفح ما يقدرش يشغّل الصوت','error'); });
        } else {
          audio.pause();
          box.classList.remove('is-playing');
        }
      });
      box._audio = audio;
    });
  }

  // ========== التسجيل الصوتي — نمط واتساب (ضغط مطوّل + معاينة) ==========
  function attachRecorder(opts){
    var micBtn   = opts.micBtn;
    var composer = opts.composer;
    var onSend   = opts.onSend;

    var bar = document.getElementById('recBar');
    if (!bar) return;
    var recTime   = document.getElementById('recTime');
    var recCancel = document.getElementById('recCancel');
    var recSend   = document.getElementById('recSend');
    var recMid    = bar.querySelector('.wa-rec-mid');
    var recHint   = bar.querySelector('.wa-rec-hint');

    // نضيف طبقة "اسحب للإلغاء"
    if (!bar.querySelector('.wa-rec-slide')){
      var slide = document.createElement('div');
      slide.className = 'wa-rec-slide';
      slide.innerHTML = '<span class="wa-rec-arrow">‹</span><span>اسحب للإلغاء</span>';
      bar.appendChild(slide);
    }
    var slideEl = bar.querySelector('.wa-rec-slide');

    // مربّع معاينة (بيظهر بعد التسجيل)
    var preview = null;
    function ensurePreview(){
      if (preview) return preview;
      preview = document.createElement('div');
      preview.className = 'wa-rec-preview';
      preview.hidden = true;
      preview.innerHTML =
        '<button type="button" class="wa-rec-cancel" data-role="prev-del" aria-label="حذف">'+
          '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path stroke-linecap="round" stroke-linejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9M4.772 5.79h14.456"/></svg>'+
        '</button>'+
        '<div class="wa-rec-preview-mid" data-role="prev-player"></div>'+
        '<button type="button" class="wa-rec-send" data-role="prev-send" aria-label="إرسال">'+
          '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M2.01 21l20.99-9L2.01 3 2 10l15 2-15 2z"/></svg>'+
        '</button>';
      bar.parentNode.insertBefore(preview, bar.nextSibling);
      return preview;
    }

    var mediaRec=null, chunks=[], stream=null, startTs=0, tickId=null;
    var mimeUsed='audio/webm';
    var isRecording=false, cancelled=false, longPressed=false;
    var pressTimer=null, startX=0, currentDX=0, activePointerId=null;
    var lastBlob=null, previewURL=null;

    function resetAll(){
      if (mediaRec && mediaRec.state !== 'inactive'){ try{ mediaRec.stop(); }catch(_){}}
      if (stream){ try{ stream.getTracks().forEach(function(t){t.stop();}); }catch(_){} }
      if (tickId){ clearInterval(tickId); tickId=null; }
      if (previewURL){ try{ URL.revokeObjectURL(previewURL); }catch(_){} previewURL=null; }
      mediaRec=null; stream=null; chunks=[]; isRecording=false; cancelled=false;
      longPressed=false; currentDX=0; activePointerId=null; lastBlob=null;
      if (pressTimer){ clearTimeout(pressTimer); pressTimer=null; }
      bar.hidden = true;
      bar.classList.remove('is-active');
      if (slideEl){ slideEl.style.transform=''; slideEl.style.opacity=''; }
      if (preview){ preview.hidden = true; preview.querySelector('[data-role=prev-player]').innerHTML=''; }
      if (composer) composer.style.display = '';
      recTime.textContent = '0:00';
      micBtn.classList.remove('is-recording');
    }

    function showRecordingUI(){
      bar.hidden = false;
      bar.classList.add('is-active');
      if (composer) composer.style.display = 'none';
      if (preview) preview.hidden = true;
      recTime.textContent = '0:00';
      if (recHint) recHint.textContent = '';
      micBtn.classList.add('is-recording');
    }

    function startRecording(){
      if (isRecording) return;
      if (!navigator.mediaDevices || !window.MediaRecorder){
        (window.appAlert||alert)('المتصفح ما يدعمش التسجيل','error'); return;
      }
      isRecording = true;
      showRecordingUI();
      navigator.mediaDevices.getUserMedia({audio:true}).then(function(s){
        if (!isRecording){ // اتلغى قبل ما يبدأ
          try{ s.getTracks().forEach(function(t){t.stop();}); }catch(_){}
          return;
        }
        stream = s; chunks = []; cancelled = false;
        var mime = '';
        var candidates = ['audio/webm;codecs=opus','audio/webm','audio/mp4','audio/mpeg','audio/ogg'];
        for (var i=0;i<candidates.length;i++){
          if (MediaRecorder.isTypeSupported(candidates[i])){ mime = candidates[i]; break; }
        }
        try { mediaRec = mime ? new MediaRecorder(s,{mimeType:mime}) : new MediaRecorder(s); }
        catch(e){ mediaRec = new MediaRecorder(s); }
        mimeUsed = mediaRec.mimeType || mime || 'audio/webm';
        mediaRec.ondataavailable = function(e){ if (e.data && e.data.size) chunks.push(e.data); };
        mediaRec.onstop = function(){
          try { stream.getTracks().forEach(function(t){ t.stop(); }); } catch(_){}
          stream = null;
          var wasCancelled = cancelled;
          isRecording = false;
          if (tickId){ clearInterval(tickId); tickId=null; }
          if (wasCancelled || !chunks.length){
            chunks = [];
            resetAll();
            return;
          }
          var blob = new Blob(chunks, {type: mimeUsed});
          chunks = [];
          if (blob.size < 1000){
            (window.appAlert||alert)('التسجيل قصير جدًا','error');
            resetAll();
            return;
          }
          lastBlob = blob;
          openPreview(blob);
        };
        try { mediaRec.start(); } catch(_){}
        startTs = Date.now();
        tickId = setInterval(function(){
          recTime.textContent = fmtSec(Math.floor((Date.now()-startTs)/1000));
        }, 250);
      }).catch(function(){
        isRecording = false;
        resetAll();
        (window.appAlert||alert)('فعّل صلاحية الميكروفون من إعدادات المتصفح','error');
      });
    }

    function stopRecording(sendAfter){
      cancelled = !sendAfter;
      if (mediaRec && mediaRec.state !== 'inactive'){
        try { mediaRec.stop(); } catch(_){}
      } else {
        // ما كانش بدأ فعلاً
        resetAll();
      }
    }

    function openPreview(blob){
      var p = ensurePreview();
      bar.hidden = true;
      bar.classList.remove('is-active');
      micBtn.classList.remove('is-recording');
      if (composer) composer.style.display = 'none';
      previewURL = URL.createObjectURL(blob);
      var mid = p.querySelector('[data-role=prev-player]');
      mid.innerHTML = audioPlayerHTML(previewURL);
      bindAudio(p);
      p.hidden = false;
    }

    // ==== أحداث الضغط على المايك ====
    function onPress(e){
      if (isRecording) return;
      if (preview && !preview.hidden) return;
      var pt = e.touches ? e.touches[0] : e;
      activePointerId = e.pointerId != null ? e.pointerId : 1;
      startX = pt.clientX;
      currentDX = 0;
      longPressed = false;
      if (pressTimer) clearTimeout(pressTimer);
      pressTimer = setTimeout(function(){
        longPressed = true;
        try { if (navigator.vibrate) navigator.vibrate(15); } catch(_){}
        startRecording();
      }, 220);
    }
    function onMove(e){
      if (!isRecording && !pressTimer) return;
      var pt = e.touches ? e.touches[0] : e;
      currentDX = pt.clientX - startX;
      // RTL: السحب لليمين = إلغاء (يمين في الشاشة العربية = عكس المايك)
      // لكن نخلي أي سحب بعيد يعتبر إلغاء
      var dist = Math.abs(currentDX);
      if (slideEl && isRecording){
        var off = Math.min(dist, 120);
        slideEl.style.transform = 'translateX('+(currentDX>0?off:-off)+'px)';
        slideEl.style.opacity = String(Math.max(0.3, 1 - dist/140));
      }
      if (dist > 110){
        // ألغِ
        if (pressTimer){ clearTimeout(pressTimer); pressTimer=null; }
        if (isRecording) stopRecording(false);
        longPressed = false;
      }
    }
    function onRelease(e){
      if (pressTimer){ clearTimeout(pressTimer); pressTimer=null; }
      if (!longPressed && !isRecording){
        // نقرة قصيرة
        (window.ChatHelpers && ChatHelpers.toast) ? ChatHelpers.toast('اضغط مطوّلاً للتسجيل 🎤')
                                                   : null;
        return;
      }
      if (isRecording){
        // لو مسحب بعيد يبقى إلغاء، غير كده معاينة
        stopRecording(Math.abs(currentDX) <= 110);
      }
    }

    // Pointer events (يشمل الماوس والمس)
    if (window.PointerEvent){
      micBtn.addEventListener('pointerdown', function(e){ e.preventDefault(); onPress(e); try{micBtn.setPointerCapture(e.pointerId);}catch(_){} });
      micBtn.addEventListener('pointermove', onMove);
      micBtn.addEventListener('pointerup',   onRelease);
      micBtn.addEventListener('pointercancel', function(){ if (isRecording) stopRecording(false); else resetAll(); });
      micBtn.addEventListener('pointerleave', function(e){ /* نتجاهل */ });
    } else {
      micBtn.addEventListener('touchstart', function(e){ e.preventDefault(); onPress(e); }, {passive:false});
      micBtn.addEventListener('touchmove', onMove, {passive:true});
      micBtn.addEventListener('touchend', onRelease);
      micBtn.addEventListener('touchcancel', function(){ if (isRecording) stopRecording(false); });
      micBtn.addEventListener('mousedown', onPress);
      window.addEventListener('mousemove', onMove);
      window.addEventListener('mouseup', onRelease);
    }
    // منع القائمة المنبثقة على الضغط المطوّل
    micBtn.addEventListener('contextmenu', function(e){ e.preventDefault(); });

    // زر إلغاء التسجيل (أثناء التسجيل)
    if (recCancel){
      recCancel.addEventListener('click', function(){ stopRecording(false); });
    }
    // زر إرسال أثناء التسجيل (يوقف ويبعت مباشرة بدون معاينة — سلوك اختصار)
    if (recSend){
      recSend.addEventListener('click', function(){
        if (!isRecording) return;
        // نبعت مباشرة بدون معاينة
        var directSend = true;
        cancelled = false;
        // نستبدل onstop مؤقتاً بحيث يبعت فوراً
        var origOnStop = mediaRec ? mediaRec.onstop : null;
        if (mediaRec){
          mediaRec.onstop = function(){
            try { stream.getTracks().forEach(function(t){ t.stop(); }); } catch(_){}
            stream = null;
            if (tickId){ clearInterval(tickId); tickId=null; }
            isRecording = false;
            var blob = new Blob(chunks, {type: mimeUsed}); chunks=[];
            if (blob.size < 1000){ (window.appAlert||alert)('التسجيل قصير جدًا','error'); resetAll(); return; }
            try { onSend(blob, mimeUsed, function(){}); } catch(_){}
            resetAll();
          };
          try { mediaRec.stop(); } catch(_){}
        }
      });
    }

    // أزرار المعاينة (حذف / إرسال)
    bar.parentNode.addEventListener('click', function(ev){
      var t = ev.target.closest && ev.target.closest('[data-role]');
      if (!t || !preview || preview.hidden) return;
      var role = t.dataset.role;
      if (role === 'prev-del'){
        resetAll();
      } else if (role === 'prev-send'){
        if (!lastBlob) { resetAll(); return; }
        var b = lastBlob, m = mimeUsed;
        // امنع الدبل-كليك
        t.disabled = true;
        try { onSend(b, m, function(){}); } catch(_){}
        resetAll();
      }
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

  // نقرة مزدوجة على الفقاعات لنسخ محتوى النص
  // (تم إزالة الضغط المطوّل عشان يفتح قائمة التفاعلات بدل النسخ)
  function bindCopy(root){
    (root || document).querySelectorAll('.wa-bubble:not([data-copybound])').forEach(function(b){
      b.dataset.copybound = '1';
      function getText(){
        var t = b.querySelector('.wa-text');
        return t ? t.innerText : '';
      }
      function trigger(){
        var txt = getText();
        if (!txt) return;
        copyText(txt).then(function(ok){ toast(ok ? 'تم نسخ الرسالة ✓' : 'تعذّر النسخ'); });
      }
      b.addEventListener('dblclick', trigger);
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
