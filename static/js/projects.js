// static/js/projects.js — Notion-style Projects tool (ES6)
//
// Self-contained overlay: list of projects → detail view that resolves linked
// notes, documents, gallery albums (photos shown inline), chat sessions and
// knowledge via /api/projects/{id}/contents. Reuses existing list endpoints
// (/api/notes, /api/gallery/albums) for the link pickers. Company-shared
// projects (ORG_OWNER) are gated `azienda-only` in the create form.

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, c => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
}

let _overlay = null;

function _ensureOverlay() {
  if (_overlay) return _overlay;
  _overlay = document.createElement('div');
  _overlay.id = 'projects-overlay';
  _overlay.style.cssText =
    'position:fixed;inset:0;z-index:9000;display:none;align-items:center;justify-content:center;'
    + 'background:rgba(0,0,0,0.55);backdrop-filter:blur(2px);';
  _overlay.addEventListener('mousedown', (e) => { if (e.target === _overlay) close(); });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && _overlay && _overlay.style.display !== 'none') close();
  });
  document.body.appendChild(_overlay);
  return _overlay;
}

function _card(inner) {
  return '<div class="admin-card" style="width:min(720px,94vw);max-height:88vh;overflow:auto;'
    + 'border-radius:10px;box-shadow:0 12px 48px rgba(0,0,0,0.4);">' + inner + '</div>';
}

function close() {
  if (_overlay) _overlay.style.display = 'none';
  document.getElementById('tool-projects-btn')?.classList.remove('active');
}

async function open() {
  _ensureOverlay();
  _overlay.style.display = 'flex';
  document.getElementById('tool-projects-btn')?.classList.add('active');
  await _renderList();
}

async function _fetchProjects() {
  try {
    const r = await fetch('/api/projects', { credentials: 'same-origin' });
    const d = await r.json();
    return Array.isArray(d.projects) ? d.projects : [];
  } catch (_) { return []; }
}

async function _renderList() {
  const projects = await _fetchProjects();
  let cards = projects.map(p =>
    `<button class="pr-open admin-btn-add" data-id="${esc(p.id)}" style="display:flex;flex-direction:column;align-items:flex-start;gap:2px;text-align:left;padding:12px 14px;min-width:160px;flex:1;">`
    + `<span style="font-weight:600;font-size:13px;">${esc(p.name)}${p.shared ? ' <span style="opacity:0.5;font-weight:400;">(azienda)</span>' : ''}</span>`
    + (p.description ? `<span style="font-size:11px;opacity:0.6;">${esc(p.description.slice(0, 80))}</span>` : '')
    + '</button>'
  ).join('');
  if (!projects.length) cards = '<div class="admin-empty">Nessun progetto. Creane uno qui sotto.</div>';

  _overlay.innerHTML = _card(
    '<div style="display:flex;align-items:center;gap:8px;margin-bottom:12px;">'
    + '<h2 style="margin:0;flex:1;">Progetti</h2>'
    + '<button class="admin-btn-sm" id="pr-close" style="opacity:0.7;">Chiudi</button></div>'
    + `<div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:14px;">${cards}</div>`
    + '<div class="admin-card" style="background:color-mix(in srgb,var(--fg) 3%,transparent);">'
    + '<div class="admin-toggle-label" style="margin-bottom:6px;">Nuovo progetto</div>'
    + '<div class="settings-col">'
    + '<input id="pr-new-name" class="settings-input" placeholder="Nome progetto">'
    + '<input id="pr-new-desc" class="settings-input" placeholder="Descrizione (opzionale)">'
    + '<div class="settings-row azienda-only"><label class="settings-label">Condiviso (azienda)</label><label class="admin-switch" style="margin-left:0;"><input type="checkbox" id="pr-new-shared"><span class="admin-slider"></span></label></div>'
    + '<div class="settings-row"><button class="admin-btn-add" id="pr-new-create">Crea</button><span id="pr-new-msg" style="font-size:11px;margin-left:8px;"></span></div>'
    + '</div></div>'
  );
  _overlay.querySelector('#pr-close')?.addEventListener('click', close);
  _overlay.querySelectorAll('.pr-open').forEach(b => b.addEventListener('click', () => _renderDetail(b.dataset.id)));
  _overlay.querySelector('#pr-new-create')?.addEventListener('click', async () => {
    const name = _overlay.querySelector('#pr-new-name').value.trim();
    const msg = _overlay.querySelector('#pr-new-msg');
    if (!name) { msg.textContent = 'Nome obbligatorio'; msg.style.color = 'var(--red)'; return; }
    try {
      const r = await fetch('/api/projects', {
        method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name,
          description: _overlay.querySelector('#pr-new-desc').value.trim(),
          shared: _overlay.querySelector('#pr-new-shared')?.checked || false,
        }),
      });
      const d = await r.json();
      if (!r.ok) throw new Error('HTTP ' + r.status);
      _renderDetail(d.project.id);
    } catch (e) { msg.textContent = e.message; msg.style.color = 'var(--red)'; }
  });
}

