/* app-ui.js — نظام التنبيهات والحوارات الموحّد: appAlert / appToast / appConfirm */
(function () {
  'use strict';

  var wrap        = document.getElementById('appToastWrap');
  var modal       = document.getElementById('appModalRoot');
  if (!wrap || !modal) return;
  var modalIc     = document.getElementById('appModalIc');
  var modalTitle  = document.getElementById('appModalTitle');
  var modalSub    = document.getElementById('appModalSub');
  var modalOk     = document.getElementById('appModalOk');
  var modalCancel = document.getElementById('appModalCancel');
  var currentResolve = null;

  var ICONS = {
    info:    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 8h.01"/><path d="M11 12h1v5h1"/></svg>',
    success: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M8 12.5l2.8 2.8L16 9.8"/></svg>',
    error:   '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M15 9l-6 6M9 9l6 6"/></svg>',
    warning: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l10 18H2L12 3z"/><path d="M12 10v5"/><path d="M12 18h.01"/></svg>'
  };
  var CLOSE_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18"/></svg>';

  function makeToast(text, kind) {
    kind = kind || 'info';
    if (!ICONS[kind]) kind = 'info';
    var t = document.createElement('div');
    t.className = 'app-toast is-' + kind;
    t.innerHTML = '<span class="at-ic">' + ICONS[kind] + '</span>' +
                  '<span>' + String(text) + '</span>' +
                  '<button type="button" class="at-close" aria-label="إغلاق">' + CLOSE_SVG + '</button>';
    var closeBtn = t.querySelector('.at-close');
    var timer;
    function dismiss() {
      clearTimeout(timer);
      t.classList.remove('is-show');
      t.classList.add('is-hide');
      setTimeout(function () { if (t.parentNode) t.remove(); }, 320);
    }
    closeBtn.addEventListener('click', dismiss);
    wrap.appendChild(t);
    requestAnimationFrame(function () { t.classList.add('is-show'); });
    timer = setTimeout(dismiss, 2800);
    try { if (navigator.vibrate) navigator.vibrate(kind === 'error' ? [40, 60, 40] : 18); } catch (_) {}
    return dismiss;
  }

  window.appAlert = function (text, kind) { return makeToast(text, kind); };
  window.appToast = function (text, kind) { return makeToast(text, kind || 'success'); };

  function openModal(opts) {
    modalTitle.textContent = opts.title || 'تأكيد';
    modalSub.textContent = opts.sub || '';
    var kind = opts.danger ? 'error' : (opts.kind || 'info');
    modalIc.className = 'app-modal-ic' + (opts.danger ? ' is-danger' : (kind === 'success' ? ' is-success' : ''));
    modalIc.innerHTML = ICONS[kind] || ICONS.info;
    modalOk.textContent = opts.okText || 'تأكيد';
    modalCancel.textContent = opts.cancelText || 'إلغاء';
    modalOk.className = 'btn ' + (opts.danger ? 'btn-danger' : 'btn-primary');
    modalCancel.style.display = opts.hideCancel ? 'none' : '';
    modal.classList.add('is-open');
    modal.setAttribute('aria-hidden', 'false');
  }
  function closeModal(v) {
    modal.classList.remove('is-open');
    modal.setAttribute('aria-hidden', 'true');
    if (currentResolve) { currentResolve(v); currentResolve = null; }
  }

  window.appConfirm = function (text, opts) {
    opts = opts || {};
    return new Promise(function (resolve) {
      currentResolve = resolve;
      openModal({
        title: opts.title || 'تأكيد', sub: text, danger: opts.danger, kind: opts.kind,
        okText: opts.okText || 'تأكيد', cancelText: opts.cancelText || 'إلغاء',
        hideCancel: opts.hideCancel
      });
    });
  };

  modalOk.addEventListener('click', function () { closeModal(true); });
  modal.querySelectorAll('[data-app-close]').forEach(function (el) {
    el.addEventListener('click', function () { closeModal(false); });
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && modal.classList.contains('is-open')) closeModal(false);
  });
})();
