// nav.js - dynamic navigation arrows based on enabled modules and order
(function(){
  function $(id){ return document.getElementById(id); }
  function setLink(anchor, href, label){
    if (!anchor) return;
    if (!href){
      anchor.classList.add('hidden');
      return;
    }
    anchor.href = href;
    anchor.classList.remove('hidden');
    if (anchor.id === 'nav-left-link' || anchor.id === 'nav-right-link') {
      anchor.textContent = label || '';
    }
  }

  async function loadModules(){
    try {
      const [modsRes, orderRes] = await Promise.all([
        fetch('/api/config/modules'),
        fetch('/api/config/modules_order')
      ]);
      const enabled = modsRes.ok ? (await modsRes.json()).modules || [] : [];
      const order = orderRes.ok ? (await orderRes.json()).order || [] : [];
      const enabledOrdered = order.filter(id => enabled.includes(id));
      return { enabled, order, enabledOrdered };
    } catch(e){
      return { enabled: [], order: [], enabledOrdered: [] };
    }
  }

  function mapModule(id){
    switch(id){
      case 'containers': return { href: '/containers', label: 'Containers' };
      case 'proxmox': return { href: '/proxmox', label: 'Proxmox' };
      case 'code_editor': return { href: '/code', label: 'Code' };
      default: return null;
    }
  }

  function computeNav(current, enabledOrdered){
    const left = { href: null, label: null };
    const right = { href: null, label: null };

    if (current === 'settings'){
      if (enabledOrdered.length){
        const first = mapModule(enabledOrdered[0]);
        const last = mapModule(enabledOrdered[enabledOrdered.length - 1]);
        if (last){ left.href = last.href; left.label = last.label; }
        if (first){ right.href = first.href; right.label = first.label; }
      }
      return { left, right };
    }

    const idx = enabledOrdered.indexOf(current);
    if (idx === -1){
      // fallback: settings both sides
      left.href = '/settings'; left.label = 'Settings';
      right.href = '/settings'; right.label = 'Settings';
      return { left, right };
    }
    const prevId = enabledOrdered[idx - 1];
    const nextId = enabledOrdered[idx + 1];

    if (prevId){
      const prev = mapModule(prevId);
      if (prev){ left.href = prev.href; left.label = prev.label; }
    } else {
      left.href = '/settings'; left.label = 'Settings';
    }

    if (nextId){
      const next = mapModule(nextId);
      if (next){ right.href = next.href; right.label = next.label; }
    } else {
      right.href = '/settings'; right.label = 'Settings';
    }

    return { left, right };
  }

  function detectCurrent(){
    const path = window.location.pathname;
    if (path.startsWith('/containers')) return 'containers';
    if (path.startsWith('/proxmox')) return 'proxmox';
    return 'settings';
  }

  document.addEventListener('DOMContentLoaded', async function(){
    const { enabledOrdered } = await loadModules();
    const current = detectCurrent();
    const nav = computeNav(current, enabledOrdered);

    setLink($('nav-left-arrow'), nav.left.href, nav.left.label);
    setLink($('nav-left-link'), nav.left.href, nav.left.label);
    setLink($('nav-right-link'), nav.right.href, nav.right.label);
    setLink($('nav-right-arrow'), nav.right.href, nav.right.label);
  });
})();
