// static/js/knowledge.js — first-class Knowledge tool (ES6)
//
// Unifies into one panel: guided RAG upload (reuses /api/personal/upload with a
// mandatory "purpose" + optional category → Chroma metadata), the company wiki
// (reuses /api/wiki), and user-definable knowledge categories
// (/api/knowledge/categories). The company/shared sections are `azienda-only`;
// in freelance mode the personal RAG upload remains. A graph slot
// (#knowledge-graph-root) is populated by knowledgeGraph.js (Fase 5).

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, c => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
}

let _overlay = null;
let _activeTab = 'docs';

function _ensureOverlay() {
  if (_overlay) return _overlay;
  _overlay = document.createElement('div');
  _overlay.id = 'knowledge-overlay';
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

function close() {
  if (_overlay) _overlay.style.display = 'none';
  document.getElementById('tool-knowledge-btn')?.classList.remove('active');
}

function _shell() {
  const tab = (id, label) =>
    `<button class="admin-btn-sm kn-tab${_activeTab === id ? ' active' : ''}" data-kn-tab="${id}" `
    + `style="${_activeTab === id ? 'background:var(--accent,var(--red));color:#fff;' : 'opacity:0.75;'}">${esc(label)}</button>`;
  return (
    '<div class="admin-card" style="width:min(680px,94vw);max-height:88vh;overflow:auto;border-radius:10px;box-shadow:0 12px 48px rgba(0,0,0,0.4);">'
    + '<div style="display:flex;align-items:center;gap:8px;margin-bottom:10px;">'
    + '<h2 style="margin:0;flex:1;">Conoscenza</h2>'
    + '<button class="admin-btn-sm" id="kn-close" style="opacity:0.7;">Chiudi</button>'
    + '</div>'
    + `<div style="display:flex;gap:6px;margin-bottom:12px;flex-wrap:wrap;">${tab('docs', 'Documenti')}${tab('wiki', 'Wiki aziendale')}${tab('cats', 'Categorie')}${tab('graph', 'Grafo')}</div>`
    + '<div id="kn-body"></div>'
    + '</div>'
  );
}

async function open() {
  _ensureOverlay();
  _overlay.innerHTML = _shell();
  _overlay.style.display = 'flex';
  document.getElementById('tool-knowledge-btn')?.classList.add('active');
  _overlay.querySelectorAll('[data-kn-tab]').forEach(b => b.addEventListener('click', () => { _activeTab = b.dataset.knTab; open(); }));
  document.getElementById('kn-close')?.addEventListener('click', close);
  if (_activeTab === 'docs') await _renderDocs();
  else if (_activeTab === 'wiki') await _renderWiki();
  else if (_activeTab === 'cats') await _renderCategories();
  else if (_activeTab === 'graph') await _renderGraph();
}

// ── Documents: guided RAG upload ──────────────────────────────────────
async function _loadCategories() {
  try {
    const r = await fetch('/api/knowledge/categories', { credentials: 'same-origin' });
    const d = await r.json();
    return Array.isArray(d.categories) ? d.categories : [];
  } catch (_) { return []; }
}

async function _renderDocs() {
  const body = document.getElementById('kn-body');
  const cats = await _loadCategories();
  const catOpts = ['<option value="">— Categoria (opzionale) —</option>']
    .concat(cats.map(c => `<option value="${esc(c.name)}">${esc(c.name)}${c.shared ? ' (azienda)' : ''}</option>`)).join('');
  body.innerHTML =
    '<div class="admin-toggle-sub" style="margin-bottom:8px;">Carica documenti nella conoscenza. Spiega <b>perché</b> lo carichi: aiuta l\'AI a usarlo nel contesto giusto.</div>'
    + '<div class="settings-col">'
    + '<div class="settings-row"><label class="settings-label">File</label><input type="file" id="kn-files" multiple accept=".pdf,.txt,.md,.docx,.csv,.json,.html" style="flex:1;"></div>'
    + '<div class="settings-row"><label class="settings-label">Scopo *</label><input id="kn-purpose" class="settings-input" placeholder="Es. Listino prezzi 2026 per preventivi"></div>'
    + `<div class="settings-row"><label class="settings-label">Categoria</label><select id="kn-category" class="settings-select">${catOpts}</select></div>`
    + '<div class="settings-row azienda-only"><label class="settings-label">Condividi (azienda)</label><label class="admin-switch" style="margin-left:0;"><input type="checkbox" id="kn-shared"><span class="admin-slider"></span></label><span style="font-size:10px;opacity:0.5;margin-left:6px;">Visibile a tutti gli utenti</span></div>'
    + '<div class="settings-row" style="margin-top:4px;"><button class="admin-btn-add" id="kn-upload">Carica</button><span id="kn-upload-msg" style="font-size:11px;margin-left:8px;"></span></div>'
    + '</div>';

  document.getElementById('kn-upload')?.addEventListener('click', async () => {
    const files = document.getElementById('kn-files').files;
    const purpose = document.getElementById('kn-purpose').value.trim();
    const msg = document.getElementById('kn-upload-msg');
    const setMsg = (t, ok) => { msg.textContent = t; msg.style.color = ok ? 'var(--green,#50fa7b)' : 'var(--red)'; };
    if (!files || !files.length) { setMsg('Seleziona almeno un file', false); return; }
    if (!purpose) { setMsg('Lo scopo è obbligatorio', false); return; }
    const fd = new FormData();
    for (const f of files) fd.append('files', f);
    fd.append('purpose', purpose);
    fd.append('category', document.getElementById('kn-category').value || '');
    fd.append('shared', document.getElementById('kn-shared')?.checked ? 'true' : 'false');
    setMsg('Caricamento…', true); msg.style.color = '';
    try {
      const r = await fetch('/api/personal/upload', { method: 'POST', credentials: 'same-origin', body: fd });
      const d = await r.json();
      if (!r.ok || d.success === false) throw new Error(d.detail || ('HTTP ' + r.status));
      setMsg(`Indicizzati ${d.indexed_count || 0} blocchi` + (d.failed_count ? `, ${d.failed_count} falliti` : ''), true);
      document.getElementById('kn-files').value = '';
      document.getElementById('kn-purpose').value = '';
    } catch (e) { setMsg(e.message || 'Caricamento non riuscito', false); }
  });
}

// ── Wiki (reuses /api/wiki) ───────────────────────────────────────────
async function _renderWiki() {
  const body = document.getElementById('kn-body');
  body.innerHTML =
    '<div class="azienda-only">'
    + '<div class="admin-toggle-sub" style="margin-bottom:8px;">Pagine autorevoli che l\'AI consulta <b>prima</b> dei documenti.</div>'
    + '<div class="settings-col" style="margin-bottom:10px;">'
    + '<input id="kn-wiki-title" class="settings-input" placeholder="Titolo pagina">'
    + '<textarea id="kn-wiki-content" class="settings-select" rows="4" style="font-family:inherit;resize:vertical;" placeholder="Contenuto…"></textarea>'
    + '<input id="kn-wiki-tags" class="settings-input" placeholder="Tag separati da virgola (opzionale)">'
    + '<div class="settings-row"><button class="admin-btn-add" id="kn-wiki-save">Salva pagina</button><span id="kn-wiki-msg" style="font-size:11px;margin-left:8px;"></span></div>'
    + '</div>'
    + '<div id="kn-wiki-list"><div class="admin-empty">Caricamento…</div></div>'
    + '</div>';

  const renderList = async () => {
    const listEl = document.getElementById('kn-wiki-list');
    try {
      const r = await fetch('/api/wiki', { credentials: 'same-origin' });
      const d = await r.json();
      const pages = d.pages || [];
      if (!pages.length) { listEl.innerHTML = '<div class="admin-empty">Nessuna pagina.</div>'; return; }
      listEl.innerHTML = pages.map(p =>
        `<div class="settings-row" style="border-bottom:1px solid var(--border);padding:6px 0;">`
        + `<span style="flex:1;font-size:12px;">${esc(p.title || '(senza titolo)')}</span>`
        + `<button class="admin-btn-sm kn-wiki-del" data-id="${esc(p.id)}" style="opacity:0.7;">Elimina</button></div>`
      ).join('');
      listEl.querySelectorAll('.kn-wiki-del').forEach(b => b.addEventListener('click', async () => {
        await fetch('/api/wiki/' + encodeURIComponent(b.dataset.id), { method: 'DELETE', credentials: 'same-origin' });
        renderList();
      }));
    } catch (_) { listEl.innerHTML = '<div class="admin-empty">Errore di caricamento.</div>'; }
  };

  document.getElementById('kn-wiki-save')?.addEventListener('click', async () => {
    const title = document.getElementById('kn-wiki-title').value.trim();
    const content = document.getElementById('kn-wiki-content').value;
    const tags = document.getElementById('kn-wiki-tags').value.split(',').map(t => t.trim()).filter(Boolean);
    const msg = document.getElementById('kn-wiki-msg');
    if (!title) { msg.textContent = 'Titolo obbligatorio'; msg.style.color = 'var(--red)'; return; }
    msg.textContent = 'Salvataggio…'; msg.style.color = '';
    try {
      const r = await fetch('/api/wiki', {
        method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title, content, tags }),
      });
      if (!r.ok) throw new Error('HTTP ' + r.status);
      msg.textContent = 'Salvato'; msg.style.color = 'var(--green,#50fa7b)';
      document.getElementById('kn-wiki-title').value = '';
      document.getElementById('kn-wiki-content').value = '';
      document.getElementById('kn-wiki-tags').value = '';
      renderList();
    } catch (e) { msg.textContent = e.message; msg.style.color = 'var(--red)'; }
  });
  renderList();
}

