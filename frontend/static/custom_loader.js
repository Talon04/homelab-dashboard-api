/**
 * =============================================================================
 * CUSTOM_LOADER.JS - User script injection
 * =============================================================================
 * 
 * Injects user-provided custom JS and CSS from the Code Editor module
 * into configured pages, enabling dashboard customisation.
 */

// custom_loader.js - injects user-provided JS/CSS from Code Editor module
(function () {
  function currentPage() {
    const p = window.location.pathname;
    if (p.startsWith('/containers')) return 'containers';
    if (p.startsWith('/proxmox')) return 'proxmox';
    return 'settings';
  }
  function injectCSS(css) {
    if (!css) return;
    const style = document.createElement('style');
    style.type = 'text/css';
    style.textContent = css;
    document.head.appendChild(style);
  }
  function injectJS(js) {
    if (!js) return;
    const script = document.createElement('script');
    script.type = 'text/javascript';
    script.textContent = js;
    document.body.appendChild(script);
  }
  async function load() {
    try {
      const modsRes = await fetch('/api/config/modules');
      if (!modsRes.ok) return;
      const mods = (await modsRes.json()).modules || [];
      if (!mods.includes('code_editor')) return;
      const cfgRes = await fetch('/api/config/module/code_editor');
      if (!cfgRes.ok) return;
      const cfg = await cfgRes.json();
      const pages = Array.isArray(cfg.pages) ? cfg.pages : [];
      if (!pages.includes(currentPage())) return;
      injectCSS(cfg.custom_css || '');
      injectJS(cfg.custom_js || '');
    } catch (e) { }
  }
  document.addEventListener('DOMContentLoaded', load);
})();
