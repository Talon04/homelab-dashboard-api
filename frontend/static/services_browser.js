// Simple service browser: list, create, delete and drag services into the canvas.

async function fetchServices() {
  const res = await fetch('/api/services');
  if (!res.ok) return [];
  return res.json();
}

async function createService(name) {
  const res = await fetch('/api/services', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  });
  return res.ok ? res.json() : null;
}

async function deleteService(id) {
  const res = await fetch('/api/services/' + id, { method: 'DELETE' });
  return res.ok;
}

function makeServiceItem(s) {
  const el = document.createElement('div');
  el.className = 'bg-gray-50 border border-gray-200 rounded p-2 mb-2 cursor-grab';
  el.draggable = true;
  el.dataset.serviceId = s.id;
  el.innerHTML = `<div class="flex justify-between items-center"><div class="font-medium">${s.name}</div><button class="text-sm text-red-600">Delete</button></div>`;

  el.addEventListener('dragstart', (ev) => {
    const dragData = { type: 'service', id: s.id };
    console.log('Service dragged:', dragData);
    ev.dataTransfer.setData('text/plain', JSON.stringify(dragData));
    ev.dataTransfer.effectAllowed = 'copy';
  });

  el.addEventListener('click', (ev) => {
    const evDetail = { id: s.id, name: s.name };
    console.log('Service clicked:', evDetail);
    // Select service and notify editor
    window.dispatchEvent(new CustomEvent('service-selected', { detail: evDetail }));
    // visually mark selected
    document.querySelectorAll('#services-list .selected').forEach(n => n.classList.remove('selected'));
    el.classList.add('selected');
  });

  const btn = el.querySelector('button');
  btn.addEventListener('click', async (e) => {
    e.stopPropagation();
    if (!confirm('Delete service "' + s.name + '"?')) return;
    const ok = await deleteService(s.id);
    if (ok) render();
    else alert('Failed to delete');
  });

  return el;
}

async function render() {
  const root = document.getElementById('services-sidebar');
  if (!root) return;
  root.innerHTML = '';

  const header = document.createElement('div');
  header.className = 'mb-3';
  header.innerHTML = `
    <div class="flex items-center justify-between">
      <h3 class="font-semibold">Services</h3>
      <button id="create-service-btn" class="text-sm text-blue-600">New</button>
    </div>
    <div class="text-xs text-gray-500 mt-1">Drag a service into the canvas to instantiate an element.</div>
  `;
  root.appendChild(header);

  const list = document.createElement('div');
  list.id = 'services-list';
  root.appendChild(list);

  document.getElementById('create-service-btn').addEventListener('click', async () => {
    const name = prompt('Service name:');
    if (!name) return;
    const s = await createService(name);
    if (s) render();
    else alert('Failed to create service');
  });

  const services = await fetchServices();
  services.forEach((s) => {
    list.appendChild(makeServiceItem(s));
  });
}

// Initialize
window.addEventListener('DOMContentLoaded', () => {
  render();
});

// Refresh list when a service is saved
window.addEventListener('services-updated', () => {
  render();
});
