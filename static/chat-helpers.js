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

    function start(){
      if (!navigator.mediaDevices || !window.MediaRecorder) {
        alert('المتصفح ما يدعمش التسجيل');
        return;
      }
      navigator.mediaDevices.getUserMedia({audio:true}).then(function(s){
        stream = s; chunks = []; cancelled = false;
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
          stream.getTracks().forEach(function(t){ t.stop(); });
          if (cancelled || !chunks.length) return;
          var blob = new Blob(chunks, {type: mimeUsed});
          // الحد الأدنى نص ثانية تقريبا
          if (blob.size < 1000) {
            alert('التسجيل قصير جدًا');
            return;
          }
          onSend(blob, mimeUsed);
        };
        mediaRec.start();
        startTs = Date.now();
        bar.hidden = false;
        if (composer) composer.style.display = 'none';
        recTime.textContent = '0:00';
        tickId = setInterval(function(){
          recTime.textContent = fmtSec(Math.floor((Date.now()-startTs)/1000));
        }, 250);
      }).catch(function(){ alert('فعّل صلاحية الميكروفون من إعدادات المتصفح'); });
    }

    function stop(send){
      cancelled = !send;
      if (mediaRec && mediaRec.state !== 'inactive') {
        try { mediaRec.stop(); } catch(e){}
      } else if (stream) {
        stream.getTracks().forEach(function(t){ t.stop(); });
      }
      clearInterval(tickId);
      bar.hidden = true;
      if (composer) composer.style.display = '';
      recTime.textContent = '0:00';
    }

    micBtn.addEventListener('click', start);
    recCancel.addEventListener('click', function(){ stop(false); });
    recSend.addEventListener('click', function(){ stop(true); });
  }

  return {
    escape: escape,
    fmtTime: fmtTime,
    fmtSec: fmtSec,
    dayKey: dayKey,
    dayLabel: dayLabel,
    audioPlayerHTML: audioPlayerHTML,
    bindAudio: bindAudio,
    attachRecorder: attachRecorder
  };
})();
