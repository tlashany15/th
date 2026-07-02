/* Voice Call — WebRTC mesh + HTTP long-polling signaling
   Works for both group and dm scopes. Compatible with Vercel (no WebSockets). */
(function(){
  var ICE = { iceServers: [
    { urls: ["stun:stun.l.google.com:19302", "stun:stun1.l.google.com:19302"] }
  ]};

  var state = null; // set on init

  function el(tag, cls, html){
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html !== undefined) e.innerHTML = html;
    return e;
  }
  function fdOf(obj){
    var f = new FormData();
    Object.keys(obj).forEach(function(k){ if (obj[k] !== undefined && obj[k] !== null) f.append(k, obj[k]); });
    return f;
  }
  function apost(url, data){
    return fetch(url, { method:'POST', body: fdOf(data||{}) }).then(function(r){ return r.json().catch(function(){ return {}; }); });
  }
  function aget(url){
    return fetch(url).then(function(r){ return r.json().catch(function(){ return {}; }); });
  }

  function renderBanner(){
    if (!state) return;
    var b = state.opts.bannerEl;
    if (!b) return;
    if (!state.callId) { b.hidden = true; b.innerHTML=''; return; }
    b.hidden = false;
    var meIn = !!state.joined;
    var isStarter = !!state.iStarted;
    var partsHTML = state.participants.map(function(p){
      var avatar = p.avatar
        ? '<img src="'+p.avatar+'" alt="">'
        : '<div class="vc-av-fb">'+(p.name||'?').charAt(0)+'</div>';
      return '<div class="vc-av" title="'+(p.name||'')+'">'+avatar+'</div>';
    }).join('');
    var title = state.opts.scope === 'group' ? 'مكالمة الجروب' : 'مكالمة صوتية';
    var subtitle = (state.startedByName ? ('بدأها: ' + state.startedByName) : '') +
                   ' • ' + state.participants.length + ' متصل';
    var actions = '';
    if (!meIn) {
      actions += '<button class="vc-btn vc-btn-join" id="vcJoinBtn">'+
                 '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M20 10.5V7a2 2 0 00-2-2H6a2 2 0 00-2 2v10a2 2 0 002 2h12a2 2 0 002-2v-3.5l4 3.5v-10z"/></svg>'+
                 '<span>انضم</span></button>';
    } else {
      actions += '<button class="vc-btn vc-btn-mute" id="vcMuteBtn">'+
                 (state.muted
                   ? '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M4.27 3L21 19.73 19.73 21l-3.02-3.02A6.94 6.94 0 0113 18.92V22h-2v-3.08A7 7 0 015 12H3a9 9 0 002.29 6.02L3 20.27 4.27 19 3 17.73 4.27 3z"/></svg>'
                   : '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 14a3 3 0 003-3V5a3 3 0 10-6 0v6a3 3 0 003 3zm5-3a5 5 0 01-10 0H5a7 7 0 006 6.92V21h2v-3.08A7 7 0 0019 11h-2z"/></svg>')+
                 '<span>'+(state.muted?'مكتوم':'مايك')+'</span></button>';
      actions += '<button class="vc-btn vc-btn-leave" id="vcLeaveBtn">'+
                 '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 9a11.6 11.6 0 00-8 3l-4-4 4-4a16 16 0 0116 0l4 4-4 4a11.6 11.6 0 00-8-3z"/></svg>'+
                 '<span>مغادرة</span></button>';
    }
    if ((meIn || isStarter || state.opts.isAdmin) && state.opts.scope === 'group') {
      actions += '<button class="vc-btn vc-btn-end" id="vcEndBtn" title="إنهاء المكالمة للجميع">'+
                 '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M6 6l12 12M18 6L6 18" stroke="currentColor" stroke-width="2.6" fill="none" stroke-linecap="round"/></svg>'+
                 '</button>';
    }

    b.innerHTML =
      '<div class="vc-bar">'+
        '<div class="vc-left">'+
          '<span class="vc-pulse"></span>'+
          '<div class="vc-info">'+
            '<div class="vc-title">'+title+'</div>'+
            '<div class="vc-sub">'+subtitle+'</div>'+
          '</div>'+
        '</div>'+
        '<div class="vc-mid">'+partsHTML+'</div>'+
        '<div class="vc-actions">'+actions+'</div>'+
      '</div>';

    var j = document.getElementById('vcJoinBtn');
    if (j) j.addEventListener('click', join);
    var l = document.getElementById('vcLeaveBtn');
    if (l) l.addEventListener('click', function(){ leave(false); });
    var m = document.getElementById('vcMuteBtn');
    if (m) m.addEventListener('click', toggleMute);
    var e = document.getElementById('vcEndBtn');
    if (e) e.addEventListener('click', function(){
      (window.appConfirm?window.appConfirm('إنهاء المكالمة للجميع؟',{danger:true,okText:'إنهاء'}):Promise.resolve(confirm('إنهاء المكالمة؟')))
        .then(function(ok){ if(ok) endCall(); });
    });
  }

  function toggleMute(){
    state.muted = !state.muted;
    if (state.localStream) {
      state.localStream.getAudioTracks().forEach(function(t){ t.enabled = !state.muted; });
    }
    renderBanner();
  }

  function stateArgs(){
    var q = 'scope='+encodeURIComponent(state.opts.scope);
    if (state.opts.scope === 'dm') q += '&peer=' + encodeURIComponent(state.opts.peerId);
    return q;
  }

  function pollState(){
    aget('/call/state?'+stateArgs()).then(function(d){
      if (!d) return;
      if (!d.active) {
        // Call ended remotely
        if (state.joined) leaveLocal();
        state.callId = null;
        state.participants = [];
        state.startedByName = '';
        state.iStarted = false;
        renderBanner();
        return;
      }
      state.callId = d.call_id;
      state.participants = d.participants || [];
      state.startedByName = d.started_by || '';
      renderBanner();
      // Establish peer connections for any new participant if we're joined
      if (state.joined) {
        state.participants.forEach(function(p){
          if (p.id === state.opts.meId) return;
          if (!state.peers[p.id]) createPeer(p.id, p.id > state.opts.meId /* higher id calls */);
        });
        // Remove peers who left
        Object.keys(state.peers).forEach(function(pid){
          if (!state.participants.some(function(p){ return String(p.id) === String(pid); })) {
            closePeer(parseInt(pid,10));
          }
        });
      }
    }).catch(function(){});
  }

  function pollSignals(){
    if (!state.callId || !state.joined) return;
    aget('/call/signal/poll?call_id='+state.callId+'&since='+state.lastSignalId).then(function(d){
      if (!d || !d.signals) return;
      d.signals.forEach(function(s){
        state.lastSignalId = Math.max(state.lastSignalId, s.id);
        var payload;
        try { payload = JSON.parse(s.payload); } catch(e){ return; }
        handleSignal(s.from, payload);
      });
    }).catch(function(){});
  }

  function sendSignal(toUser, payload){
    apost('/call/signal/send', { call_id: state.callId, to: toUser, payload: JSON.stringify(payload) });
  }

  function ensurePeerAudioEl(fromId){
    var a = document.getElementById('vcAudio_'+fromId);
    if (a) return a;
    a = document.createElement('audio');
    a.id = 'vcAudio_'+fromId;
    a.autoplay = true;
    a.playsInline = true;
    document.body.appendChild(a);
    return a;
  }

  function createPeer(remoteId, isOfferer){
    if (state.peers[remoteId]) return state.peers[remoteId];
    var pc = new RTCPeerConnection(ICE);
    state.peers[remoteId] = pc;
    if (state.localStream) {
      state.localStream.getTracks().forEach(function(t){ pc.addTrack(t, state.localStream); });
    }
    pc.onicecandidate = function(ev){
      if (ev.candidate) sendSignal(remoteId, { type:'ice', candidate: ev.candidate });
    };
    pc.ontrack = function(ev){
      var a = ensurePeerAudioEl(remoteId);
      a.srcObject = ev.streams[0];
    };
    pc.onconnectionstatechange = function(){
      if (pc.connectionState === 'failed' || pc.connectionState === 'closed') {
        closePeer(remoteId);
      }
    };
    if (isOfferer) {
      pc.createOffer().then(function(o){ return pc.setLocalDescription(o); })
        .then(function(){ sendSignal(remoteId, { type:'offer', sdp: pc.localDescription }); });
    }
    return pc;
  }

  function closePeer(remoteId){
    var pc = state.peers[remoteId];
    if (pc) { try{ pc.close(); }catch(e){} delete state.peers[remoteId]; }
    var a = document.getElementById('vcAudio_'+remoteId);
    if (a) a.remove();
  }

  function handleSignal(fromId, payload){
    var pc = state.peers[fromId];
    if (!pc && payload.type === 'offer') pc = createPeer(fromId, false);
    if (!pc) return;
    if (payload.type === 'offer') {
      pc.setRemoteDescription(new RTCSessionDescription(payload.sdp))
        .then(function(){ return pc.createAnswer(); })
        .then(function(a){ return pc.setLocalDescription(a); })
        .then(function(){ sendSignal(fromId, { type:'answer', sdp: pc.localDescription }); });
    } else if (payload.type === 'answer') {
      pc.setRemoteDescription(new RTCSessionDescription(payload.sdp)).catch(function(){});
    } else if (payload.type === 'ice' && payload.candidate) {
      pc.addIceCandidate(new RTCIceCandidate(payload.candidate)).catch(function(){});
    }
  }

  function join(){
    if (state.joined) return;
    navigator.mediaDevices.getUserMedia({ audio:true, video:false }).then(function(stream){
      state.localStream = stream;
      state.muted = false;
      return apost('/call/join', { scope: state.opts.scope, peer: state.opts.peerId || '' });
    }).then(function(d){
      if (!d || !d.ok) throw new Error('join_failed');
      state.callId = d.call_id;
      state.joined = true;
      state.iStarted = !!d.created;
      // Trigger a state poll now
      pollState();
      // Start heartbeat + signal poll
      if (!state.hbTimer) state.hbTimer = setInterval(function(){
        if (state.callId) apost('/call/heartbeat', { call_id: state.callId });
      }, 10000);
      if (!state.sigTimer) state.sigTimer = setInterval(pollSignals, 1500);
      renderBanner();
    }).catch(function(err){
      (window.appAlert||alert)('تعذّر فتح المايك — تأكد إنك سمحت للتطبيق','error');
    });
  }

  function leaveLocal(){
    Object.keys(state.peers).forEach(function(pid){ closePeer(parseInt(pid,10)); });
    if (state.localStream) { state.localStream.getTracks().forEach(function(t){ t.stop(); }); state.localStream = null; }
    if (state.hbTimer) { clearInterval(state.hbTimer); state.hbTimer = null; }
    if (state.sigTimer) { clearInterval(state.sigTimer); state.sigTimer = null; }
    state.joined = false;
    state.muted = false;
    state.iStarted = false;
    state.lastSignalId = 0;
  }

  function leave(silent){
    var cid = state.callId;
    leaveLocal();
    if (cid) apost('/call/leave', { call_id: cid });
    if (!silent) renderBanner();
  }

  function endCall(){
    if (!state.callId) return;
    apost('/call/end', { call_id: state.callId }).then(function(){
      leaveLocal();
      state.callId = null;
      state.participants = [];
      renderBanner();
    });
  }

  function init(opts){
    state = {
      opts: opts,
      callId: null,
      joined: false,
      iStarted: false,
      muted: false,
      localStream: null,
      participants: [],
      startedByName: '',
      peers: {},
      lastSignalId: 0,
      hbTimer: null,
      sigTimer: null,
    };
    if (opts.startBtn) {
      opts.startBtn.addEventListener('click', function(){
        if (state.joined) return;
        if (state.callId) { join(); return; }
        join();
      });
    }
    pollState();
    setInterval(pollState, 4000);
    window.addEventListener('beforeunload', function(){
      if (state.joined && state.callId) {
        try {
          navigator.sendBeacon('/call/leave', fdOf({ call_id: state.callId }));
        } catch(e){}
      }
    });
  }

  window.VoiceCall = { init: init };
})();
