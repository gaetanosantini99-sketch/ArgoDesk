// static/js/connectWizard.js — guided email/calendar connection wizard (ES6)
//
// NO OAuth: walks the user through choosing a provider, generating an
// app-password (when required), then fills the IMAP/SMTP/CalDAV form from the
// server presets (`/api/connect/presets`) and saves through the EXISTING
// endpoints — `/api/email/accounts` (+ /test) and `/api/calendar/config`
// (+ /test). Self-contained overlay so it can be opened from the Email panel,
// the calendar empty-state, or anywhere via `window.connectWizard.open()`.

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, c => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
}

let _overlay = null;
let _presets = null;

function _ensureOverlay() {
  if (_overlay) return _overlay;
  _overlay = document.createElement('div');
  _overlay.id = 'connect-wizard-overlay';
  _overlay.style.cssText =
    'position:fixed;inset:0;z-index:10000;display:none;align-items:center;justify-content:center;'
    + 'background:rgba(0,0,0,0.55);backdrop-filter:blur(2px);';
  _overlay.addEventListener('mousedown', (e) => { if (e.target === _overlay) close(); });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && _overlay && _overlay.style.display !== 'none') close();
  });
  document.body.appendChild(_overlay);
  return _overlay;
}

function _panel(innerHtml) {
  const ov = _ensureOverlay();
  ov.innerHTML =
    '<div class="connect-wizard-card admin-card" style="width:min(560px,92vw);max-height:88vh;overflow:auto;'
    + 'border-radius:10px;box-shadow:0 12px 48px rgba(0,0,0,0.4);">' + innerHtml + '</div>';
  ov.style.display = 'flex';
}

async function _loadPresets() {
  if (_presets) return _presets;
  const res = await fetch('/api/connect/presets', { credentials: 'same-origin' });
  if (!res.ok) throw new Error('HTTP ' + res.status);
  const data = await res.json();
  _presets = data.presets || {};
  return _presets;
}

function close() {
  if (_overlay) _overlay.style.display = 'none';
}

// ── Step 1: provider chooser ──────────────────────────────────────────
async function open(initialProvider) {
  _ensureOverlay();
  _panel('<div class="admin-empty" style="padding:24px;text-align:center;">Caricamento…</div>');
  let presets;
  try {
    presets = await _loadPresets();
  } catch (e) {
    _panel('<h2>Procedura guidata</h2><div class="admin-empty">Impossibile caricare i provider.</div>'
      + '<div style="text-align:right;margin-top:10px;"><button class="admin-btn-sm" id="cw-close">Chiudi</button></div>');
    document.getElementById('cw-close')?.addEventListener('click', close);
    return;
  }
  if (initialProvider && presets[initialProvider]) {
    _renderProvider(initialProvider);
    return;
  }

  let cards = '';
  for (const [key, p] of Object.entries(presets)) {
    cards += `<button type="button" class="cw-provider-card admin-btn-add" data-provider="${esc(key)}" `
      + 'style="display:flex;flex-direction:column;align-items:flex-start;gap:2px;text-align:left;padding:12px 14px;flex:1;min-width:150px;">'
      + `<span style="font-weight:600;font-size:13px;">${esc(p.label)}</span>`
      + `<span style="font-size:11px;opacity:0.6;">${p.app_password && p.app_password.required ? 'Richiede password per app' : 'Configurazione manuale'}</span>`
      + '</button>';
  }
  _panel(
    '<h2 style="margin-top:0;">Connetti email e calendario</h2>'
    + '<div class="admin-toggle-sub" style="margin-bottom:12px;">Scegli il tuo provider: ti guidiamo passo passo, senza OAuth. '
    + 'Usiamo IMAP/SMTP/CalDAV con una password dedicata.</div>'
    + `<div style="display:flex;gap:10px;flex-wrap:wrap;">${cards}</div>`
    + '<div style="text-align:right;margin-top:14px;"><button class="admin-btn-sm" id="cw-close" style="opacity:0.7;">Annulla</button></div>'
  );
  _overlay.querySelectorAll('.cw-provider-card').forEach(btn => {
    btn.addEventListener('click', () => _renderProvider(btn.dataset.provider));
  });
  document.getElementById('cw-close')?.addEventListener('click', close);
}

