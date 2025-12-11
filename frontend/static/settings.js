let currentSettings = {};

window.addEventListener("DOMContentLoaded", async () => {
  await loadSettings();

  // Event listeners
  document.getElementById("save-settings").addEventListener("click", saveSettings);
  document.getElementById("complete-setup").addEventListener("click", completeSetup);
  document.getElementById("reset-settings").addEventListener("click", resetSettings);
});

async function loadSettings() {
  try {
    // Load modules enabled + order and render list
    await loadModulesUI();
    // Update nav based on current modules
    try {
      const res = await fetch('/api/config/modules');
      if (res.ok) {
        const data = await res.json();
        updateNavFromModules(Array.isArray(data.modules) ? data.modules : []);
      }
    } catch (e) { }

    // Check if this is first boot
    const firstBootRes = await fetch("/api/config/first_boot");
    const firstBootData = await firstBootRes.json();

    if (firstBootData.first_boot) {
      document.getElementById("first-boot-banner").classList.remove("hidden");
    }

    // Load internal IP configuration
    const internalIpRes = await fetch("/api/config/internal_ip");
    const internalIpData = await internalIpRes.json();

    // Load external IP configuration
    const externalIpRes = await fetch("/api/config/external_ip");
    const externalIpData = await externalIpRes.json();

    // Load proxy configuration
    const proxyRes = await fetch("/api/config/proxy_count");
    const proxyData = await proxyRes.json();

    document.getElementById("internal-ip").value = internalIpData.internal_ip || "127.0.0.1";
    document.getElementById("external-ip").value = externalIpData.external_ip || "127.0.0.1";
    document.getElementById("proxy-count").value = proxyData.proxy_count || 0;

    // Store current settings
    currentSettings = {
      internal_ip: internalIpData.internal_ip || "127.0.0.1",
      external_ip: externalIpData.external_ip || "127.0.0.1",
      proxy_count: proxyData.proxy_count || 0
    };

  } catch (err) {
    console.error("Failed to load settings:", err);
    showStatus("Failed to load current settings", "error");
  }
}

async function saveSettings() {
  try {
    console.log("Saving settings...");
    const internalIp = document.getElementById("internal-ip").value.trim();
    const externalIp = document.getElementById("external-ip").value.trim();
    const proxyCount = parseInt(document.getElementById("proxy-count").value) || 0;

    // Validate inputs
    if (!isValidIP(internalIp)) {
      showStatus("Invalid internal IP address", "error");
      return;
    }

    if (!isValidIP(externalIp)) {
      showStatus("Invalid external IP address", "error");
      return;
    }

    if (proxyCount < 0) {
      showStatus("Proxy count cannot be negative", "error");
      return;
    }

    // Save internal IP
    const internalRes = await fetch("/api/config/internal_ip", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        internal_ip: internalIp
      })
    });

    if (!internalRes.ok) {
      throw new Error("Failed to save internal IP");
    }

    // Save external IP
    const externalRes = await fetch("/api/config/external_ip", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        external_ip: externalIp
      })
    });

    if (!externalRes.ok) {
      throw new Error("Failed to save external IP");
    }

    // Save proxy count
    const proxyRes = await fetch("/api/config/proxy_count", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        proxy_count: proxyCount
      })
    });

    if (!proxyRes.ok) {
      throw new Error("Failed to save proxy settings");
    }

    // Save module configuration (enabled + order + per-module configs)
    await saveModules();

    // Update current settings
    currentSettings = {
      internal_ip: internalIp,
      external_ip: externalIp,
      proxy_count: proxyCount
    };

    showStatus("Settings and modules saved successfully!", "success");

  } catch (err) {
    console.error("Failed to save settings:", err);
    showStatus("Failed to save settings: " + err.message, "error");
  }
}

async function completeSetup() {
  try {
    // First save current settings
    await saveSettings();

    // Then set first_boot to false
    const res = await fetch("/api/config/first_boot", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        first_boot: false
      })
    });

    if (!res.ok) {
      throw new Error("Failed to complete setup");
    }

    showStatus("Setup completed successfully! Redirecting to dashboard...", "success");

    // Redirect to dashboard after a short delay
    setTimeout(() => {
      window.location.href = "/containers";
    }, 2000);

  } catch (err) {
    console.error("Failed to complete setup:", err);
    showStatus("Failed to complete setup: " + err.message, "error");
  }
}