async function _renderDetail(projectId) {
  _overlay.innerHTML = _card('<div class="admin-empty">Caricamento…</div>');
  let project = null, contents = null;
  try {
    project = await fetch('/api/projects/' + projectId, { credentials: 'same-origin' }).then(r => r.json());
    contents = await fetch(`/api/projects/${projectId}/contents`, { credentials: 'same-origin' }).then(r => r.json());
  } catch (_) {
    _overlay.innerHTML = _card('<div class="admin-empty">Errore di caricamento.</div>');
    return;
  }

  const section = (title, items, renderItem, extraBtn) =>
    `<div style="margin-bottom:14px;"><div class="admin-toggle-label" style="margin-bottom:4px;display:flex;align-items:center;">`
    + `<span style="flex:1;">${esc(title)}</span>${extraBtn || ''}</div>`
    + (items && items.length ? items.map(renderItem).join('') : '<div class="admin-empty" style="font-size:11px;">Niente collegato.</div>')
    + '</div>';

  const linkRow = (label, linkId) =>
    `<div class="settings-row" style="border-bottom:1px solid var(--border);padding:5px 0;">`
    + `<span style="flex:1;font-size:12px;">${esc(label)}</span>`
    + `<button class="admin-btn-sm pr-unlink" data-link="${esc(linkId)}" style="opacity:0.6;">Scollega</button></div>`;

  const albumBlock = (a) =>
    `<div style="border:1px solid var(--border);border-radius:8px;padding:8px;margin-bottom:6px;">`
    + `<div class="settings-row" style="margin-bottom:6px;"><span style="flex:1;font-size:12px;font-weight:600;">${esc(a.name)}</span>`
    + `<button class="admin-btn-sm pr-unlink" data-link="${esc(a.link_id)}" style="opacity:0.6;">Scollega</button></div>`
    + `<div style="display:flex;gap:4px;flex-wrap:wrap;">`
    + (a.images || []).map(im => `<img src="${esc(im.url)}" loading="lazy" style="width:54px;height:54px;object-fit:cover;border-radius:4px;">`).join('')
    + '</div></div>';

  _overlay.innerHTML = _card(
    '<div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">'
    + '<button class="admin-btn-sm" id="pr-back" style="opacity:0.7;">‹ Progetti</button>'
    + `<h2 style="margin:0;flex:1;">${esc(project.name)}${project.shared ? ' <span style="opacity:0.5;font-size:12px;">(azienda)</span>' : ''}</h2>`
    + '<button class="admin-btn-sm" id="pr-del" style="opacity:0.6;">Elimina</button>'
    + '<button class="admin-btn-sm" id="pr-close" style="opacity:0.7;">Chiudi</button></div>'
    + (project.description ? `<div class="admin-toggle-sub" style="margin-bottom:10px;">${esc(project.description)}</div>` : '')
    + section('Pagine e Note', contents.notes, n => linkRow(n.title, n.link_id),
        '<button class="admin-btn-sm" id="pr-link-note" style="font-size:10px;">+ Collega nota</button>')
    + section('Documenti', contents.documents, d => linkRow(d.title, d.link_id))
    + section('Album', contents.albums, albumBlock,
        '<button class="admin-btn-sm" id="pr-link-album" style="font-size:10px;">+ Collega album</button>')
    + section('Chat collegate', contents.sessions, s => linkRow(s.name, s.link_id))
    + section('Conoscenza', (contents.knowledge_categories || []).concat(contents.knowledge_entities || []),
        k => linkRow(k.name, k.link_id))
  );

  _overlay.querySelector('#pr-close')?.addEventListener('click', close);
  _overlay.querySelector('#pr-back')?.addEventListener('click', () => _renderList());
  _overlay.querySelector('#pr-del')?.addEventListener('click', async () => {
    if (!confirm('Eliminare questo progetto? I link verranno rimossi (gli oggetti restano).')) return;
    await fetch('/api/projects/' + projectId, { method: 'DELETE', credentials: 'same-origin' });
    _renderList();
  });
  _overlay.querySelectorAll('.pr-unlink').forEach(b => b.addEventListener('click', async () => {
    await fetch(`/api/projects/${projectId}/links/${b.dataset.link}`, { method: 'DELETE', credentials: 'same-origin' });
    _renderDetail(projectId);
  }));
  _overlay.querySelector('#pr-link-note')?.addEventListener('click', () => _linkPicker(projectId, 'note'));
  _overlay.querySelector('#pr-link-album')?.addEventListener('click', () => _linkPicker(projectId, 'album'));
}

