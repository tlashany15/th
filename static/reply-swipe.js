/* reply-swipe.js — سحب يمين للرد + منشن + جسر إرسال reply_to_id/mentions
   يعمل داخل صفحات الشات (تحتوي #msgs و #composer). */
(function(){
  if (!document.getElementById('msgs') || !document.getElementById('composer')) return;

  var state = { replyId: null, replyName: '', replyText: '' };
  window.__ChatReply = state;

  function esc(s){ var d=document.createElement('div'); d.textContent=s||''; return d.innerHTML; }

  function clearReply(){
    state.replyId = null; state.replyName = ''; state.replyText = '';
    var pv = document.getElementById('replyPreview'); if (pv) pv.remove();
  }

  function showReplyPreview(){
    var composer = document.getElementById('composer'); if (!composer) return;
    var pv = document.getElementById('replyPreview');
    if (!pv) {
      pv = document.createElement('div');
      pv.id = 'replyPreview';
      pv.className = 'wa-reply-preview';
      composer.parentNode.insertBefore(pv, composer);
    }
    pv.innerHTML =
      '<div class="wrp-body">'+
        '<div class="wrp-name">↩︎ الرد على '+esc(state.replyName)+'</div>'+
        '<div class="wrp-text">'+esc(state.replyText)+'</div>'+
      '</div>'+
      '<button type="button" class="wrp-close" aria-label="إلغاء الرد">✕</button>';
    pv.querySelector('.wrp-close').addEventListener('click', clearReply);
  }

  function setReply(id, name, text){
    state.replyId = id;
    state.replyName = name || 'رسالة';
    state.replyText = (text || '').slice(0, 140);
    showReplyPreview();
    var t = document.getElementById('textInput'); if (t) { t.focus(); }
  }
  window.__setChatReply = setReply;

  // --------- اعتراض fetch لحقن reply_to_id + mentions ---------
  var origFetch = window.fetch;
  window.fetch = function(url, opts){
    try {
      if (opts && opts.method === 'POST' && typeof url === 'string'
          && (/\/group\/send(\?|$)/.test(url) || /\/chat\/\d+\/send(\?|$)/.test(url))
          && opts.body instanceof FormData) {
        if (state.replyId){
          opts.body.append('reply_to_id', state.replyId);
        }
        // mentions من نص الرسالة (المجموعة فقط)
        if (/\/group\/send/.test(url) && window.__GroupMembers){
          var body = opts.body.get('body') || '';
          window.__GroupMembers.forEach(function(m){
            if (!m || !m.full_name) return;
            var re = new RegExp('@' + m.full_name.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'), 'g');
            if (re.test(body)) opts.body.append('mentions', m.id);
          });
        }
        return origFetch(url, opts).then(function(r){ clearReply(); return r; });
      }
    } catch(e){}
    return origFetch(url, opts);
  };

  // --------- سحب لليمين ---------
  var msgs = document.getElementById('msgs');
  var start = null, active = null;
  msgs.addEventListener('touchstart', function(e){
    var el = e.target.closest('.wa-msg'); if (!el) return;
    var t = e.touches[0];
    start = { x: t.clientX, y: t.clientY, el: el };
    active = null;
  }, {passive:true});
  msgs.addEventListener('touchmove', function(e){
    if (!start) return;
    var t = e.touches[0]; var dx = t.clientX - start.x; var dy = t.clientY - start.y;
    if (Math.abs(dy) > 30) { finishReset(); start = null; return; }
    // سحب لليمين البصري: في RTL، dx موجب = يمين. في LTR كذلك.
    if (dx < 4) return;
    active = start.el;
    active.classList.add('wa-swiping');
    var d = Math.min(dx, 80);
    active.style.transform = 'translateX(' + d + 'px)';
    if (!active.querySelector('.wa-swipe-hint')){
      var h = document.createElement('div');
      h.className = 'wa-swipe-hint';
      h.innerHTML = '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M9 14l-4-4 4-4M5 10h9a4 4 0 014 4v3"/></svg>';
      active.appendChild(h);
    }
  }, {passive:true});
  function finishReset(){
    if (!active) return;
    active.style.transform = '';
    active.classList.remove('wa-swiping');
    var hint = active.querySelector('.wa-swipe-hint'); if (hint) hint.remove();
  }
  msgs.addEventListener('touchend', function(){
    if (!active) { start = null; return; }
    var m = /translateX\(([\d.]+)px\)/.exec(active.style.transform);
    var d = m ? parseFloat(m[1]) : 0;
    finishReset();
    if (d > 55){
      var id = active.dataset.id;
      var senderEl = active.querySelector('.wa-sender');
      var name = senderEl ? senderEl.textContent.trim() : 'رسالة';
      var textEl = active.querySelector('.wa-text');
      var text = textEl ? textEl.textContent.trim()
                        : (active.querySelector('.wa-img') ? '🖼️ صورة'
                          : (active.querySelector('audio') ? '🎤 رسالة صوتية' : ''));
      setReply(id, name, text);
    }
    start = null; active = null;
  });

  // --------- منشن (Autocomplete) — يشتغل في الجروب وفي الدردشة الخاصة ---------
  var textInput = document.getElementById('textInput');
  var composer  = document.getElementById('composer');
  if (textInput && composer){
    var isGroup = window.location.pathname.indexOf('/group') === 0;
    // في الدردشة الخاصة: نجيب قائمة المستخدمين مرة واحدة
    if (!isGroup && !window.__GroupMembers){
      fetch('/group/members', {credentials:'same-origin'})
        .then(function(r){ return r.json(); })
        .then(function(d){ window.__GroupMembers = (d.members || []); })
        .catch(function(){});
    }
    var pop = null, popItems = [], popIdx = 0, popStart = -1;
    function ensurePop(){
      if (pop) return pop;
      pop = document.createElement('div');
      pop.className = 'wa-mention-pop';
      pop.style.display = 'none';
      pop.style.position = 'fixed';
      document.body.appendChild(pop);
      return pop;
    }
    function positionPop(){
      if (!pop || pop.style.display === 'none') return;
      var r = composer.getBoundingClientRect();
      pop.style.left = r.left + 'px';
      pop.style.width = r.width + 'px';
      pop.style.bottom = (window.innerHeight - r.top + 6) + 'px';
    }
    function ensureMembers(cb){
      if (window.__GroupMembers && window.__GroupMembers.length){ cb(); return; }
      fetch('/group/members', {credentials:'same-origin'})
        .then(function(r){ return r.json(); })
        .then(function(d){ window.__GroupMembers = (d.members || []); cb(); })
        .catch(function(){ cb(); });
    }
    function hidePop(){ if (pop){ pop.style.display='none'; pop.innerHTML=''; } popItems=[]; popStart=-1; }
    function render(){
      if (!pop || !popItems.length){ hidePop(); return; }
      pop.innerHTML = popItems.map(function(m,i){
        var av = m.avatar
          ? '<img class="wmp-av" src="'+m.avatar+'" alt="">'
          : '<div class="wmp-av wmp-av-fb" style="background:hsl('+((m.id||0)*47%360)+',60%,45%)">'+esc((m.full_name||'?').charAt(0))+'</div>';
        return '<div class="wa-mention-pop-item'+(i===popIdx?' is-active':'')+'" data-i="'+i+'">'
              +  av + '<span class="wmp-name">' + esc(m.full_name) + '</span>'
              +'</div>';
      }).join('');
      pop.style.display = 'block'; positionPop();
      Array.from(pop.querySelectorAll('.wa-mention-pop-item')).forEach(function(el){
        el.addEventListener('mousedown', function(ev){
          ev.preventDefault();
          insertMention(popItems[parseInt(el.dataset.i,10)]);
        });
        el.addEventListener('touchstart', function(ev){
          ev.preventDefault();
          insertMention(popItems[parseInt(el.dataset.i,10)]);
        }, {passive:false});
      });
    }
    function insertMention(m){
      if (!m) return;
      var v = textInput.value;
      var before = v.slice(0, popStart);
      var after  = v.slice(textInput.selectionStart);
      textInput.value = before + '@' + m.full_name + ' ' + after;
      var pos = (before + '@' + m.full_name + ' ').length;
      textInput.setSelectionRange(pos, pos);
      hidePop();
      textInput.focus();
    }
    textInput.addEventListener('input', function(){
      var v = textInput.value, pos = textInput.selectionStart;
      var upto = v.slice(0, pos);
      var atMatch = /@([^\s@]{0,20})$/.exec(upto);
      if (!atMatch){ hidePop(); return; }
      if (!window.__GroupMembers){ ensureMembers(function(){ textInput.dispatchEvent(new Event('input')); }); return; }
      popStart = pos - atMatch[0].length;
      var q = (atMatch[1] || '').toLowerCase();
      popItems = window.__GroupMembers.filter(function(m){
        return m && m.full_name && m.full_name.toLowerCase().indexOf(q) !== -1;
      }).slice(0, 6);
      popIdx = 0;
      ensurePop(); render();
    });
    textInput.addEventListener('keydown', function(e){
      if (!pop || pop.style.display === 'none' || !popItems.length) return;
      if (e.key === 'ArrowDown'){ popIdx = (popIdx+1)%popItems.length; render(); e.preventDefault(); }
      else if (e.key === 'ArrowUp'){ popIdx = (popIdx-1+popItems.length)%popItems.length; render(); e.preventDefault(); }
      else if (e.key === 'Enter' || e.key === 'Tab'){ insertMention(popItems[popIdx]); e.preventDefault(); }
      else if (e.key === 'Escape'){ hidePop(); }
    });
    textInput.addEventListener('blur', function(){ setTimeout(hidePop, 150); });
  }
})();

// (mention popup repositioning handled inline via positionPop)
