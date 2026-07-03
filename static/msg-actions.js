/* msg-actions.js — قائمة تفاعلات (ضغط مطوّل) + رسم التفاعلات
   يعمل داخل صفحات الدردشة (يحتوي #msgs). يعتمد على window.__MsgReactionsScope
   المضبوطة من صفحة الشات: 'chat' مع otherId أو 'group'.
*/
(function(){
  if (!document.getElementById('msgs')) return;

  var EMOJIS = ['👍','❤️','😂','😮','😢','🙏'];

  function esc(s){ var d=document.createElement('div'); d.textContent=s||''; return d.innerHTML; }

  function reactEndpoint(msgId){
    var scope = window.__MsgReactionsScope || {};
    if (scope.type === 'chat' && scope.otherId){
      return '/chat/' + scope.otherId + '/react/' + msgId;
    }
    if (scope.type === 'group'){
      return '/group/react/' + msgId;
    }
    return null;
  }

  // ====== رسم التفاعلات على فقاعة ======
  function renderReactionsInto(bubble, reactions){
    if (!bubble) return;
    var box = bubble.querySelector('.wa-reactions');
    if (!reactions || !reactions.length){
      if (box) box.remove();
      bubble.classList.remove('has-reactions');
      return;
    }
    bubble.classList.add('has-reactions');
    if (!box){
      box = document.createElement('div');
      box.className = 'wa-reactions';
      // نحطها قبل .wa-meta عشان تظهر أسفل النص فوق الوقت
      var meta = bubble.querySelector('.wa-meta');
      if (meta) bubble.insertBefore(box, meta);
      else bubble.appendChild(box);
    }
    box.innerHTML = reactions.map(function(r){
      return '<button type="button" class="wa-react-chip'+(r.mine?' is-mine':'')+'" data-emoji="'+esc(r.emoji)+'">'
           +   '<span class="wa-react-e">'+esc(r.emoji)+'</span>'
           +   '<span class="wa-react-c">'+(r.count>1?r.count:'')+'</span>'
           + '</button>';
    }).join('');
    Array.from(box.querySelectorAll('.wa-react-chip')).forEach(function(chip){
      chip.addEventListener('click', function(ev){
        ev.stopPropagation();
        var msgEl = bubble.closest('.wa-msg');
        var mid = msgEl && msgEl.dataset.id;
        if (!mid) return;
        toggleReaction(mid, chip.dataset.emoji);
      });
    });
  }

  window.__renderReactions = function(msgId, reactions){
    var el = document.querySelector('.wa-msg[data-id="'+msgId+'"] .wa-bubble');
    if (el) renderReactionsInto(el, reactions);
  };

  window.__applyReactionsUpdates = function(updates){
    if (!updates) return;
    Object.keys(updates).forEach(function(k){
      window.__renderReactions(k, updates[k]);
    });
  };

  // ====== إرسال التفاعل ======
  function toggleReaction(msgId, emoji){
    var url = reactEndpoint(msgId); if (!url) return;
    var fd = new FormData(); fd.append('emoji', emoji);
    fetch(url, {method:'POST', body:fd, credentials:'same-origin'})
      .then(function(r){ return r.json(); })
      .then(function(d){
        if (d && d.ok) window.__renderReactions(msgId, d.reactions || []);
      })
      .catch(function(){});
  }

  // ====== قائمة التفاعلات الطافية ======
  var picker = null, pickerFor = null;
  function ensurePicker(){
    if (picker) return picker;
    picker = document.createElement('div');
    picker.className = 'wa-react-picker';
    picker.innerHTML = EMOJIS.map(function(e){
      return '<button type="button" class="wa-react-pick-btn" data-emoji="'+esc(e)+'">'+esc(e)+'</button>';
    }).join('');
    document.body.appendChild(picker);
    picker.addEventListener('click', function(ev){
      var b = ev.target.closest('.wa-react-pick-btn'); if (!b) return;
      ev.stopPropagation();
      if (pickerFor) toggleReaction(pickerFor, b.dataset.emoji);
      hidePicker();
    });
    return picker;
  }
  function hidePicker(){
    if (picker){ picker.classList.remove('is-open'); picker.style.display='none'; }
    pickerFor = null;
  }
  function showPicker(msgEl){
    var mid = msgEl.dataset.id; if (!mid) return;
    ensurePicker();
    pickerFor = mid;
    picker.style.display = 'flex';
    // احسب الموضع فوق الفقاعة
    var bubble = msgEl.querySelector('.wa-bubble') || msgEl;
    var r = bubble.getBoundingClientRect();
    picker.style.visibility = 'hidden';
    picker.classList.add('is-open');
    // انتظر لبعد الرندر عشان نقيس مقاسه
    requestAnimationFrame(function(){
      var pw = picker.offsetWidth, ph = picker.offsetHeight;
      var top = r.top - ph - 8;
      if (top < 8) top = r.bottom + 8; // لو مفيش مكان فوق، نحطها تحت
      var left = r.left + (r.width - pw) / 2;
      var vw = window.innerWidth;
      if (left < 8) left = 8;
      if (left + pw > vw - 8) left = vw - pw - 8;
      picker.style.top = (top + window.scrollY) + 'px';
      picker.style.left = left + 'px';
      picker.style.visibility = 'visible';
    });
  }

  // إغلاق عند النقر خارجها أو التمرير
  document.addEventListener('click', function(ev){
    if (!picker || picker.style.display === 'none') return;
    if (ev.target.closest('.wa-react-picker')) return;
    if (ev.target.closest('.wa-msg') && pickerFor &&
        ev.target.closest('.wa-msg').dataset.id === pickerFor) return;
    hidePicker();
  });
  window.addEventListener('scroll', hidePicker, true);
  window.addEventListener('resize', hidePicker);

  // ====== الضغط المطوّل على الرسائل ======
  var msgs = document.getElementById('msgs');
  var pressTimer = null, pressStart = null, longPressed = false, pressTarget = null;

  function clearPress(){
    if (pressTimer){ clearTimeout(pressTimer); pressTimer = null; }
    pressStart = null; pressTarget = null;
  }

  msgs.addEventListener('touchstart', function(e){
    var msgEl = e.target.closest && e.target.closest('.wa-msg');
    if (!msgEl) return;
    // تجاهل الأزرار الداخلية (حذف/رد) والصور
    if (e.target.closest('.wa-del') || e.target.closest('.wa-react-chip')) return;
    var t = e.touches[0];
    pressStart = {x:t.clientX, y:t.clientY};
    pressTarget = msgEl;
    longPressed = false;
    pressTimer = setTimeout(function(){
      longPressed = true;
      try { if (navigator.vibrate) navigator.vibrate(10); } catch(_){}
      showPicker(msgEl);
    }, 380);
  }, {passive:true});

  msgs.addEventListener('touchmove', function(e){
    if (!pressStart) return;
    var t = e.touches[0];
    var dx = Math.abs(t.clientX - pressStart.x);
    var dy = Math.abs(t.clientY - pressStart.y);
    if (dx > 8 || dy > 8) clearPress();
  }, {passive:true});

  msgs.addEventListener('touchend', function(e){
    if (longPressed) { e.preventDefault(); }
    clearPress();
    longPressed = false;
  });
  msgs.addEventListener('touchcancel', clearPress);

  // على الديسكتوب: زر يمين أو Ctrl+Click
  msgs.addEventListener('contextmenu', function(e){
    var msgEl = e.target.closest && e.target.closest('.wa-msg');
    if (!msgEl) return;
    if (e.target.closest('.wa-del') || e.target.closest('.wa-react-chip')) return;
    e.preventDefault();
    showPicker(msgEl);
  });
})();
