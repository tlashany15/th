/* polish-global.js
 * 1) Force Arabic-Indic digits (٠١٢..٩ / ۰۱۲..۹) to Latin (0-9) everywhere,
 *    including <input>/<textarea> values, on load and on every mutation/input.
 * 2) Insert tatweel (ـ) between connectable Arabic letters in headings
 *    (h1..h5) and buttons/tabs to give a bolder editorial look.
 * Idempotent. Safe under MutationObserver.
 */
(function () {
  'use strict';

  // ---------- Digit normalization ----------
  var DIGIT_MAP = {
    '\u0660': '0', '\u0661': '1', '\u0662': '2', '\u0663': '3', '\u0664': '4',
    '\u0665': '5', '\u0666': '6', '\u0667': '7', '\u0668': '8', '\u0669': '9',
    '\u06F0': '0', '\u06F1': '1', '\u06F2': '2', '\u06F3': '3', '\u06F4': '4',
    '\u06F5': '5', '\u06F6': '6', '\u06F7': '7', '\u06F8': '8', '\u06F9': '9',
    '\u066B': '.', '\u066C': ','
  };
  var DIGIT_RE = /[\u0660-\u0669\u06F0-\u06F9\u066B\u066C]/g;

  function toLatin(str) {
    if (!str) return str;
    if (!DIGIT_RE.test(str)) return str;
    DIGIT_RE.lastIndex = 0;
    return str.replace(DIGIT_RE, function (m) { return DIGIT_MAP[m] || m; });
  }

  // ---------- Tatweel ----------
  // Letters that do NOT connect to the following letter (right-joining only):
  //   ا أ إ آ د ذ ر ز و ؤ ء ة ى (final ya without dots also stops the join)
  var NO_JOIN_AFTER = {
    '\u0621': 1, '\u0622': 1, '\u0623': 1, '\u0624': 1, '\u0625': 1,
    '\u0627': 1, '\u062F': 1, '\u0630': 1, '\u0631': 1, '\u0632': 1,
    '\u0648': 1, '\u0629': 1, '\u0649': 1
  };
  // Hamza standalone doesn't connect from previous either.
  var NO_JOIN_BEFORE = { '\u0621': 1 };

  function isArabicLetter(ch) {
    var c = ch.charCodeAt(0);
    return (c >= 0x0621 && c <= 0x064A);
  }

  function addTatweel(str) {
    if (!str || str.length < 2) return str;
    var out = '';
    for (var i = 0; i < str.length; i++) {
      var a = str[i];
      out += a;
      if (i === str.length - 1) break;
      var b = str[i + 1];
      if (a === '\u0640' || b === '\u0640') continue; // already has tatweel
      if (!isArabicLetter(a) || !isArabicLetter(b)) continue;
      if (NO_JOIN_AFTER[a]) continue;
      if (NO_JOIN_BEFORE[b]) continue;
      out += '\u0640';
    }
    return out;
  }

  var TATWEEL_SELECTOR = 'h1, h2, h3, h4, h5, .ap-title, .ap-eyebrow, .ap-kpi-l, .ap-sc-t, .ap-shortcut-t, .ap-share-t, .ap-closed-t, .btn, button, .tab, .nav-tab, .chip, .badge';

  function shouldSkip(node) {
    // Skip input/textarea/script/style, and inside <code>/<pre>.
    var p = node.parentNode;
    while (p && p.nodeType === 1) {
      var tag = p.tagName;
      if (tag === 'SCRIPT' || tag === 'STYLE' || tag === 'TEXTAREA' || tag === 'CODE' || tag === 'PRE') return true;
      if (p.dataset && p.dataset.noPolish === '1') return true;
      p = p.parentNode;
    }
    return false;
  }

  function walkTextNodes(root, cb) {
    if (!root) return;
    if (root.nodeType === 3) { cb(root); return; }
    if (root.nodeType !== 1) return;
    var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null);
    var n;
    while ((n = walker.nextNode())) cb(n);
  }

  function normalizeDigitsIn(root) {
    walkTextNodes(root, function (n) {
      if (shouldSkip(n)) return;
      var v = n.nodeValue;
      var nv = toLatin(v);
      if (nv !== v) n.nodeValue = nv;
    });
  }

  function tatweelIn(root) {
    if (!root || root.nodeType !== 1) return;
    var els = root.matches && root.matches(TATWEEL_SELECTOR) ? [root] : [];
    var found = root.querySelectorAll ? root.querySelectorAll(TATWEEL_SELECTOR) : [];
    for (var i = 0; i < found.length; i++) els.push(found[i]);
    for (var j = 0; j < els.length; j++) {
      var el = els[j];
      if (!el || el.dataset.tatweel === '1') continue;
      // Only process leaf-ish elements: no complex children (only text/inline).
      var hasBlock = false;
      for (var k = 0; k < el.children.length; k++) {
        var t = el.children[k].tagName;
        if (t === 'DIV' || t === 'SECTION' || t === 'ARTICLE' || t === 'UL' || t === 'OL' || t === 'TABLE') { hasBlock = true; break; }
      }
      if (hasBlock) continue;
      walkTextNodes(el, function (n) {
        var v = n.nodeValue;
        if (!v || !v.trim()) return;
        var nv = addTatweel(toLatin(v));
        if (nv !== v) n.nodeValue = nv;
      });
      el.dataset.tatweel = '1';
    }
  }

  function normalizeInputs(root) {
    var scope = (root && root.querySelectorAll) ? root : document;
    var list = scope.querySelectorAll('input, textarea');
    for (var i = 0; i < list.length; i++) {
      var el = list[i];
      if (el.dataset.digitBound === '1') continue;
      el.dataset.digitBound = '1';
      // Force latin numeric keypad hint where reasonable.
      if (el.tagName === 'INPUT' && !el.hasAttribute('inputmode')) {
        var t = (el.type || '').toLowerCase();
        if (t === 'number' || t === 'tel') el.setAttribute('inputmode', 'numeric');
      }
      // Initial value.
      if (el.value) {
        var nv = toLatin(el.value);
        if (nv !== el.value) el.value = nv;
      }
      // Live.
      el.addEventListener('input', function (e) {
        var t = e.target;
        if (!t || (t.tagName !== 'INPUT' && t.tagName !== 'TEXTAREA')) return;
        var v = t.value;
        var nv = toLatin(v);
        if (nv !== v) {
          var start = null, end = null;
          try { start = t.selectionStart; end = t.selectionEnd; } catch (_) {}
          t.value = nv;
          try { if (start != null) t.setSelectionRange(start, end); } catch (_) {}
        }
      });
    }
  }

  function runAll(root) {
    try { normalizeDigitsIn(root || document.body); } catch (e) {}
    try { tatweelIn(root || document.body); } catch (e) {}
    try { normalizeInputs(root || document); } catch (e) {}
  }

  function boot() {
    runAll(document.body);
    var mo = new MutationObserver(function (muts) {
      for (var i = 0; i < muts.length; i++) {
        var m = muts[i];
        if (m.type === 'childList') {
          for (var j = 0; j < m.addedNodes.length; j++) {
            var n = m.addedNodes[j];
            if (n.nodeType === 1) runAll(n);
            else if (n.nodeType === 3 && !shouldSkip(n)) {
              var nv = toLatin(n.nodeValue);
              if (nv !== n.nodeValue) n.nodeValue = nv;
            }
          }
        } else if (m.type === 'characterData') {
          var t = m.target;
          if (t && t.nodeType === 3 && !shouldSkip(t)) {
            var v = t.nodeValue;
            var nv2 = toLatin(v);
            if (nv2 !== v) t.nodeValue = nv2;
          }
        }
      }
    });
    mo.observe(document.body, { childList: true, subtree: true, characterData: true });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