// Lightweight picker: fetch candidates for a kind, let the user pick one, link it.
async function _linkPicker(projectId, kind) {
  let items = [];
  try {
    if (kind === 'note') {
      const d = await fetch('/api/notes', { credentials: 'same-origin' }).then(r => r.json());
      items = (d.notes || []).map(n => ({ id: n.id, label: n.title || '(senza titolo)' }));
    } else if (kind === 'album') {
      const d = await fetch('/api/gallery/albums', { credentials: 'same-origin' }).then(r => r.json());
      const albums = Array.isArray(d) ? d : (d.albums || []);
      items = albums.map(a => ({ id: a.id, label: a.name || '(album)' }));
    }
  } catch (_) {}
  if (!items.length) { alert('Nessun elemento disponibile da collegare.'); return; }

  const menu = document.createElement('div');
  menu.className = 'admin-card';
  menu.style.cssText = 'position:fixed;z-index:10001;top:50%;left:50%;transform:translate(-50%,-50%);'
    + 'width:min(360px,90vw);max-height:70vh;overflow:auto;box-shadow:0 12px 48px rgba(0,0,0,0.5);';
  menu.innerHTML = '<div class="admin-toggle-label" style="margin-bottom:6px;">Scegli</div>'
    + items.map(it => `<button class="admin-btn-sm pr-pick" data-id="${esc(it.id)}" style="display:block;width:100%;text-align:left;margin-bottom:3px;">${esc(it.label)}</button>`).join('');
  document.body.appendChild(menu);
  const cleanup = () => menu.remove();
  menu.querySelectorAll('.pr-pick').forEach(b => b.addEventListener('click', async () => {
    await fetch(`/api/projects/${projectId}/links`, {
      method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ kind, target_id: b.dataset.id }),
    });
    cleanup();
    _renderDetail(projectId);
  }));
  setTimeout(() => {
    const close = (e) => { if (!menu.contains(e.target)) { cleanup(); document.removeEventListener('click', close); } };
    document.addEventListener('click', close);
  }, 0);
}

// Called from gallery.js album menu → pick a project and link this album.
async function addAlbumToProject(albumId) {
  const projects = await _fetchProjects();
  if (!projects.length) { alert('Crea prima un progetto (icona Progetti nella barra laterale).'); return; }
  const menu = document.createElement('div');
  menu.className = 'admin-card';
  menu.style.cssText = 'position:fixed;z-index:10001;top:50%;left:50%;transform:translate(-50%,-50%);'
    + 'width:min(360px,90vw);max-height:70vh;overflow:auto;box-shadow:0 12px 48px rgba(0,0,0,0.5);';
  menu.innerHTML = '<div class="admin-toggle-label" style="margin-bottom:6px;">Aggiungi a progetto</div>'
    + projects.map(p => `<button class="admin-btn-sm pr-pick" data-id="${esc(p.id)}" style="display:block;width:100%;text-align:left;margin-bottom:3px;">${esc(p.name)}</button>`).join('');
  document.body.appendChild(menu);
  menu.querySelectorAll('.pr-pick').forEach(b => b.addEventListener('click', async () => {
    await fetch(`/api/projects/${b.dataset.id}/links`, {
      method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ kind: 'album', target_id: albumId }),
    });
    menu.remove();
    try { window.uiModule?.showToast?.('Album aggiunto al progetto'); } catch (_) {}
  }));
  setTimeout(() => {
    const close = (e) => { if (!menu.contains(e.target)) { menu.remove(); document.removeEventListener('click', close); } };
    document.addEventListener('click', close);
  }, 0);
}

const projectsModule = { open, close, addAlbumToProject };
window.projectsModule = projectsModule;
export default projectsModule;
