import './style.css';
import { createIcons, Network, Database, Layers, Plus, Orbit, List, Search, RefreshCw, Scan, ZoomIn, ZoomOut, ChevronLeft, ChevronRight, X, Trash2, Copy, CopyPlus, Download, Pencil, Save, FilterX } from 'lucide';
import { createGraph } from './graph.js';

const icons = { Network, Database, Layers, Plus, Orbit, List, Search, RefreshCw, Scan, ZoomIn, ZoomOut, ChevronLeft, ChevronRight, X, Trash2, Copy, CopyPlus, Download, Pencil, Save, FilterX };
createIcons({ icons });
const byId = id => document.getElementById(id);
const state = { namespace: '', memoryType: '', query: '', mode: 'text', offset: 0, total: 0, detail: null, editing: null, generation: 0, view: 'graph', busy: false };
let graph, toastTimer, editorBaseline = '', pendingDelete = null;

function editorValues() {
  return JSON.stringify(['memory-title', 'memory-namespace', 'memory-type', 'memory-content', 'memory-tags'].map(id => byId(id).value));
}

function editorDirty() {
  return byId('editor-dialog').open && editorValues() !== editorBaseline;
}

function closeDialog(id) {
  if (state.busy) return;
  if (id === 'editor-dialog' && editorDirty()) byId('discard-dialog').showModal();
  else byId(id).close();
}

function textCount() { byId('text-count').textContent = `${byId('memory-content').value.length.toLocaleString()} / 100,000`; }

function downloadMemory(detail) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(detail, null, 2)], { type: 'application/json' }));
  const link = document.createElement('a'); link.href = url; link.download = `memory-${detail.id}.json`; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function confirmDelete(detail) {
  pendingDelete = detail;
  byId('delete-name').textContent = `${detail.title} (${detail.namespace})`;
  byId('delete-error').hidden = true;
  byId('delete-dialog').showModal();
}

async function rowAction(action, id) {
  if (state.busy) return;
  try {
    const detail = await api(`/memories/${encodeURIComponent(id)}`);
    if (action === 'edit') {
      if (!detail.original_available) throw new Error('Original text is unavailable for this older memory.');
      openEditor(detail);
    } else if (action === 'duplicate') {
      if (!detail.original_available) throw new Error('Original text is unavailable for this older memory.');
      openEditor(detail, true);
    } else if (action === 'download') downloadMemory(detail);
    else if (action === 'delete') confirmDelete(detail);
  } catch (error) { notify(error.message); }
}

function notify(message) {
  clearTimeout(toastTimer);
  byId('toast').textContent = message;
  byId('toast').hidden = false;
  toastTimer = setTimeout(() => { byId('toast').hidden = true; }, 4500);
}

async function api(path, options = {}) {
  const response = await fetch(`/api${path}`, { ...options, headers: { 'Content-Type': 'application/json', 'X-Memory-Client': 'local-ui', ...options.headers } });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    const message = Array.isArray(data.detail) ? data.detail.map(item => `${item.loc.at(-1)}: ${item.msg}`).join('; ') : data.detail;
    throw new Error(message || `Request failed (${response.status})`);
  }
  return response.status === 204 ? null : response.json();
}

function params() {
  const values = new URLSearchParams();
  if (state.namespace) values.set('namespace', state.namespace);
  if (state.memoryType) values.set('memory_type', state.memoryType);
  if (state.query) values.set('query', state.query);
  return values;
}

function showNotice(message = '') { byId('notice').textContent = message; byId('notice').hidden = !message; }