// ── Categories ────────────────────────────────────────────────────────
async function _renderCategories() {
  const body = document.getElementById('kn-body');
  body.innerHTML =
    '<div class="admin-toggle-sub" style="margin-bottom:8px;">Aree di conoscenza per organizzare i caricamenti.</div>'
    + '<div class="settings-col" style="margin-bottom:10px;">'
    + '<div class="settings-row"><input id="kn-cat-name" class="settings-input" placeholder="Nome categoria (es. Contratti)" style="flex:1;"></div>'
    + '<div class="settings-row"><input id="kn-cat-desc" class="settings-input" placeholder="Descrizione (opzionale)" style="flex:1;"></div>'
    + '<div class="settings-row azienda-only"><label class="settings-label">Condivisa</label><label class="admin-switch" style="margin-left:0;"><input type="checkbox" id="kn-cat-shared"><span class="admin-slider"></span></label></div>'
    + '<div class="settings-row"><button class="admin-btn-add" id="kn-cat-add">Aggiungi</button><span id="kn-cat-msg" style="font-size:11px;margin-left:8px;"></span></div>'
    + '</div>'
    + '<div id="kn-cat-list"><div class="admin-empty">Caricamento…</div></div>';

  const renderList = async () => {
    const listEl = document.getElementById('kn-cat-list');
    const cats = await _loadCategories();
    if (!cats.length) { listEl.innerHTML = '<div class="admin-empty">Nessuna categoria.</div>'; return; }
    listEl.innerHTML = cats.map(c =>
      `<div class="settings-row" style="border-bottom:1px solid var(--border);padding:6px 0;">`
      + `<span style="flex:1;font-size:12px;">${esc(c.name)}${c.shared ? ' <span style="opacity:0.5;">(azienda)</span>' : ''}`
      + (c.description ? `<br><span style="font-size:10px;opacity:0.6;">${esc(c.description)}</span>` : '') + '</span>'
      + `<button class="admin-btn-sm kn-cat-del" data-id="${esc(c.id)}" style="opacity:0.7;">Elimina</button></div>`
    ).join('');
    listEl.querySelectorAll('.kn-cat-del').forEach(b => b.addEventListener('click', async () => {
      await fetch('/api/knowledge/categories/' + encodeURIComponent(b.dataset.id), { method: 'DELETE', credentials: 'same-origin' });
      renderList();
    }));
  };

  document.getElementById('kn-cat-add')?.addEventListener('click', async () => {
    const name = document.getElementById('kn-cat-name').value.trim();
    const msg = document.getElementById('kn-cat-msg');
    if (!name) { msg.textContent = 'Nome obbligatorio'; msg.style.color = 'var(--red)'; return; }
    msg.textContent = 'Salvataggio…'; msg.style.color = '';
    try {
      const r = await fetch('/api/knowledge/categories', {
        method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name,
          description: document.getElementById('kn-cat-desc').value.trim(),
          shared: document.getElementById('kn-cat-shared')?.checked || false,
        }),
      });
      if (!r.ok) throw new Error('HTTP ' + r.status);
      msg.textContent = 'Aggiunta'; msg.style.color = 'var(--green,#50fa7b)';
      document.getElementById('kn-cat-name').value = '';
      document.getElementById('kn-cat-desc').value = '';
      renderList();
    } catch (e) { msg.textContent = e.message; msg.style.color = 'var(--red)'; }
  });
  renderList();
}

// ── Graph (populated by knowledgeGraph.js — Fase 5) ───────────────────
async function _renderGraph() {
  const body = document.getElementById('kn-body');
  body.innerHTML = '<div id="knowledge-graph-root" class="azienda-only"></div>';
  try {
    const mod = await import('./knowledgeGraph.js');
    const render = mod.renderKnowledgeGraph || (mod.default && mod.default.renderKnowledgeGraph);
    if (typeof render === 'function') render(document.getElementById('knowledge-graph-root'));
  } catch (_) {
    body.innerHTML = '<div class="admin-empty">Grafo non disponibile.</div>';
  }
}

const knowledgeModule = { open, close };
window.knowledgeModule = knowledgeModule;
export default knowledgeModule;
