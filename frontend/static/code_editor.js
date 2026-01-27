/**
 * =============================================================================
 * CODE_EDITOR.JS - Embedded code editor interface
 * =============================================================================
 * 
 * Provides a simple file browser and code editor for managing user scripts
 * stored in the user_code directory. Supports Python and JavaScript files.
 */

(function () {
  const treeEl = () => document.getElementById('file-tree');
  const editorTA = () => document.getElementById('editor');
  const editorPath = () => document.getElementById('editor-path');
  const consoleEl = () => document.getElementById('console');
  let cm = null;

  function log(msg) {
    const el = consoleEl();
    el.textContent += (typeof msg === 'string' ? msg : JSON.stringify(msg, null, 2)) + '\n';
    el.scrollTop = el.scrollHeight;
  }

  function setModeByPath(path) {
    if (!cm) return;
    if (path.endsWith('.py')) cm.setOption('mode', 'python');
    else if (path.endsWith('.js')) cm.setOption('mode', 'javascript');
    else cm.setOption('mode', null);
  }

  async function fetchJSON(url, opts) {
    const res = await fetch(url, opts);
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).error || (res.status + ': ' + res.statusText));
    return res.json();
  }

  async function loadTree() {
    const data = await fetchJSON('/api/code/tree');
    renderTreeRoot(data);
  }

  function renderTreeRoot(root) {
    const el = treeEl();
    el.innerHTML = '';
    const container = document.createElement('div');
    el.appendChild(container);

    // Render top-level
    renderDirectory(container, root.path || '', 0);
  }

  async function renderDirectory(parentEl, relPath, depth) {
    try {
      const data = await fetchJSON('/api/code/tree' + (relPath ? ('?path=' + encodeURIComponent(relPath)) : ''));
      const dirEl = document.createElement('div');
      dirEl.className = 'space-y-1';

      (data.dirs || []).forEach(d => {
        const row = document.createElement('div');
        row.className = 'pl-' + (depth * 2);
        const btn = document.createElement('button');
        btn.className = 'text-left hover:underline';
        btn.textContent = '📁 ' + d.name;
        const children = document.createElement('div');
        children.className = 'ml-4 hidden';
        btn.addEventListener('click', async () => {
          if (children.childElementCount === 0) {
            await renderDirectory(children, d.path, depth + 1);
          }
          children.classList.toggle('hidden');
        });
        row.appendChild(btn);
        dirEl.appendChild(row);
        dirEl.appendChild(children);
      });

      (data.files || []).forEach(f => {
        const row = document.createElement('div');
        row.className = 'pl-' + (depth * 2) + ' flex items-center gap-2';
        const link = document.createElement('button');
        link.className = 'text-left hover:underline';
        link.textContent = '📄 ' + f.name;
        link.addEventListener('click', () => openFile(f.path));
        const badge = document.createElement('span');
        badge.className = 'text-[10px] text-gray-500';
        badge.textContent = f.path.endsWith('.py') ? 'py' : f.path.endsWith('.js') ? 'js' : '';
        row.appendChild(link);
        if (badge.textContent) row.appendChild(badge);
        dirEl.appendChild(row);
      });

      parentEl.appendChild(dirEl);
    } catch (e) { log(e.message); }
  }

  async function openFile(path) {
    try {
      const data = await fetchJSON('/api/code/file?path=' + encodeURIComponent(path));
      if (cm) cm.setValue(data.content || ''); else editorTA().value = data.content || '';
      editorPath().textContent = path;
      editorTA().dataset.path = path;
      setModeByPath(path);
    } catch (e) { log(e.message); }
  }

  async function saveFile() {
    const path = editorTA().dataset.path;
    if (!path) return log('No file selected');
    try {
      await fetchJSON('/api/code/file', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path, content: cm ? cm.getValue() : editorTA().value }) });
      log('Saved ' + path);
    } catch (e) { log(e.message); }
  }

  async function runFile() {
    const path = editorTA().dataset.path;
    if (!path) return log('No file selected');
    if (path.endsWith('.py')) {
      try {
        const result = await fetchJSON('/api/code/run', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path }) });
        if (result.stdout) log(result.stdout);
        if (result.stderr) log(result.stderr);
        log('Exit code: ' + result.code);
      } catch (e) { log(e.message); }
    } else if (path.endsWith('.js')) {
      try {
        const code = cm ? cm.getValue() : editorTA().value;
        const script = document.createElement('script');
        script.type = 'text/javascript';
        script.textContent = code;
        document.body.appendChild(script);
        log('Executed JS in browser context');
      } catch (e) { log(e.message); }
    } else {
      log('Run supports .py (server) and .js (client) files');
    }
  }

  async function newFile() {
    const name = prompt('Enter file path (e.g., js/main.js or py/task.py):');
    if (!name) return;
    try {
      await fetchJSON('/api/code/file', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path: name, content: '' }) });
      treeEl().innerHTML = '';
      await loadTree();
      await openFile(name);
    } catch (e) { log(e.message); }
  }

  async function deleteFile() {
    const path = editorTA().dataset.path;
    if (!path) return log('No file selected');
    if (!confirm('Delete ' + path + '?')) return;
    try {
      await fetchJSON('/api/code/file?path=' + encodeURIComponent(path), { method: 'DELETE' });
      if (cm) cm.setValue(''); else editorTA().value = '';
      editorPath().textContent = 'No file selected';
      editorTA().dataset.path = '';
      treeEl().innerHTML = '';
      await loadTree();
      log('Deleted ' + path);
    } catch (e) { log(e.message); }
  }

  function clearConsole() { consoleEl().textContent = ''; }

  document.addEventListener('DOMContentLoaded', function () {
    // Initialize CodeMirror
    if (window.CodeMirror) {
      cm = CodeMirror.fromTextArea(editorTA(), {
        lineNumbers: true,
        theme: 'neo',
        indentUnit: 2,
        tabSize: 2,
        lineWrapping: true,
      });
      cm.setSize('100%', '60vh');
    }
    document.getElementById('save-file').addEventListener('click', saveFile);
    document.getElementById('run-file').addEventListener('click', runFile);
    document.getElementById('new-file').addEventListener('click', newFile);
    document.getElementById('delete-file').addEventListener('click', deleteFile);
    document.getElementById('clear-console').addEventListener('click', clearConsole);
    loadTree().then(async () => {
      const params = new URLSearchParams(window.location.search);
      const p = params.get('path');
      if (p) {
        try { await openFile(p); } catch (e) { log(e.message); }
      }
    });
  });
})();