async function refresh() {
  const generation = ++state.generation;
  byId('refresh').disabled = true;
  byId('clear-filters').disabled = !state.namespace && !state.memoryType && !state.query;
  showNotice('');
  try {
    if (state.mode === 'semantic' && state.query && !state.namespace) throw new Error('Select a namespace for semantic search.');
    const query = params();
    query.set('offset', state.offset); query.set('limit', '50');
    const semantic = state.mode === 'semantic' && !!state.query;
    const graphQuery = params();
    if (semantic) graphQuery.delete('query');
    const [status, result, network] = await Promise.all([
      api('/status'), api(`/${semantic ? 'search' : 'memories'}?${query}`), api(`/graph?${graphQuery}`),
    ]);
    if (generation !== state.generation) return;
    state.total = result.total;
    const selectedNamespace = state.namespace;
    const namespaces = [...new Set(['default', ...status.namespaces, ...(selectedNamespace ? [selectedNamespace] : [])])];
    byId('namespace').replaceChildren(new Option('All namespaces', ''), ...namespaces.map(name => new Option(name, name)));
    byId('namespace').value = selectedNamespace;
    byId('total-count').textContent = status.total;
    byId('view-count').textContent = result.total;
    byId('namespace-count').textContent = status.namespaces.length;
    if (semantic) {
      const ids = new Set(result.items.map(item => item.id));
      network.nodes = result.items.map(item => ({ id: item.id, title: item.title, memory_type: item.memory_type, namespace: item.namespace, tags: item.tags }));
      network.links = network.links.filter(link => ids.has(link.source) && ids.has(link.target));
    }
    byId('link-count').textContent = network.links.length;
    byId('graph-limit').textContent = network.truncated ? 'Graph limited to 300 memories / 3,000 links' : `${network.nodes.length} memories`;
    byId('graph-caption').textContent = 'Edges: shared tags within a namespace';
    graph?.setData(network);
    byId('graph-empty').hidden = network.nodes.length > 0;
    byId('graph-empty').querySelector('h2').textContent = status.total ? 'No matching memories' : 'No memories yet';
    renderRows(result.items, semantic);
    byId('connection').textContent = 'Connected'; byId('connection').classList.add('ready');
  } catch (error) {
    if (generation !== state.generation) return;
    showNotice(error.message);
    byId('connection').textContent = 'Request failed'; byId('connection').classList.remove('ready');
  } finally {
    if (generation === state.generation) byId('refresh').disabled = false;
  }
}

function renderRows(items, semantic) {
  const fragment = document.createDocumentFragment();
  for (const item of items) {
    const row = document.createElement('tr');
    const title = document.createElement('td');
    const button = document.createElement('button'); button.textContent = item.title; button.addEventListener('click', () => openDetail(item.id));
    const preview = document.createElement('small'); preview.textContent = item.content?.slice(0, 120) || item.status;
    title.append(button, preview);
    const type = document.createElement('td');
    const badge = document.createElement('span'); badge.className = 'type-badge';
    const dot = document.createElement('span'); dot.className = `dot ${item.memory_type}`;
    badge.append(dot, document.createTextNode(item.memory_type)); type.append(badge);
    const namespace = document.createElement('td'); namespace.textContent = item.namespace;
    const updated = document.createElement('td'); updated.textContent = semantic ? `Score ${item.score.toFixed(3)}` : new Date(item.updated_at).toLocaleDateString();
    const actions = document.createElement('td'); actions.className = 'memory-actions';
    const actionGroup = document.createElement('div'); actionGroup.className = 'row-actions';
    for (const [action, icon, label] of [['edit', 'pencil', 'Edit'], ['duplicate', 'copy-plus', 'Duplicate'], ['download', 'download', 'Download'], ['delete', 'trash-2', 'Delete']]) {
      const control = document.createElement('button'); control.className = `icon-button${action === 'delete' ? ' danger' : ''}`;
      control.type = 'button'; control.dataset.action = action; control.title = `${label} memory`;
      control.setAttribute('aria-label', `${label} ${item.title}`);
      const glyph = document.createElement('i'); glyph.dataset.lucide = icon; control.append(glyph);
      control.addEventListener('click', async () => { control.disabled = true; try { await rowAction(action, item.id); } finally { control.disabled = false; } });
      actionGroup.append(control);
    }
    actions.append(actionGroup);
    row.append(title, type, namespace, updated, actions); fragment.append(row);
  }
  byId('memory-rows').replaceChildren(fragment);
  createIcons({ icons });
  byId('list-empty').hidden = items.length > 0;
  byId('page-summary').textContent = state.total ? `${state.offset + 1}-${state.offset + items.length} of ${state.total}` : '0 memories';
  byId('previous').disabled = semantic || state.offset === 0;
  byId('next').disabled = semantic || state.offset + items.length >= state.total;
}

