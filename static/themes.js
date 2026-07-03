/* Theme picker — WhatsApp/Telegram-style themes for chat surfaces.
   Persists in localStorage("tahsin_chat_theme"). Applied to <html data-chat-theme>.
   Also supports a "custom" theme editor (bubbles color + background color/image). */
(function(){
  // Per-account theme storage: keys are namespaced with the current user id so
  // switching accounts on the same device shows each user's own theme.
  var UID = (typeof window !== 'undefined' && window.CURRENT_USER_ID != null)
    ? String(window.CURRENT_USER_ID) : 'guest';
  var KEY = 'tahsin_chat_theme:' + UID;
  var KEY_CUSTOM = 'tahsin_chat_theme_custom:' + UID;

  // One-time migration from the old global keys (only for the first user that logs in).
  try {
    var legacy = localStorage.getItem('tahsin_chat_theme');
    if (legacy && !localStorage.getItem(KEY)) localStorage.setItem(KEY, legacy);
    var legacyC = localStorage.getItem('tahsin_chat_theme_custom');
    if (legacyC && !localStorage.getItem(KEY_CUSTOM)) localStorage.setItem(KEY_CUSTOM, legacyC);
    localStorage.removeItem('tahsin_chat_theme');
    localStorage.removeItem('tahsin_chat_theme_custom');
  } catch(e){}

  var THEMES = [
    { id:'default',  name:'فريق التحصين',  bg:'linear-gradient(180deg,#0b0f17,#141b2d)',  me:'linear-gradient(160deg,#f5b950,#ef6b57)', them:'#202a44', meText:'#1a0e02', themText:'#eef2fb' },
    { id:'wa-dark',  name:'واتساب داكن',    bg:'#0b141a', me:'#005c4b', them:'#202c33', meText:'#e9edef', themText:'#e9edef' },
    { id:'wa-light', name:'واتساب فاتح',    bg:'#efeae2', me:'#d9fdd3', them:'#ffffff', meText:'#111b21', themText:'#111b21' },
    { id:'tg-blue',  name:'تليجرام أزرق',   bg:'linear-gradient(180deg,#0f1c2e,#17324c)', me:'#2b5278', them:'#182533', meText:'#fff', themText:'#fff' },
    { id:'tg-dark',  name:'تليجرام داكن',   bg:'#0e1621', me:'#766ac8', them:'#182533', meText:'#fff', themText:'#fff' },
    { id:'amoled',   name:'أسود AMOLED',    bg:'#000',    me:'linear-gradient(160deg,#f5b950,#ef6b57)', them:'#0e0e0e', meText:'#1a0e02', themText:'#eee' },
    { id:'rose',     name:'وردي',           bg:'linear-gradient(180deg,#2a0f1f,#3d1729)', me:'linear-gradient(160deg,#ff6b9d,#c94b7b)', them:'#4a1e35', meText:'#fff', themText:'#ffe8f0' },
    { id:'ocean',    name:'محيطي',          bg:'linear-gradient(180deg,#062a3d,#0a3d5a)', me:'linear-gradient(160deg,#22d3ee,#0891b2)', them:'#0d485f', meText:'#052732', themText:'#e0f7fa' },
    { id:'forest',   name:'غابة',           bg:'linear-gradient(180deg,#0f2417,#163a24)', me:'linear-gradient(160deg,#4ade80,#16a34a)', them:'#1e4d31', meText:'#062910', themText:'#e6ffed' },
    { id:'sunset',   name:'غروب',           bg:'linear-gradient(180deg,#2d1b4e,#c2185b)', me:'linear-gradient(160deg,#ffb347,#ff6b6b)', them:'#3d1e5c', meText:'#1a0e02', themText:'#ffe5ec' },
    { id:'midnight', name:'منتصف الليل',    bg:'linear-gradient(180deg,#0a0e27,#1a1e4e)', me:'linear-gradient(160deg,#6366f1,#8b5cf6)', them:'#1e1e4e', meText:'#fff', themText:'#e0e7ff' },
    { id:'mocha',    name:'موكا',           bg:'linear-gradient(180deg,#2b1810,#4a2e1c)', me:'linear-gradient(160deg,#d4a574,#8b5a3c)', them:'#3d251a', meText:'#1a0e02', themText:'#f5e6d3' },
    { id:'mint',     name:'نعناع',          bg:'linear-gradient(180deg,#0f2e2a,#1a4d42)', me:'linear-gradient(160deg,#6ee7b7,#10b981)', them:'#1e4d43', meText:'#052e26', themText:'#d1fae5' },
    { id:'custom',   name:'مخصص',           bg:'#111', me:'#2b5278', them:'#182533', meText:'#fff', themText:'#fff', isCustom:true },
  ];

  function getSaved(){ try { return localStorage.getItem(KEY) || 'default'; } catch(e){ return 'default'; } }
  function getCustom(){
    try { return JSON.parse(localStorage.getItem(KEY_CUSTOM) || 'null') || defaultCustom(); }
    catch(e){ return defaultCustom(); }
  }
  function defaultCustom(){
    return { bgColor:'#0e1621', bgImage:'', bgBlur:0, me:'#2b5278', meText:'#ffffff', them:'#182533', themText:'#ffffff' };
  }
  function saveCustom(obj){ try{ localStorage.setItem(KEY_CUSTOM, JSON.stringify(obj)); }catch(e){} }

  function applyCustomStyle(){
    var c = getCustom();
    var blur = Math.max(0, Math.min(30, parseInt(c.bgBlur || 0, 10) || 0));
    var bg = c.bgImage
      ? "url('"+c.bgImage+"') center/cover no-repeat, "+c.bgColor
      : c.bgColor;
    // We render bg on ::before so we can blur ONLY the background layer, not the messages.
    var css =
      'html[data-chat-theme="custom"] .wa-msgs{ background:'+c.bgColor+' !important; position:relative; isolation:isolate; }'+
      'html[data-chat-theme="custom"] .wa-msgs::before{'+
        ' content:""; position:sticky; top:0; left:0;'+
        ' display:block; width:100%; height:100%;'+
        ' margin-bottom:-100%; flex-shrink:0;'+
        ' background:'+bg+';'+
        ' filter: blur('+blur+'px);'+
        ' transform: scale('+(blur>0?1.06:1)+');'+
        ' z-index:0; pointer-events:none;'+
      '}'+
      'html[data-chat-theme="custom"] .wa-msgs > *{ position:relative; z-index:1; }'+
      'html[data-chat-theme="custom"] .wa-head,'+
      'html[data-chat-theme="custom"] .wa-composer{ background:'+c.bgColor+'; border-color:rgba(0,0,0,.3); }'+
      'html[data-chat-theme="custom"] .wa-me .wa-bubble{ background:'+c.me+' !important; color:'+c.meText+' !important; border:none; }'+
      'html[data-chat-theme="custom"] .wa-them .wa-bubble{ background:'+c.them+' !important; color:'+c.themText+' !important; border:none; }'+
      'html[data-chat-theme="custom"] .tg-chats-head{ background:'+c.bgColor+'; }';
    var s = document.getElementById('thCustomStyle');
    if (!s){ s = document.createElement('style'); s.id = 'thCustomStyle'; document.head.appendChild(s); }
    s.textContent = css;
  }

  function apply(id){
    var t = THEMES.find(function(x){ return x.id === id; }) || THEMES[0];
    document.documentElement.setAttribute('data-chat-theme', t.id);
    try { localStorage.setItem(KEY, t.id); } catch(e){}
    if (t.id === 'custom') applyCustomStyle();
  }
  // Apply immediately (before DOM ready) to avoid flash
  applyCustomStyle();
  apply(getSaved());

  var SVG_PALETTE = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3a9 9 0 100 18c1.7 0 2-1.4 1-2.4-.8-.8-.3-2.6 1-2.6h2a5 5 0 005-5c0-4.4-4-8-9-8z"/><circle cx="7.5" cy="10.5" r="1.2" fill="currentColor" stroke="none"/><circle cx="12" cy="7.5" r="1.2" fill="currentColor" stroke="none"/><circle cx="16.5" cy="10.5" r="1.2" fill="currentColor" stroke="none"/></svg>';
  var SVG_CHECK   = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5 9-11"/></svg>';
  var SVG_CLOSE   = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 6l12 12M6 18L18 6"/></svg>';
  var SVG_EDIT    = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 013 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>';

  function cardHTML(t, isActive){
    var c = t.isCustom ? getCustom() : null;
    var bg = t.isCustom ? (c.bgImage ? "url('"+c.bgImage+"') center/cover, "+c.bgColor : c.bgColor) : t.bg;
    var me = t.isCustom ? c.me : t.me;
    var them = t.isCustom ? c.them : t.them;
    var meText = t.isCustom ? c.meText : t.meText;
    var themText = t.isCustom ? c.themText : t.themText;
    return '<button type="button" class="th-card '+(isActive?'is-active':'')+'" data-theme="'+t.id+'">'+
             '<div class="th-card-preview" style="background:'+bg+';">'+
               '<div class="th-p-bubble them" style="background:'+them+';color:'+themText+'">مرحبًا</div>'+
               '<div class="th-p-bubble me"   style="background:'+me+';color:'+meText+'">أهلاً!</div>'+
               '<div class="th-card-check">'+SVG_CHECK+'</div>'+
               (t.isCustom ? '<div class="th-card-edit" data-edit-custom>'+SVG_EDIT+'</div>' : '')+
             '</div>'+
             '<div class="th-card-name">'+t.name+'</div>'+
           '</button>';
  }

  function buildModal(){
    var existing = document.getElementById('thModal');
    if (existing) existing.remove();
    var m = document.createElement('div');
    m.id = 'thModal'; m.className = 'th-modal';
    var saved = getSaved();
    var cards = THEMES.map(function(t){ return cardHTML(t, t.id === saved); }).join('');
    m.innerHTML =
      '<div class="th-modal-back" data-th-close></div>'+
      '<div class="th-modal-card">'+
        '<div class="th-modal-grip"></div>'+
        '<div class="th-modal-head">'+
          '<div class="th-modal-title">اختر مظهر الدردشة</div>'+
          '<button type="button" class="th-modal-close" data-th-close aria-label="إغلاق">'+SVG_CLOSE+'</button>'+
        '</div>'+
        '<div class="th-grid">'+cards+'</div>'+
        buildCustomEditor()+
      '</div>';
    document.body.appendChild(m);
    m.addEventListener('click', function(ev){
      if (ev.target.closest('[data-th-close]')){ closeModal(); return; }
      if (ev.target.closest('[data-edit-custom]')){
        ev.stopPropagation(); ev.preventDefault();
        var ed = m.querySelector('.th-custom-editor');
        ed.classList.add('is-open'); m.classList.add('is-editing');
        return;
      }
      var card = ev.target.closest('.th-card');
      if (card){
        var id = card.dataset.theme;
        apply(id);
        m.querySelectorAll('.th-card').forEach(function(c){ c.classList.toggle('is-active', c.dataset.theme === id); });
        if (id === 'custom'){
          var ed = m.querySelector('.th-custom-editor');
          ed.classList.add('is-open'); m.classList.add('is-editing');
        } else {
          setTimeout(closeModal, 180);
        }
      }
    });
    wireCustomEditor(m);
    return m;
  }

  function buildCustomEditor(){
    var c = getCustom();
    return '<div class="th-custom-editor">'+
      '<div class="th-custom-title">'+
        '<button type="button" class="th-custom-back" data-c-back aria-label="رجوع">'+
          '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 6l-6 6 6 6"/></svg>'+
        '</button>'+
        '<span>تخصيص الثيم</span>'+
      '</div>'+
      '<div class="th-custom-row"><label>لون الخلفية</label><input type="color" data-c="bgColor" value="'+c.bgColor+'"></div>'+
      '<div class="th-custom-row"><label>صورة الخلفية</label>'+
        '<div class="th-custom-imgctrls">'+
          '<label class="th-custom-file"><input type="file" accept="image/*" data-c-file="bgImage" hidden>اختر صورة</label>'+
          '<button type="button" class="th-custom-clear" data-c-clear="bgImage">مسح</button>'+
        '</div></div>'+
      '<div class="th-custom-row"><label>ضبابية الخلفية <span class="th-blur-val" data-blur-val>'+(c.bgBlur||0)+'px</span></label>'+
        '<input type="range" min="0" max="30" step="1" data-c="bgBlur" value="'+(c.bgBlur||0)+'" class="th-custom-range"></div>'+
      '<div class="th-custom-row"><label>لون فقاعتي</label><input type="color" data-c="me" value="'+c.me+'"></div>'+
      '<div class="th-custom-row"><label>لون النص عندي</label><input type="color" data-c="meText" value="'+c.meText+'"></div>'+
      '<div class="th-custom-row"><label>لون فقاعة الآخر</label><input type="color" data-c="them" value="'+c.them+'"></div>'+
      '<div class="th-custom-row"><label>لون نص الآخر</label><input type="color" data-c="themText" value="'+c.themText+'"></div>'+
      '<div class="th-custom-actions">'+
        '<button type="button" class="th-custom-apply" data-c-apply>تطبيق</button>'+
      '</div>'+
    '</div>';
  }

  function wireCustomEditor(m){
    var editor = m.querySelector('.th-custom-editor');
    if (!editor) return;
    editor.addEventListener('input', function(ev){
      var el = ev.target;
      if (el.dataset.c){
        var c = getCustom(); c[el.dataset.c] = el.value; saveCustom(c);
      }
    });
    editor.addEventListener('input', function(ev){ if(ev.target && ev.target.dataset && ev.target.dataset.c==='bgBlur'){ var lbl=editor.querySelector('[data-blur-val]'); if(lbl) lbl.textContent = ev.target.value + 'px'; var c=getCustom(); c.bgBlur=ev.target.value; saveCustom(c); applyCustomStyle(); } });
    editor.addEventListener('change', function(ev){
      var el = ev.target;
      if (el.dataset.cFile){
        var f = el.files && el.files[0]; if (!f) return;
        var reader = new FileReader();
        reader.onload = function(){
          var c = getCustom(); c.bgImage = reader.result; saveCustom(c);
        };
        reader.readAsDataURL(f);
      }
    });
    editor.addEventListener('click', function(ev){
      var clr = ev.target.closest('[data-c-clear]');
      if (clr){
        var key = clr.dataset.cClear;
        var c = getCustom(); c[key] = ''; saveCustom(c);
        return;
      }
      if (ev.target.closest('[data-c-apply]')){
        apply('custom');
        // Refresh custom card preview
        var card = m.querySelector('.th-card[data-theme="custom"]');
        if (card){
          var t = THEMES.find(function(x){return x.id==='custom';});
          card.outerHTML = cardHTML(t, true);
        }
        setTimeout(closeModal, 200);
      }
    });
  }

  function openModal(){ buildModal().classList.add('is-open'); document.body.style.overflow='hidden'; }
  function closeModal(){ var m=document.getElementById('thModal'); if(m){ m.classList.remove('is-open'); } document.body.style.overflow=''; }
  document.addEventListener('keydown', function(e){ if (e.key === 'Escape') closeModal(); });

  function makeBtn(){
    var b = document.createElement('button');
    b.type = 'button';
    b.className = 'th-theme-btn';
    b.title = 'مظهر الدردشة';
    b.setAttribute('aria-label','مظهر الدردشة');
    b.innerHTML = SVG_PALETTE;
    b.addEventListener('click', openModal);
    return b;
  }

  function inject(){
    // 1:1 chat + group header
    document.querySelectorAll('.wa-head').forEach(function(h){
      if (h.querySelector('.th-theme-btn')) return;
      h.appendChild(makeBtn());
    });
    // Chats list header — button on the visual RIGHT (RTL => insetInlineStart)
    document.querySelectorAll('.tg-chats-head').forEach(function(h){
      if (h.querySelector('.th-theme-btn')) return;
      var b = makeBtn();
      b.style.position = 'absolute';
      b.style.top = '10px';
      b.style.insetInlineStart = '10px';
      b.style.zIndex = '3';
      b.style.background = 'rgba(0,0,0,.35)';
      b.style.color = '#fff';
      h.appendChild(b);
    });
  }

  if (document.readyState === 'loading'){
    document.addEventListener('DOMContentLoaded', inject);
  } else {
    inject();
  }
  window.TahsinTheme = { open: openModal, apply: apply, current: getSaved };
})();
