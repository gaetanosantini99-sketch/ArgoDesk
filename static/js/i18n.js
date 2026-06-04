// static/js/i18n.js — ArgoDesk lightweight i18n (no framework, no build step).
//
// Usage:
//   <script src="/static/js/i18n.js"></script>
//   ArgoI18n.init().then(() => ArgoI18n.apply());   // translate the DOM
//   ArgoI18n.t('login.title')                        // programmatic lookup
//
// Mark up elements declaratively:
//   <h1 data-i18n="login.title">Login</h1>
//   <input data-i18n-placeholder="chat.input_placeholder">
//   <button data-i18n-title="sidebar.new_chat"></button>
//
// Default locale is Italian (the product targets Italian SMEs). The fallback
// chain is: current locale → English → the in-markup text → the key itself, so
// untranslated strings degrade gracefully instead of showing blank.
(function (global) {
  'use strict';
  var STORAGE_KEY = 'argodesk-locale';
  var DEFAULT_LOCALE = 'it';
  var SUPPORTED = ['it', 'en'];

  var _catalogs = {}; // locale -> { key: value }
  var _locale = DEFAULT_LOCALE;

  function getLocale() {
    try {
      var v = localStorage.getItem(STORAGE_KEY);
      if (v && SUPPORTED.indexOf(v) !== -1) return v;
    } catch (_) {}
    return DEFAULT_LOCALE;
  }

  async function _load(locale) {
    if (_catalogs[locale]) return _catalogs[locale];
    try {
      var res = await fetch('/static/locales/' + locale + '.json', { credentials: 'same-origin' });
      _catalogs[locale] = res.ok ? await res.json() : {};
    } catch (_) {
      _catalogs[locale] = {};
    }
    return _catalogs[locale];
  }

  async function init(locale) {
    _locale = locale || getLocale();
    await _load(_locale);
    if (_locale !== 'en') await _load('en'); // fallback catalog
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

  function apply(root) {
    root = root || document;
    root.querySelectorAll('[data-i18n]').forEach(function (elm) {
      var k = elm.getAttribute('data-i18n');
      var v = t(k, elm.textContent);
      if (v != null) elm.textContent = v;
    });
    root.querySelectorAll('[data-i18n-placeholder]').forEach(function (elm) {
      var k = elm.getAttribute('data-i18n-placeholder');
      elm.setAttribute('placeholder', t(k, elm.getAttribute('placeholder') || ''));
    });
    root.querySelectorAll('[data-i18n-title]').forEach(function (elm) {
      var k = elm.getAttribute('data-i18n-title');
      elm.setAttribute('title', t(k, elm.getAttribute('title') || ''));
    });
  }

  async function setLocale(locale) {
    if (SUPPORTED.indexOf(locale) === -1) return;
    try { localStorage.setItem(STORAGE_KEY, locale); } catch (_) {}
    await init(locale);
    apply(document);
  }

  global.ArgoI18n = {
    init: init, t: t, apply: apply, setLocale: setLocale,
    getLocale: getLocale, SUPPORTED: SUPPORTED, DEFAULT_LOCALE: DEFAULT_LOCALE,
  };
})(window);