// ── Step 2: provider config (app-password + email + calendar) ─────────
function _renderProvider(key) {
  const p = _presets[key];
  if (!p) return open();
  const ap = p.app_password || {};
  const em = p.email || {};
  const cal = p.calendar || {};

  let apHtml = '';
  if (ap.title || (ap.steps && ap.steps.length)) {
    const steps = (ap.steps || []).map(s => `<li style="margin:2px 0;">${esc(s)}</li>`).join('');
    const link = ap.url
      ? `<div style="margin-top:6px;"><a href="${esc(ap.url)}" target="_blank" rel="noopener" `
        + `style="color:var(--accent,var(--red));text-decoration:underline;">${esc(ap.url)}</a> `
        + `<button type="button" class="admin-btn-sm cw-copy" data-copy="${esc(ap.url)}" style="margin-left:6px;">Copia link</button></div>`
      : '';
    apHtml =
      '<div style="border:1px solid var(--border);border-left:3px solid var(--accent,var(--red));border-radius:6px;padding:10px 12px;margin-bottom:12px;background:color-mix(in srgb,var(--fg) 4%,transparent);">'
      + `<div style="font-weight:600;font-size:12px;margin-bottom:4px;">${esc(ap.title || '')}</div>`
      + `<ol style="margin:0;padding-left:18px;font-size:11px;line-height:1.5;">${steps}</ol>`
      + link
      + '</div>';
  }

  const calHtml = cal.supported === false
    ? '<div class="admin-toggle-sub" style="font-size:11px;opacity:0.75;">' + esc(cal.note || 'Calendario non supportato per questo provider.') + '</div>'
    : `
      <div class="settings-col">
        <div class="settings-row"><label class="settings-label">URL CalDAV</label><input id="cw-cal-url" class="settings-input" placeholder="https://…" value="${esc(cal.url || '')}"></div>
        <div class="settings-row"><label class="settings-label">Utente</label><input id="cw-cal-user" class="settings-input" placeholder="you@example.com"></div>
        <div class="settings-row"><label class="settings-label">Password</label><input id="cw-cal-pass" class="settings-input" type="password" placeholder="password per app"></div>
        <div class="settings-row" style="margin-top:4px;"><button class="admin-btn-add" id="cw-cal-save">Salva calendario</button><button class="admin-btn-sm" id="cw-cal-test" style="opacity:0.8;">Verifica connessione</button><span id="cw-cal-msg" style="font-size:11px;margin-left:6px;"></span></div>
      </div>`;

  _panel(
    `<div style="display:flex;align-items:center;gap:8px;"><button class="admin-btn-sm" id="cw-back" style="opacity:0.7;">‹ Indietro</button><h2 style="margin:0;flex:1;">${esc(p.label)}</h2><button class="admin-btn-sm" id="cw-close" style="opacity:0.7;">Chiudi</button></div>`
    + '<div style="height:8px;"></div>'
    + apHtml
    + '<div style="font-size:11px;font-weight:600;opacity:0.6;margin:4px 0 6px;">Email</div>'
    + '<div class="settings-col">'
    + '<div class="settings-row"><label class="settings-label">Email</label><input id="cw-em-from" class="settings-input" placeholder="you@example.com"></div>'
    + `<div class="settings-row"><label class="settings-label">IMAP host</label><input id="cw-em-imap-host" class="settings-input" value="${esc(em.imap_host || '')}"></div>`
    + `<div class="settings-row"><label class="settings-label">IMAP porta</label><input id="cw-em-imap-port" class="settings-input" type="number" style="max-width:100px" value="${esc(em.imap_port || 993)}"></div>`
    + `<div class="settings-row"><label class="settings-label">SMTP host</label><input id="cw-em-smtp-host" class="settings-input" value="${esc(em.smtp_host || '')}"></div>`
    + `<div class="settings-row"><label class="settings-label">SMTP porta</label><input id="cw-em-smtp-port" class="settings-input" type="number" style="max-width:100px" value="${esc(em.smtp_port || 465)}"></div>`
    + '<div class="settings-row"><label class="settings-label">Password</label><input id="cw-em-pass" class="settings-input" type="password" placeholder="password per app"></div>'
    + '<div class="settings-row" style="margin-top:4px;"><button class="admin-btn-add" id="cw-em-save">Salva email</button><button class="admin-btn-sm" id="cw-em-test" style="opacity:0.8;">Verifica connessione</button><span id="cw-em-msg" style="font-size:11px;margin-left:6px;"></span></div>'
    + '</div>'
    + '<div style="font-size:11px;font-weight:600;opacity:0.6;margin:14px 0 6px;">Calendario</div>'
    + calHtml
  );

  document.getElementById('cw-back')?.addEventListener('click', () => open());
  document.getElementById('cw-close')?.addEventListener('click', close);
  _overlay.querySelectorAll('.cw-copy').forEach(b => b.addEventListener('click', () => _copy(b.dataset.copy)));

  // Mirror email into the SMTP/CalDAV/IMAP username fields on entry.
  const fromEl = document.getElementById('cw-em-from');
  const _smtpSecurity = (em.smtp_security || 'ssl');

  const _emailBody = () => {
    const from = (fromEl.value || '').trim();
    const body = {
      name: from,
      from_address: from,
      imap_host: document.getElementById('cw-em-imap-host').value.trim(),
      imap_port: parseInt(document.getElementById('cw-em-imap-port').value) || 993,
      imap_user: from,
      imap_starttls: !!em.imap_starttls,
      smtp_host: document.getElementById('cw-em-smtp-host').value.trim(),
      smtp_port: parseInt(document.getElementById('cw-em-smtp-port').value) || 465,
      smtp_security: _smtpSecurity,
      smtp_user: from,
    };
    const pass = document.getElementById('cw-em-pass').value;
    if (pass) { body.imap_password = pass; body.smtp_password = pass; }
    return body;
  };

  const _emailMsg = (text, ok) => {
    const m = document.getElementById('cw-em-msg');
    m.textContent = text; m.style.color = ok ? 'var(--green,#50fa7b)' : 'var(--red)';
  };

  document.getElementById('cw-em-test')?.addEventListener('click', async () => {
    _emailMsg('Verifica…', true); document.getElementById('cw-em-msg').style.color = '';
    try {
      const r = await fetch('/api/email/accounts/test', {
        method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(_emailBody()),
      });
      const d = await r.json();
      if (d.ok) _emailMsg('Connessione riuscita', true);
      else _emailMsg((d.imap && !d.imap.ok ? 'IMAP: ' + (d.imap.error || 'errore') : '') + (d.smtp && !d.smtp.ok ? ' · SMTP: ' + (d.smtp.error || 'errore') : '') || 'Connessione non riuscita', false);
    } catch (e) { _emailMsg('Errore: ' + e.message, false); }
  });

  document.getElementById('cw-em-save')?.addEventListener('click', async () => {
    const body = _emailBody();
    if (!body.from_address) { _emailMsg('Inserisci l’email', false); return; }
    _emailMsg('Salvataggio…', true); document.getElementById('cw-em-msg').style.color = '';
    try {
      const r = await fetch('/api/email/accounts', {
        method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
      });
      const d = await r.json();
      if (!r.ok || d.error) throw new Error(d.error || ('HTTP ' + r.status));
      _emailMsg('Account email salvato', true);
    } catch (e) { _emailMsg(e.message || 'Salvataggio non riuscito', false); }
  });

  if (cal.supported !== false) {
    const _calMsg = (text, ok) => {
      const m = document.getElementById('cw-cal-msg');
      m.textContent = text; m.style.color = ok ? 'var(--green,#50fa7b)' : 'var(--red)';
    };
    const _calBody = () => ({
      url: (document.getElementById('cw-cal-url').value || '').replace('{email}', (document.getElementById('cw-cal-user').value || '').trim()).trim(),
      username: document.getElementById('cw-cal-user').value.trim(),
      password: document.getElementById('cw-cal-pass').value,
    });
    document.getElementById('cw-cal-test')?.addEventListener('click', async () => {
      _calMsg('Verifica…', true); document.getElementById('cw-cal-msg').style.color = '';
      try {
        const r = await fetch('/api/calendar/test', {
          method: 'POST', credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(_calBody()),
        });
        const d = await r.json();
        _calMsg(d.ok ? 'Connessione riuscita' : (d.error || 'Connessione non riuscita'), !!d.ok);
      } catch (e) { _calMsg('Errore: ' + e.message, false); }
    });
    document.getElementById('cw-cal-save')?.addEventListener('click', async () => {
      _calMsg('Verifica e salvataggio…', true); document.getElementById('cw-cal-msg').style.color = '';
      const body = _calBody();
      try {
        const t = await fetch('/api/calendar/test', {
          method: 'POST', credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
        });
        const td = await t.json();
        if (!td.ok) { _calMsg(td.error || 'Connessione non riuscita — non salvato', false); return; }
        await fetch('/api/calendar/config', {
          method: 'POST', credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
        });
        _calMsg('Calendario salvato', true);
      } catch (e) { _calMsg(e.message || 'Salvataggio non riuscito', false); }
    });
  }
}

async function _copy(text) {
  const value = String(text || '');
  if (!value) return;
  try {
    if (navigator.clipboard && window.isSecureContext) { await navigator.clipboard.writeText(value); return; }
  } catch (_) {}
  const ta = document.createElement('textarea');
  ta.value = value; ta.style.cssText = 'position:fixed;left:-9999px;';
  document.body.appendChild(ta); ta.select();
  try { document.execCommand('copy'); } catch (_) {}
  ta.remove();
}

const connectWizard = { open, close };
window.connectWizard = connectWizard;
export default connectWizard;
