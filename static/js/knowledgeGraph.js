// static/js/knowledgeGraph.js — GraphRAG-lite viewer (ES6)
//
// Renders the company knowledge graph from /api/knowledge/graph into a light
// vanilla SVG (circular layout — no heavy physics dependency). Clicking a node
// expands its 1-hop neighbourhood via /api/knowledge/entity/{id}. Loaded lazily
// by knowledge.js when the "Grafo" tab is opened.

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, c => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
}

const TYPE_COLOR = {
  person: '#5b8abf', org: '#bf5b8a', concept: '#8abf5b',
  doc: '#bfa15b', project: '#7a5bbf',
};

async function _fetchGraph(focus) {
  const url = focus ? `/api/knowledge/graph?focus=${encodeURIComponent(focus)}` : '/api/knowledge/graph';
  const r = await fetch(url, { credentials: 'same-origin' });
  if (!r.ok) throw new Error('HTTP ' + r.status);
  return await r.json();
}

function _renderSvg(container, data, onNode) {
  const nodes = data.nodes || [];
  const edges = data.edges || [];
  if (!nodes.length) {
    container.innerHTML = '<div class="admin-empty">Il grafo è vuoto. Carica documenti con il grafo attivo per popolarlo.</div>';
    return;
  }
  const W = 600, H = 420, cx = W / 2, cy = H / 2;
  const R = Math.min(cx, cy) - 50;
  const pos = {};
  nodes.forEach((n, i) => {
    const a = (2 * Math.PI * i) / nodes.length - Math.PI / 2;
    pos[n.id] = { x: cx + R * Math.cos(a), y: cy + R * Math.sin(a) };
  });

  let svg = `<svg viewBox="0 0 ${W} ${H}" width="100%" style="max-height:60vh;background:color-mix(in srgb,var(--fg) 3%,transparent);border-radius:8px;">`;
  // Edges
  for (const e of edges) {
    const a = pos[e.src], b = pos[e.dst];
    if (!a || !b) continue;
    svg += `<line x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}" stroke="var(--border)" stroke-width="1"/>`;
    const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
    svg += `<text x="${mx}" y="${my}" font-size="8" fill="var(--fg)" opacity="0.5" text-anchor="middle">${esc(e.relation || '')}</text>`;
  }
  // Nodes
  for (const n of nodes) {
    const p = pos[n.id];
    const color = TYPE_COLOR[n.type] || '#888';
    svg += `<g class="kg-node" data-id="${esc(n.id)}" style="cursor:pointer;">`
      + `<circle cx="${p.x}" cy="${p.y}" r="9" fill="${color}" stroke="var(--bg)" stroke-width="1.5"/>`
      + `<text x="${p.x}" y="${p.y - 13}" font-size="9" fill="var(--fg)" text-anchor="middle">${esc((n.name || '').slice(0, 22))}</text>`
      + `</g>`;
  }
  svg += '</svg>';
  container.innerHTML = svg;
  container.querySelectorAll('.kg-node').forEach(g => {
    g.addEventListener('click', () => onNode(g.dataset.id));
  });
}

export async function renderKnowledgeGraph(rootEl) {
  if (!rootEl) return;
  // Feature-flag enable toggle (reads from /api/auth/settings).
  let enabled = false;
  try {
    const s = await fetch('/api/auth/settings', { credentials: 'same-origin' }).then(r => r.json());
    enabled = !!s.knowledge_graph_enabled;
  } catch (_) {}

  rootEl.innerHTML =
    '<div class="settings-row" style="align-items:center;margin-bottom:8px;">'
    + '<label class="settings-label" style="flex:1;">Grafo della conoscenza attivo</label>'
    + `<label class="admin-switch" style="margin-left:0;"><input type="checkbox" id="kg-enable" ${enabled ? 'checked' : ''}><span class="admin-slider"></span></label>`
    + '</div>'
    + '<div class="admin-toggle-sub" style="margin-bottom:8px;">Estrae entità e relazioni dai documenti caricati e le mostra all\'agente accanto ai documenti. Spende token LLM in background.</div>'
    + '<div id="kg-canvas"><div class="admin-empty">Caricamento…</div></div>';

  const toggle = rootEl.querySelector('#kg-enable');
  toggle?.addEventListener('change', async () => {
    try {
      await fetch('/api/auth/settings', {
        method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ knowledge_graph_enabled: toggle.checked }),
      });
    } catch (_) {}
  });

  const canvas = rootEl.querySelector('#kg-canvas');
  const load = async (focus) => {
    canvas.innerHTML = '<div class="admin-empty">Caricamento…</div>';
    try {
      const data = await _fetchGraph(focus);
      _renderSvg(canvas, data, (id) => load(id));
    } catch (e) {
      canvas.innerHTML = '<div class="admin-empty">Errore di caricamento del grafo.</div>';
    }
  };
  load(null);
}

const knowledgeGraphModule = { renderKnowledgeGraph };
export default knowledgeGraphModule;
