/* badge-v14.js — الضغط على شارة التوثيق يفتح نافذة «حساب رسمي» */
(function () {
  var SHIELD =
    '<svg viewBox="0 0 24 24" aria-hidden="true"><g fill="currentColor">' +
    '<rect x="3.6" y="3.6" width="16.8" height="16.8" rx="5.2"/>' +
    '<rect x="3.6" y="3.6" width="16.8" height="16.8" rx="5.2" transform="rotate(45 12 12)"/></g>' +
    '<path d="M8.1 12.4l2.6 2.6 5.2-5.4" fill="none" stroke="#0d121b" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>';

  function openOfficial(title, text) {
    var back = document.createElement('div');
    back.className = 'ofc-back';
    back.innerHTML =
      '<div class="ofc-card" role="dialog" aria-modal="true">' +
      '<div class="ofc-ic">' + SHIELD + '</div>' +
      '<div class="ofc-t"></div>' +
      '<div class="ofc-s"></div>' +
      '<button type="button" class="ofc-btn">تمام</button>' +
      '</div>';
    back.querySelector('.ofc-t').textContent = title;
    back.querySelector('.ofc-s').textContent = text;
    document.body.appendChild(back);
    requestAnimationFrame(function () { back.classList.add('is-in'); });

    function close() {
      back.classList.remove('is-in');
      setTimeout(function () { back.remove(); }, 200);
    }
    back.addEventListener('click', function (e) {
      if (e.target === back || e.target.closest('.ofc-btn')) close();
    });
    document.addEventListener('keydown', function esc(e) {
      if (e.key === 'Escape') { close(); document.removeEventListener('keydown', esc); }
    });
  }

  document.addEventListener('click', function (e) {
    var b = e.target.closest('.verified-badge, .admin-badge');
    if (!b) return;
    e.preventDefault();
    e.stopPropagation();
    if (b.dataset.kind === 'admin') {
      openOfficial(
        'مسؤول معتمد',
        'ده مسؤول معيّن من المسؤول الرئيسي — هو المسؤول عن الرواتب والأعداد.'
      );
    } else if (b.dataset.kind === 'group') {
      openOfficial('مجموعة رسمية', 'دي مجموعة رسمية موثّقة تابعة لإدارة التطبيق.');
    } else {
      openOfficial(
        'حساب رسمي موثّق',
        'ده الحساب الرسمي الخاص بخدمة العمال. أي رسالة جاية منه رسمية من الإدارة.'
      );
    }
  }, true);
})();