async function openDetail(id) {
  try {
    const detail = await api(`/memories/${encodeURIComponent(id)}`);
    state.detail = detail;
    byId('detail-title').textContent = detail.title;
    byId('detail-meta').textContent = `${detail.memory_type} | ${detail.namespace} | ${detail.status} | ${detail.chunk_count} chunks\nUpdated ${new Date(detail.updated_at).toLocaleString()}`;
    byId('detail-content').textContent = detail.content || detail.chunks.map(chunk => chunk.text).join('\n\n');
    byId('detail-tags').replaceChildren(...detail.tags.map(tag => { const element = document.createElement('span'); element.className = 'tag'; element.textContent = tag; return element; }));
    byId('chunk-content').replaceChildren(...detail.chunks.map(chunk => { const element = document.createElement('pre'); element.textContent = `${chunk.chunk_index + 1}. ${chunk.text}`; return element; }));
    byId('edit-memory').disabled = !detail.original_available;
    byId('duplicate-memory').disabled = !detail.original_available;
    byId('edit-memory').title = detail.original_available ? 'Edit memory' : 'Original text unavailable for this older record';
    if (!byId('detail-dialog').open) byId('detail-dialog').showModal();
  } catch (error) { notify(error.message); }
}

function openEditor(detail = null, duplicate = false) {
  if (state.busy) return;
  state.editing = duplicate ? null : detail?.id || null;
  byId('editor-title').textContent = duplicate ? 'Duplicate memory' : detail ? 'Edit memory' : 'New memory';
  byId('memory-title').value = duplicate ? `${detail.title.slice(0, 193)} (copy)` : detail?.title || '';
  byId('memory-namespace').value = detail?.namespace || state.namespace || 'default';
  byId('memory-namespace').disabled = !!detail && !duplicate;
  byId('memory-type').value = detail?.memory_type || state.memoryType || 'semantic';
  byId('memory-content').value = detail?.content || '';
  byId('memory-tags').value = detail?.tags.join(', ') || '';
  byId('editor-error').hidden = true;
  editorBaseline = editorValues();
  textCount();
  byId('detail-dialog').close();
  byId('editor-dialog').showModal();
}

byId('editor-form').addEventListener('submit', async event => {
  event.preventDefault();
  if (state.busy) return;
  state.busy = true;
  const saveButton = byId('save-memory'); saveButton.disabled = true; byId('save-label').textContent = 'Indexing...';
  byId('editor-error').hidden = true;
  const payload = { title: byId('memory-title').value, content: byId('memory-content').value,
    namespace: byId('memory-namespace').value, memory_type: byId('memory-type').value,
    tags: byId('memory-tags').value.split(',').map(tag => tag.trim()).filter(Boolean) };
  try {
    const saved = await api(`/memories${state.editing ? '/' + state.editing : ''}`, { method: state.editing ? 'PUT' : 'POST', body: JSON.stringify(payload) });
    byId('editor-dialog').close(); state.offset = 0;
    await refresh(); await openDetail(saved.id); notify('Memory saved');
  } catch (error) { byId('editor-error').textContent = error.message; byId('editor-error').hidden = false; }
  finally { state.busy = false; saveButton.disabled = false; byId('save-label').textContent = 'Save memory'; }
});

