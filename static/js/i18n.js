// static/js/i18n.js — ArgoDesk lightweight i18n (no framework, no build step).
//
// Two complementary mechanisms:
//   1. Keyed translations via data-i18n / data-i18n-title / data-i18n-placeholder
//      attributes (precise, for elements we explicitly tagged).
//   2. A runtime English→target *phrase dictionary* (locales/dict.<locale>.json)
//      applied to text nodes + title/placeholder across the DOM, plus a
//      MutationObserver so JS-rendered content (toasts, modals, dynamic
//      buttons) gets translated as it appears — without tagging every element.
//
// Safety: the dictionary only replaces EXACT, whole-string matches of known UI
// phrases. Arbitrary user/AI/chat text never matches, so it is left untouched.
// Inputs, code, scripts and [data-no-i18n] subtrees are skipped.
//
// English ("en") is the source language: when active, no dictionary runs.
(function (global) {
  'use strict';
  var STORAGE_KEY = 'argodesk-locale';
  var DEFAULT_LOCALE = 'it';
  var SUPPORTED = ['it', 'en'];

  var _catalogs = {};   // locale -> { key: value }   (keyed translations)
  var _dicts = {};      // locale -> { englishPhrase: translated }  (runtime dict)
  var _locale = DEFAULT_LOCALE;
  var _observer = null;

  // Elements whose text/subtree must never be auto-translated.
  var SKIP_TAGS = { SCRIPT: 1, STYLE: 1, NOSCRIPT: 1, TEXTAREA: 1, INPUT: 1,
                    CODE: 1, PRE: 1, KBD: 1, SAMP: 1, SVG: 1, PATH: 1 };
  // Big/user-content containers skipped for safety + performance.
  var SKIP_IDS = { 'chat-history': 1, 'message': 1, 'welcome-tip': 1 };

  function getLocale() {
    try {
      var v = localStorage.getItem(STORAGE_KEY);
      if (v && SUPPORTED.indexOf(v) !== -1) return v;
    } catch (_) {}
    return DEFAULT_LOCALE;
  }

  async function _loadJSON(url) {
    try {
      var res = await fetch(url, { credentials: 'same-origin' });
      return res.ok ? await res.json() : {};
    } catch (_) { return {}; }
  }

  async function _loadCatalog(locale) {
    if (!_catalogs[locale]) _catalogs[locale] = await _loadJSON('/static/locales/' + locale + '.json');
    return _catalogs[locale];
  }

  async function _loadDict(locale) {
    if (locale === 'en') return {};
    if (!_dicts[locale]) _dicts[locale] = await _loadJSON('/static/locales/dict.' + locale + '.json');
    return _dicts[locale];
  }

  // Runtime phrase-dictionary + global MutationObserver are DISABLED: applying
  // the dict across the whole DOM and re-walking every mutation froze the
  // browser on the Email view (heavy, frequently-mutating subtree). Keyed
  // (data-i18n*) translations are unaffected and still localize the UI chrome.
  // Re-enable only once the observer is reworked to be safe (scoped, debounced,
  // re-entrancy-guarded, Email subtree skipped). One-line switch:
  var RUNTIME_DICT_ENABLED = false;

  async function init(locale) {
    _locale = locale || getLocale();
    await _loadCatalog(_locale);
    if (_locale !== 'en') { await _loadCatalog('en'); if (RUNTIME_DICT_ENABLED) await _loadDict(_locale); }
    try { document.documentElement.setAttribute('lang', _locale); } catch (_) {}
    return _locale;
  }

  function t(key, fallback) {
    var cur = _catalogs[_locale] || {};
    if (cur[key] != null) return cur[key];
    var en = _catalogs['en'] || {};
    if (en[key] != null) return en[key];
    return fallback != null ? fallback : key;
  }

  // ── Keyed (data-i18n*) application ──
  function applyKeyed(root) {
    root = root || document;
    if (root.querySelectorAll) {
      root.querySelectorAll('[data-i18n]').forEach(function (e) {
        var v = t(e.getAttribute('data-i18n'), e.textContent); if (v != null) e.textContent = v;
      });
      root.querySelectorAll('[data-i18n-placeholder]').forEach(function (e) {
        e.setAttribute('placeholder', t(e.getAttribute('data-i18n-placeholder'), e.getAttribute('placeholder') || ''));
      });
      root.querySelectorAll('[data-i18n-title]').forEach(function (e) {
        e.setAttribute('title', t(e.getAttribute('data-i18n-title'), e.getAttribute('title') || ''));
      });
    }
  }

  // ── Dictionary (phrase) application ──
  function _skip(node) {
    var el = node.nodeType === 3 ? node.parentNode : node;
    while (el && el.nodeType === 1) {
      if (SKIP_TAGS[el.tagName]) return true;
      if (el.id && SKIP_IDS[el.id]) return true;
      if (el.getAttribute && el.getAttribute('data-no-i18n') != null) return true;
      if (el.isContentEditable) return true;
      el = el.parentNode;
    }
    return false;
  }

  function _translateTextNodes(root, dict) {
    if (!root || (root.nodeType !== 1 && root.nodeType !== 3)) return;
    if (root.nodeType === 3) {
      if (_skip(root)) return;
      var key = root.nodeValue.trim();
      if (key && dict[key]) root.nodeValue = root.nodeValue.replace(key, dict[key]);
      return;
    }
    if (_skip(root)) return;
    var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null);
    var batch = [], n;
    while ((n = walker.nextNode())) batch.push(n);
    batch.forEach(function (tn) {
      if (_skip(tn)) return;
      var k = tn.nodeValue.trim();
      if (k && dict[k]) tn.nodeValue = tn.nodeValue.replace(k, dict[k]);
    });
  }

  function _translateAttrs(root, dict) {
    if (!root.querySelectorAll) return;
    root.querySelectorAll('[title]').forEach(function (e) {
      var k = (e.getAttribute('title') || '').trim();
      if (k && dict[k]) e.setAttribute('title', dict[k]);
    });
    root.querySelectorAll('[placeholder]').forEach(function (e) {
      if (e.tagName === 'INPUT' || e.tagName === 'TEXTAREA') {
        var k = (e.getAttribute('placeholder') || '').trim();
        if (k && dict[k]) e.setAttribute('placeholder', dict[k]);
      }
    });
  }

  function applyDict(root) {
    if (_locale === 'en') return;
    var dict = _dicts[_locale];
    if (!dict || !Object.keys(dict).length) return;
    root = root || document.body;
    if (!root) return;
    _translateTextNodes(root, dict);
    _translateAttrs(root, dict);
  }

  function _startObserver() {
    if (_observer || _locale === 'en') return;
    var dict = _dicts[_locale];
    if (!dict || !Object.keys(dict).length) return;
    _observer = new MutationObserver(function (muts) {
      for (var i = 0; i < muts.length; i++) {
        var m = muts[i];
        if (m.type === 'childList') {
          m.addedNodes.forEach(function (node) {
            if (node.nodeType === 1) { _translateTextNodes(node, dict); _translateAttrs(node, dict); }
            else if (node.nodeType === 3) { _translateTextNodes(node, dict); }
          });
        } else if (m.type === 'characterData' && m.target.nodeType === 3) {
          if (!_skip(m.target)) {
            var k = m.target.nodeValue.trim();
            if (k && dict[k]) m.target.nodeValue = m.target.nodeValue.replace(k, dict[k]);
          }
        }
      }
    });
    try {
      _observer.observe(document.body, { childList: true, subtree: true, characterData: true });
    } catch (_) {}
  }

  function apply(root) {
    applyKeyed(root);
    applyDict(root || document.body);
    _startObserver();
  }

  async function setLocale(locale) {
    if (SUPPORTED.indexOf(locale) === -1) return;
    try { localStorage.setItem(STORAGE_KEY, locale); } catch (_) {}
    // Switching language live is simplest (and safest) with a reload, since the
    // dictionary replaced text in place. Persist first, then reload.
    location.reload();
  }

  global.ArgoI18n = {
    init: init, t: t, apply: apply, applyKeyed: applyKeyed, applyDict: applyDict,
    setLocale: setLocale, getLocale: getLocale,
    SUPPORTED: SUPPORTED, DEFAULT_LOCALE: DEFAULT_LOCALE,
  };
})(window);