async function saveModules() {
  const state = getModulesStateFromUI();
  // Save enabled list
  const res = await fetch("/api/config/modules", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ modules: state.enabled })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || "Failed to save modules");
  }
  // Save order
  const res2 = await fetch("/api/config/modules_order", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ order: state.order })
  });
  if (!res2.ok) {
    const err2 = await res2.json().catch(() => ({}));
    throw new Error(err2.error || "Failed to save modules order");
  }
  // Save per-module configs
  for (const [mid, cfg] of Object.entries(state.configs || {})) {
    const resCfg = await fetch(`/api/config/module/${mid}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(cfg)
    });
    if (!resCfg.ok) {
      const e3 = await resCfg.json().catch(() => ({}));
      throw new Error(e3.error || `Failed to save config for ${mid}`);
    }
  }
  updateNavFromModules(state.enabled);
}

async function loadModulesUI() {
  const list = document.getElementById('modules-list');
  if (!list) return;
  const available = [
    { id: 'containers', label: 'Containers' },
    {
      id: 'proxmox', label: 'Proxmox VMs', config: {
        api_url: { label: 'API URL', type: 'text', placeholder: 'https://host:8006/api2/json' },
        token_id: { label: 'Token ID', type: 'text', placeholder: 'root@pam!mytoken' },
        token_secret: { label: 'Token Secret', type: 'password', placeholder: '********' },
        verify_ssl: { label: 'Verify SSL', type: 'checkbox' },
        node: { label: 'Node (optional)', type: 'text', placeholder: 'pve' }
      }
    },
    { id: 'code_editor', label: 'Code Editor' }
  ];
  let enabled = ["containers"];
  let order = ["containers"];
  try {
    const [modsRes, orderRes] = await Promise.all([
      fetch('/api/config/modules'),
      fetch('/api/config/modules_order')
    ]);
    if (modsRes.ok) {
      const data = await modsRes.json();
      if (Array.isArray(data.modules)) enabled = data.modules;
    }
    if (orderRes.ok) {
      const data2 = await orderRes.json();
      if (Array.isArray(data2.order) && data2.order.length) order = data2.order;
    }
  } catch (e) {
    // keep defaults
  }
  // Render according to order
  list.innerHTML = '';
  const byId = Object.fromEntries(available.map(m => [m.id, m]));
  const ordered = order.filter(id => byId[id]).concat(available.map(m => m.id).filter(id => !order.includes(id)));
  for (let idx = 0; idx < ordered.length; idx++) {
    const id = ordered[idx];
    const meta = byId[id];
    // Card that holds the row + optional config so they move together
    const card = document.createElement('div');
    card.className = 'flex flex-col items-start gap-2 border border-gray-200 rounded-md px-3 py-2 bg-gray-50 min-w-[180px]';
    card.dataset.moduleId = id;

    const row = document.createElement('div');
    row.className = 'flex items-center gap-3';
    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.className = 'h-4 w-4';
    checkbox.checked = enabled.includes(id);
    const label = document.createElement('span');
    label.textContent = meta.label;
    const up = document.createElement('button');
    up.type = 'button';
    up.className = 'px-2 py-1 text-sm bg-gray-100 rounded hover:bg-gray-200 module-move-btn';
    up.textContent = '<';
    up.disabled = idx === 0;
    up.addEventListener('click', () => moveModule(card, -1));
    const down = document.createElement('button');
    down.type = 'button';
    down.className = 'px-2 py-1 text-sm bg-gray-100 rounded hover:bg-gray-200 module-move-btn';
    down.textContent = '>';
    down.disabled = idx === ordered.length - 1;
    down.addEventListener('click', () => moveModule(card, +1));
    row.appendChild(checkbox);
    row.appendChild(label);
    row.appendChild(up);
    row.appendChild(down);
    card.appendChild(row);

    // Configuration panel per module (if defined)
    if (meta.config) {
      const details = document.createElement('details');
      details.className = 'w-full';
      const summary = document.createElement('summary');
      summary.className = 'cursor-pointer select-none text-gray-600';
      summary.textContent = `Configure ${meta.label}`;
      details.appendChild(summary);
      const panel = document.createElement('div');
      panel.className = 'mt-3 grid grid-cols-1 md:grid-cols-2 gap-3';

      // Load module config
      let modConfig = {};
      try {
        const resp = await fetch(`/api/config/module/${id}`);
        if (resp.ok) modConfig = await resp.json();
      } catch (e) { }

      for (const [key, field] of Object.entries(meta.config)) {
        const wrap = document.createElement('div');
        const lab = document.createElement('label');
        lab.className = 'block text-sm text-gray-700 mb-1';
        lab.textContent = field.label;
        wrap.appendChild(lab);
        let input;
        if (field.type === 'checkbox') {
          input = document.createElement('input');
          input.type = 'checkbox';
          input.className = 'h-4 w-4';
          input.checked = Boolean(modConfig[key] ?? (key === 'verify_ssl' ? true : false));
        } else {
          input = document.createElement('input');
          input.type = field.type || 'text';
          input.className = 'w-full px-3 py-2 border border-gray-300 rounded-md';
          if (field.placeholder) input.placeholder = field.placeholder;
          input.value = String(modConfig[key] ?? '');
        }
        input.dataset.moduleId = id;
        input.dataset.configKey = key;
        wrap.appendChild(input);
        panel.appendChild(wrap);
      }
      details.appendChild(panel);
      card.appendChild(details);
    }
    list.appendChild(card);
  }
}

function moveModule(rowEl, delta) {
  const parent = rowEl.parentElement;
  if (!parent) return;
  const nodes = Array.from(parent.children);
  const idx = nodes.indexOf(rowEl);
  const newIdx = idx + delta;
  if (newIdx < 0 || newIdx >= nodes.length) return;
  parent.insertBefore(rowEl, delta < 0 ? nodes[newIdx] : nodes[newIdx].nextSibling);
  // Update disabled states
  Array.from(parent.children).forEach((el, i) => {
    const buttons = el.querySelectorAll('.module-move-btn');
    if (buttons.length === 2) {
      buttons[0].disabled = i === 0;
      buttons[1].disabled = i === parent.children.length - 1;
    }
  });
}

function getModulesStateFromUI() {
  const list = document.getElementById('modules-list');
  const rows = Array.from(list ? list.querySelectorAll('div[data-module-id]') : []);
  const order = rows.map(el => el.dataset.moduleId);
  const enabled = rows.filter(el => el.querySelector('input[type="checkbox"]').checked).map(el => el.dataset.moduleId);
  // Collect per-module configs
  const configs = {};
  const inputs = Array.from(list ? list.querySelectorAll('[data-module-id][data-config-key]') : []);
  inputs.forEach(inp => {
    const mid = inp.dataset.moduleId;
    const key = inp.dataset.configKey;
    const val = inp.type === 'checkbox' ? inp.checked : inp.value;
    if (!configs[mid]) configs[mid] = {};
    configs[mid][key] = val;
  });
  return { order, enabled, configs };
}

function updateNavFromModules(enabled) {
  const showContainers = Array.isArray(enabled) && enabled.includes('containers');
  document.querySelectorAll('a[href="/containers"]').forEach(el => {
    if (showContainers) {
      el.classList.remove('hidden');
    } else {
      el.classList.add('hidden');
    }
  });
}

async function resetSettings() {
  if (!confirm("Are you sure you want to reset all settings to defaults?")) {
    return;
  }

  try {
    // Reset internal IP to default
    const internalRes = await fetch("/api/config/internal_ip", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        internal_ip: "127.0.0.1"
      })
    });

    if (!internalRes.ok) {
      throw new Error("Failed to reset internal IP");
    }

    // Reset external IP to default
    const externalRes = await fetch("/api/config/external_ip", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        external_ip: "127.0.0.1"
      })
    });

    if (!externalRes.ok) {
      throw new Error("Failed to reset external IP");
    }

    // Reset proxy count to 0
    const proxyRes = await fetch("/api/config/proxy_count", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        proxy_count: 0
      })
    });

    if (!proxyRes.ok) {
      throw new Error("Failed to reset proxy settings");
    }

    // Reset form values
    document.getElementById("internal-ip").value = "127.0.0.1";
    document.getElementById("external-ip").value = "127.0.0.1";
    document.getElementById("proxy-count").value = 0;

    currentSettings = {
      internal_ip: "127.0.0.1",
      external_ip: "127.0.0.1",
      proxy_count: 0
    };

    showStatus("Settings reset to defaults", "success");

  } catch (err) {
    console.error("Failed to reset settings:", err);
    showStatus("Failed to reset settings: " + err.message, "error");
  }
}

function isValidIP(ip) {
  // Basic IP validation (IPv4)
  const ipRegex = /^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$/;
  return ipRegex.test(ip) || ip === "localhost";
}

function showStatus(message, type) {
  const statusDiv = document.getElementById("status-message");
  const statusText = document.getElementById("status-text");

  statusText.textContent = message;

  // Remove old classes
  statusDiv.classList.remove("hidden", "bg-green-100", "text-green-700", "bg-red-100", "text-red-700");

  // Add new classes based on type
  if (type === "success") {
    statusDiv.classList.add("bg-green-100", "text-green-700");
  } else if (type === "error") {
    statusDiv.classList.add("bg-red-100", "text-red-700");
  }

  statusDiv.classList.remove("hidden");

  // Auto-hide after 5 seconds
  setTimeout(() => {
    statusDiv.classList.add("hidden");
  }, 5000);
}
