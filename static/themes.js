/* Theme picker — WhatsApp/Telegram-style themes for chat surfaces.
   Persists in localStorage("tahsin_chat_theme"). Applied to <html data-chat-theme>. */
(function(){
  var KEY = 'tahsin_chat_theme';
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
  ];

  function getSaved(){
    try { return localStorage.getItem(KEY) || 'default'; } catch(e){ return 'default'; }
  }
  function apply(id){
    var t = THEMES.find(function(x){ return x.id === id; }) || THEMES[0];
    document.documentElement.setAttribute('data-chat-theme', t.id);
    try { localStorage.setItem(KEY, t.id); } catch(e){}
  }
  // Apply immediately (before DOM ready) to avoid flash
  apply(getSaved());

  var SVG_PALETTE = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3a9 9 0 100 18c1.7 0 2-1.4 1-2.4-.8-.8-.3-2.6 1-2.6h2a5 5 0 005-5c0-4.4-4-8-9-8z"/><circle cx="7.5" cy="10.5" r="1.2" fill="currentColor" stroke="none"/><circle cx="12" cy="7.5" r="1.2" fill="currentColor" stroke="none"/><circle cx="16.5" cy="10.5" r="1.2" fill="currentColor" stroke="none"/></svg>';
  var SVG_CHECK   = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5 9-11"/></svg>';
  var SVG_CLOSE   = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 6l12 12M6 18L18 6"/></svg>';

  function buildModal(){
    if (document.getElementById('thModal')) return document.getElementById('thModal');
    var m = document.createElement('div');
    m.id = 'thModal'; m.className = 'th-modal';
    var cards = THEMES.map(function(t){
      var isActive = (t.id === getSaved());
      var previewStyle = 'background:'+t.bg+';';
      return '<button type="button" class="th-card '+(isActive?'is-active':'')+'" data-theme="'+t.id+'">'+
               '<div class="th-card-preview" style="'+previewStyle+'">'+
                 '<div class="th-p-bubble them" style="background:'+t.them+';color:'+t.themText+'">مرحبًا</div>'+
                 '<div class="th-p-bubble me"   style="background:'+t.me+';color:'+t.meText+'">أهلاً!</div>'+
                 '<div class="th-card-check">'+SVG_CHECK+'</div>'+
               '</div>'+
               '<div class="th-card-name">'+t.name+'</div>'+
             '</button>';
    }).join('');
    m.innerHTML =
      '<div class="th-modal-back" data-th-close></div>'+
      '<div class="th-modal-card">'+
        '<div class="th-modal-grip"></div>'+
        '<div class="th-modal-head">'+
          '<div class="th-modal-title">اختر مظهر الدردشة</div>'+
          '<button type="button" class="th-modal-close" data-th-close aria-label="إغلاق">'+SVG_CLOSE+'</button>'+
        '</div>'+
        '<div class="th-grid">'+cards+'</div>'+
      '</div>';
    document.body.appendChild(m);
    m.addEventListener('click', function(ev){
      if (ev.target.closest('[data-th-close]')){ closeModal(); return; }
      var card = ev.target.closest('.th-card');
      if (card){
        var id = card.dataset.theme;
        apply(id);
        m.querySelectorAll('.th-card').forEach(function(c){ c.classList.toggle('is-active', c.dataset.theme === id); });
        setTimeout(closeModal, 180);
      }
    });
    return m;
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
    // Chats list header
    document.querySelectorAll('.tg-chats-head').forEach(function(h){
      if (h.querySelector('.th-theme-btn')) return;
      var b = makeBtn();
      b.style.position = 'absolute';
      b.style.top = '10px';
      b.style.insetInlineEnd = '10px';
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
  // Also expose global toggle for the sidebar link
  window.TahsinTheme = { open: openModal, apply: apply, current: getSaved };
})();