for (const button of document.querySelectorAll('[data-close]')) button.addEventListener('click', () => closeDialog(button.dataset.close));
byId('editor-dialog').addEventListener('cancel', event => { event.preventDefault(); closeDialog('editor-dialog'); });
byId('discard-edit').addEventListener('click', () => { byId('discard-dialog').close(); byId('editor-dialog').close(); });
byId('memory-content').addEventListener('input', textCount);
window.addEventListener('beforeunload', event => { if (editorDirty() || state.busy) { event.preventDefault(); event.returnValue = ''; } });
byId('new-memory').addEventListener('click', () => openEditor());
byId('empty-create').addEventListener('click', () => openEditor());
byId('edit-memory').addEventListener('click', () => openEditor(state.detail));
byId('duplicate-memory').addEventListener('click', () => openEditor(state.detail, true));
byId('delete-memory').addEventListener('click', () => confirmDelete(state.detail));
byId('confirm-delete').addEventListener('click', async () => {
  if (state.busy || !pendingDelete) return;
  state.busy = true;
  byId('confirm-delete').disabled = true;
  try {
    await api(`/memories/${pendingDelete.id}`, { method: 'DELETE' });
    byId('delete-dialog').close();
    if (state.detail?.id === pendingDelete.id) { byId('detail-dialog').close(); state.detail = null; }
    pendingDelete = null; state.offset = 0;
    await refresh(); notify('Memory deleted');
  } catch (error) { byId('delete-error').textContent = error.message; byId('delete-error').hidden = false; }
  finally { state.busy = false; byId('confirm-delete').disabled = false; }
});
byId('delete-dialog').addEventListener('cancel', event => { if (state.busy) event.preventDefault(); });
byId('copy-memory').addEventListener('click', async () => { try { await navigator.clipboard.writeText(byId('detail-content').textContent); notify('Text copied'); } catch { notify('Clipboard access is unavailable.'); } });
byId('export-memory').addEventListener('click', () => downloadMemory(state.detail));

function changeView(view) {
  state.view = view;
  for (const name of ['graph', 'list']) { byId(`${name}-view`).hidden = view !== name; byId(`${name}-tab`).setAttribute('aria-selected', String(view === name)); }
  graph?.active(view === 'graph');
}
byId('graph-tab').addEventListener('click', () => changeView('graph'));
byId('list-tab').addEventListener('click', () => changeView('list'));
byId('namespace').addEventListener('change', event => { state.namespace = event.target.value; state.offset = 0; refresh(); });
for (const button of document.querySelectorAll('[data-type]')) button.addEventListener('click', () => {
  state.memoryType = button.dataset.type; state.offset = 0;
  document.querySelectorAll('[data-type]').forEach(item => item.classList.toggle('active', item === button)); refresh();
});
byId('search-form').addEventListener('submit', event => { event.preventDefault(); state.query = byId('search').value.trim(); state.mode = byId('search-mode').value; state.offset = 0; refresh(); });
byId('search').addEventListener('input', () => { if (!byId('search').value && state.query) { state.query = ''; state.offset = 0; refresh(); } });
byId('refresh').addEventListener('click', refresh);
byId('clear-filters').addEventListener('click', () => {
  state.namespace = ''; state.memoryType = ''; state.query = ''; state.mode = 'text'; state.offset = 0;
  byId('namespace').value = ''; byId('search').value = ''; byId('search-mode').value = 'text';
  document.querySelectorAll('[data-type]').forEach(button => button.classList.toggle('active', button.dataset.type === ''));
  refresh();
});
byId('previous').addEventListener('click', () => { state.offset = Math.max(0, state.offset - 50); refresh(); });
byId('next').addEventListener('click', () => { state.offset += 50; refresh(); });
byId('fit').addEventListener('click', () => graph?.fit());
byId('zoom-in').addEventListener('click', () => graph?.zoom(.8));
byId('zoom-out').addEventListener('click', () => graph?.zoom(1.25));
byId('labels').addEventListener('change', event => graph?.labels(event.target.checked));
byId('rotate').addEventListener('change', event => graph?.rotate(event.target.checked));

await document.fonts.ready;
try { graph = createGraph(byId('graph'), openDetail); }
catch (error) { changeView('list'); byId('graph-tab').disabled = true; notify('3D rendering is unavailable. Memory list remains available.'); }
await refresh();