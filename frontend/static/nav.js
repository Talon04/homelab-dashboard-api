/**
 * =============================================================================
 * NAV.JS - Dynamic navigation arrows
 * =============================================================================
 * 
 * Manages navigation arrows based on enabled modules and their display order.
 * Provides circular navigation between pages.
 */

// nav.js - dynamic navigation arrows based on enabled modules and order
(function () {
  function $(id) { return document.getElementById(id); }
  function setLink(anchor, href, label) {
    if (!anchor) return;
    if (!href) {
      anchor.classList.add('hidden');
      return;
    }
    anchor.href = href;
    anchor.classList.remove('hidden');
    if (anchor.id === 'nav-left-link' || anchor.id === 'nav-right-link') {
      anchor.textContent = label || '';
    }
  }

  async function loadModules() {
    try {
      const [modsRes, orderRes] = await Promise.all([
        fetch('/api/config/modules'),
        fetch('/api/config/modules_order')
      ]);
      const enabled = modsRes.ok ? (await modsRes.json()).modules || [] : [];
      const order = orderRes.ok ? (await orderRes.json()).order || [] : [];
      const enabledOrdered = order.filter(id => enabled.includes(id));
      return { enabled, order, enabledOrdered };
    } catch (e) {
      return { enabled: [], order: [], enabledOrdered: [] };
    }
  }

  function mapModule(id) {
    switch (id) {
      case 'containers': return { href: '/containers', label: 'Containers' };
      case 'proxmox': return { href: '/proxmox', label: 'Proxmox' };
      case 'code_editor': return { href: '/code', label: 'Code' };
      case 'monitor': return { href: '/monitor', label: 'Monitor' };
      default: return null;
    }
  }

  function mapPage(id) {
    if (id === 'settings') return { href: '/settings', label: 'Settings' };
    return mapModule(id);
  }

  function computeNav(current, enabledOrdered) {
    const left = { href: null, label: null };
    const right = { href: null, label: null };

    const pages = ['settings', ...enabledOrdered];
    if (!pages.length) {
      return { left, right };
    }

    const idx = pages.indexOf(current);
    if (idx === -1) {
      // Fallback: treat as settings
      const settingsPage = mapPage('settings');
      left.href = settingsPage.href; left.label = settingsPage.label;
      right.href = settingsPage.href; right.label = settingsPage.label;
      return { left, right };
    }

    const prevId = pages[(idx - 1 + pages.length) % pages.length];
    const nextId = pages[(idx + 1) % pages.length];

    const prev = mapPage(prevId);
    const next = mapPage(nextId);

    if (prev) {
      left.href = prev.href;
      left.label = prev.label;
    }
    if (next) {
      right.href = next.href;
      right.label = next.label;
    }

    return { left, right };
  }

  function detectCurrent() {
    const path = window.location.pathname;
    if (path.startsWith('/containers')) return 'containers';
    if (path.startsWith('/proxmox')) return 'proxmox';
    if (path.startsWith('/code')) return 'code_editor';
    if (path.startsWith('/monitor')) return 'monitor';
    return 'settings';
  }

  document.addEventListener('DOMContentLoaded', async function () {
    const { enabledOrdered } = await loadModules();
    const current = detectCurrent();
    const nav = computeNav(current, enabledOrdered);

    setLink($('nav-left-arrow'), nav.left.href, nav.left.label);
    setLink($('nav-left-link'), nav.left.href, nav.left.label);
    setLink($('nav-right-link'), nav.right.href, nav.right.label);
    setLink($('nav-right-arrow'), nav.right.href, nav.right.label);
  });
})();
