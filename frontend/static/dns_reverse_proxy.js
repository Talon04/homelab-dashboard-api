// =============================================================================
// DNS_REVERSE_PROXY.JS - DNS and reverse proxy mapping table UI
// =============================================================================

(function () {
  const defaultOptions = {
    reverse_proxy: {
      hostname_mode: 'route_host',
      include_wildcards: false,
      normalize_hostnames: true,
      skip_tls_verify: false,
    },
    dns: {
      hostname_mode: 'host_plus_domain',
      include_wildcards: false,
      include_disabled: false,
      normalize_hostnames: true,
    },
  };

  let moduleConfig = null;
  let currentEditAction = null;

  async function loadMappings() {
    const statusEl = document.getElementById('dns-rp-status');
    const bodyEl = document.getElementById('dns-rp-table-body');
    if (!statusEl || !bodyEl) return;

    statusEl.textContent = 'Loading mappings...';
    bodyEl.innerHTML = '';

    try {
      const res = await fetch('/api/dns-reverse-proxy/mappings');
      if (!res.ok) {
        throw new Error('Failed to fetch mappings');
      }
      const data = await res.json();
      const rows = Array.isArray(data.rows) ? data.rows : [];

      if (!rows.length) {
        statusEl.textContent = 'No mapping rows found. Verify module API settings in Settings.';
        return;
      }

      rows.forEach((row) => {
        const tr = document.createElement('tr');

        const statusClass =
          row.status === 'matched'
            ? 'bg-green-100 text-green-800'
            : row.status === 'missing_dns'
              ? 'bg-yellow-100 text-yellow-800'
              : 'bg-red-100 text-red-800';

        const dnsText = row.dns_value
          ? `${row.dns_record_type || ''} ${row.dns_value}`.trim()
          : '-';
        const rpText = row.reverse_proxy_target || '-';

        const actionsHtml = `
          <div class="flex items-center gap-2">
            <button class="dns-rp-action-edit-rp px-2 py-1 text-xs border border-gray-300 rounded ${row.has_reverse_proxy ? 'hover:bg-gray-50' : 'opacity-50 cursor-not-allowed'}" ${row.has_reverse_proxy ? '' : 'disabled'}>Edit RP</button>
            <button class="dns-rp-action-edit-dns px-2 py-1 text-xs border border-gray-300 rounded ${row.has_dns ? 'hover:bg-gray-50' : 'opacity-50 cursor-not-allowed'}" ${row.has_dns ? '' : 'disabled'}>Edit DNS</button>
            <button class="dns-rp-action-delete px-2 py-1 text-xs border border-red-300 text-red-700 rounded hover:bg-red-50" title="Delete reverse proxy + DNS">&#128465;</button>
          </div>
        `;

        tr.innerHTML = `
          <td class="px-4 py-2 text-sm text-gray-900">${escapeHtml(row.hostname || '-')}</td>
          <td class="px-4 py-2 text-sm text-gray-700">${escapeHtml(rpText)}</td>
          <td class="px-4 py-2 text-sm text-gray-700">${escapeHtml(dnsText)}</td>
          <td class="px-4 py-2 text-sm">
            <span class="px-2 py-1 rounded-full text-xs font-medium ${statusClass}">${escapeHtml((row.status || 'unknown').replaceAll('_', ' '))}</span>
          </td>
          <td class="px-4 py-2 text-sm">${actionsHtml}</td>
        `;

        const editRpBtn = tr.querySelector('.dns-rp-action-edit-rp');
        const editDnsBtn = tr.querySelector('.dns-rp-action-edit-dns');
        const deleteBtn = tr.querySelector('.dns-rp-action-delete');

        if (editRpBtn) {
          editRpBtn.addEventListener('click', () => openEditModal('reverse_proxy', row));
        }
        if (editDnsBtn) {
          editDnsBtn.addEventListener('click', () => openEditModal('dns', row));
        }
        if (deleteBtn) {
          deleteBtn.addEventListener('click', () => deleteMapping(row));
        }

        bodyEl.appendChild(tr);
      });

      statusEl.textContent = `Loaded ${rows.length} mapping row(s).`;
    } catch (err) {
      statusEl.textContent = `Failed to load mappings: ${err.message}`;
    }
  }

  function escapeHtml(value) {
    return String(value)
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  async function loadModuleConfig() {
    const res = await fetch('/api/config/module/dns_reverse_proxy');
    if (!res.ok) {
      throw new Error('Failed to load DNS/Proxy module config');
    }
    const cfg = await res.json();
    moduleConfig = (cfg && typeof cfg === 'object') ? cfg : {};
    if (!moduleConfig.mapping_options || typeof moduleConfig.mapping_options !== 'object') {
      moduleConfig.mapping_options = JSON.parse(JSON.stringify(defaultOptions));
    }
    moduleConfig.mapping_options.reverse_proxy = {
      ...defaultOptions.reverse_proxy,
      ...(moduleConfig.mapping_options.reverse_proxy || {}),
    };
    moduleConfig.mapping_options.dns = {
      ...defaultOptions.dns,
      ...(moduleConfig.mapping_options.dns || {}),
    };
  }

  async function saveMappingOptions() {
    if (!moduleConfig) return;
    const res = await fetch('/api/config/module/dns_reverse_proxy', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        mapping_options: moduleConfig.mapping_options,
      }),
    });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(text || 'Failed to save mapping options');
    }
  }

  function openModal(modalEl) {
    modalEl.classList.remove('hidden');
    modalEl.classList.add('flex');
  }

  function closeModal(modalEl) {
    modalEl.classList.remove('flex');
    modalEl.classList.add('hidden');
  }

  async function deleteMapping(row) {
    const hostname = String(row.hostname || '').trim();
    if (!hostname) return;
    const confirmed = window.confirm(`Delete reverse proxy and DNS entries for ${hostname}?`);
    if (!confirmed) return;

    try {
      const res = await fetch('/api/dns-reverse-proxy/mappings/action/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ hostname }),
      });
      const data = await res.json();
      if (!res.ok || !data.ok) {
        throw new Error(data.error || 'Delete failed');
      }
      await loadMappings();
    } catch (err) {
      alert(`Delete failed: ${err.message}`);
    }
  }

  function parseDial(dial) {
    const value = String(dial || '').trim();
    if (!value) return { target_protocol: 'http', target_host: '', target_port: 80 };
    const idx = value.lastIndexOf(':');
    if (idx > 0) {
      const host = value.slice(0, idx);
      const port = Number(value.slice(idx + 1)) || 80;
      return {
        target_protocol: port === 443 ? 'https' : 'http',
        target_host: host,
        target_port: port,
      };
    }
    return { target_protocol: 'http', target_host: value, target_port: 80 };
  }

  function openEditModal(kind, row) {
    const modal = document.getElementById('dns-rp-edit-modal');
    const title = document.getElementById('dns-rp-edit-title');
    const desc = document.getElementById('dns-rp-edit-description');
    const payloadEl = document.getElementById('dns-rp-edit-payload');
    if (!modal || !title || !desc || !payloadEl) return;

    const hostname = String(row.hostname || '').trim();
    if (kind === 'reverse_proxy') {
      const parsed = parseDial(row.reverse_proxy_target);
      title.textContent = 'Edit Reverse Proxy Mapping';
      desc.textContent = 'Edit this JSON payload and click Save.';
      payloadEl.value = JSON.stringify(
        {
          hostname,
          target_protocol: parsed.target_protocol,
          target_host: parsed.target_host,
          target_port: parsed.target_port,
        },
        null,
        2,
      );
      currentEditAction = { endpoint: '/api/dns-reverse-proxy/mappings/action/edit-reverse-proxy' };
    } else {
      title.textContent = 'Edit DNS Mapping';
      desc.textContent = 'Edit this JSON payload and click Save.';
      payloadEl.value = JSON.stringify(
        {
          hostname,
          record_type: row.dns_record_type || 'A',
          record_value: row.dns_value || '',
        },
        null,
        2,
      );
      currentEditAction = { endpoint: '/api/dns-reverse-proxy/mappings/action/edit-dns' };
    }

    openModal(modal);
  }

  function bindEditModalUi() {
    const modal = document.getElementById('dns-rp-edit-modal');
    const closeBtn = document.getElementById('dns-rp-edit-close');
    const cancelBtn = document.getElementById('dns-rp-edit-cancel');
    const saveBtn = document.getElementById('dns-rp-edit-save');
    const payloadEl = document.getElementById('dns-rp-edit-payload');
    if (!modal || !closeBtn || !cancelBtn || !saveBtn || !payloadEl) return;

    [closeBtn, cancelBtn].forEach((btn) => btn.addEventListener('click', () => closeModal(modal)));

    saveBtn.addEventListener('click', async () => {
      if (!currentEditAction) return;
      let payload;
      try {
        payload = JSON.parse(payloadEl.value);
      } catch (err) {
        alert(`Invalid JSON: ${err.message}`);
        return;
      }

      try {
        const res = await fetch(currentEditAction.endpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (!res.ok || !data.ok) {
          throw new Error(data.error || 'Save failed');
        }
        closeModal(modal);
        await loadMappings();
      } catch (err) {
        alert(`Save failed: ${err.message}`);
      }
    });
  }

  function bindProviderConfigUi() {
    const rpBtn = document.getElementById('dns-rp-rp-config');
    const dnsBtn = document.getElementById('dns-rp-dns-config');

    const rpModal = document.getElementById('dns-rp-rp-config-modal');
    const rpClose = document.getElementById('dns-rp-rp-config-close');
    const rpCancel = document.getElementById('dns-rp-rp-config-cancel');
    const rpSave = document.getElementById('dns-rp-rp-config-save');
    const rpText = document.getElementById('dns-rp-rp-config-text');

    if (rpBtn && rpModal && rpClose && rpCancel && rpSave && rpText) {
      rpBtn.addEventListener('click', async () => {
        try {
          const res = await fetch('/api/dns-reverse-proxy/provider/reverse-proxy/config');
          const data = await res.json();
          if (!res.ok || !data.ok) {
            throw new Error(data.error || 'Failed to load reverse proxy config');
          }
          rpText.value = data.config_text || '{}';
          rpText.placeholder = 'Caddyfile-style reverse proxy blocks';
          openModal(rpModal);
        } catch (err) {
          alert(`Reverse proxy config failed: ${err.message}`);
        }
      });

      [rpClose, rpCancel].forEach((btn) => btn.addEventListener('click', () => closeModal(rpModal)));

      rpSave.addEventListener('click', async () => {
        try {
          const res = await fetch('/api/dns-reverse-proxy/provider/reverse-proxy/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ config_text: rpText.value }),
          });
          const data = await res.json();
          if (!res.ok || !data.ok) {
            throw new Error(data.error || 'Failed to save reverse proxy config');
          }
          closeModal(rpModal);
          await loadMappings();
        } catch (err) {
          alert(`Save reverse proxy config failed: ${err.message}`);
        }
      });
    }

    if (dnsBtn) {
      dnsBtn.addEventListener('click', async () => {
        try {
          const res = await fetch('/api/dns-reverse-proxy/provider/dns/config-link');
          const data = await res.json();
          if (!res.ok || !data.ok || !data.url) {
            throw new Error(data.error || 'Failed to resolve DNS config link');
          }
          window.open(data.url, '_blank', 'noopener');
        } catch (err) {
          alert(`DNS config failed: ${err.message}`);
        }
      });
    }
  }

  function bindSettingsUi() {
    const rpBtn = document.getElementById('dns-rp-rp-settings');
    const dnsBtn = document.getElementById('dns-rp-dns-settings');
    const rpModal = document.getElementById('dns-rp-rp-modal');
    const dnsModal = document.getElementById('dns-rp-dns-modal');

    if (!rpBtn || !dnsBtn || !rpModal || !dnsModal) return;

    const rpHostnameMode = document.getElementById('rp-hostname-mode');
    const rpIncludeWildcards = document.getElementById('rp-include-wildcards');
    const rpNormalizeHostnames = document.getElementById('rp-normalize-hostnames');
    const rpSkipTlsVerify = document.getElementById('rp-skip-tls-verify');

    const dnsHostnameMode = document.getElementById('dns-hostname-mode');
    const dnsIncludeWildcards = document.getElementById('dns-include-wildcards');
    const dnsIncludeDisabled = document.getElementById('dns-include-disabled');
    const dnsNormalizeHostnames = document.getElementById('dns-normalize-hostnames');

    const rpClose = document.getElementById('dns-rp-rp-close');
    const rpCancel = document.getElementById('dns-rp-rp-cancel');
    const rpSave = document.getElementById('dns-rp-rp-save');

    const dnsClose = document.getElementById('dns-rp-dns-close');
    const dnsCancel = document.getElementById('dns-rp-dns-cancel');
    const dnsSave = document.getElementById('dns-rp-dns-save');

    function loadReverseProxyForm() {
      const o = moduleConfig.mapping_options.reverse_proxy;
      rpHostnameMode.value = o.hostname_mode;
      rpIncludeWildcards.checked = !!o.include_wildcards;
      rpNormalizeHostnames.checked = !!o.normalize_hostnames;
      rpSkipTlsVerify.checked = !!o.skip_tls_verify;
    }

    function loadDnsForm() {
      const o = moduleConfig.mapping_options.dns;
      dnsHostnameMode.value = o.hostname_mode;
      dnsIncludeWildcards.checked = !!o.include_wildcards;
      dnsIncludeDisabled.checked = !!o.include_disabled;
      dnsNormalizeHostnames.checked = !!o.normalize_hostnames;
    }

    rpBtn.addEventListener('click', () => {
      loadReverseProxyForm();
      openModal(rpModal);
    });

    dnsBtn.addEventListener('click', () => {
      loadDnsForm();
      openModal(dnsModal);
    });

    [rpClose, rpCancel].forEach((btn) => btn && btn.addEventListener('click', () => closeModal(rpModal)));
    [dnsClose, dnsCancel].forEach((btn) => btn && btn.addEventListener('click', () => closeModal(dnsModal)));

    rpSave.addEventListener('click', async () => {
      moduleConfig.mapping_options.reverse_proxy = {
        hostname_mode: rpHostnameMode.value,
        include_wildcards: rpIncludeWildcards.checked,
        normalize_hostnames: rpNormalizeHostnames.checked,
        skip_tls_verify: rpSkipTlsVerify.checked,
      };
      try {
        await saveMappingOptions();
        closeModal(rpModal);
        await loadMappings();
      } catch (err) {
        alert(`Failed to save reverse proxy settings: ${err.message}`);
      }
    });

    dnsSave.addEventListener('click', async () => {
      moduleConfig.mapping_options.dns = {
        hostname_mode: dnsHostnameMode.value,
        include_wildcards: dnsIncludeWildcards.checked,
        include_disabled: dnsIncludeDisabled.checked,
        normalize_hostnames: dnsNormalizeHostnames.checked,
      };
      try {
        await saveMappingOptions();
        closeModal(dnsModal);
        await loadMappings();
      } catch (err) {
        alert(`Failed to save DNS settings: ${err.message}`);
      }
    });
  }

  function bindBuilderUi() {
    const newBtn = document.getElementById('dns-rp-new');
    const modal = document.getElementById('dns-rp-builder-modal');
    if (!newBtn || !modal) return;

    const closeBtn = document.getElementById('dns-rp-builder-close');
    const cancelBtn = document.getElementById('dns-rp-builder-cancel');
    const nextBtn = document.getElementById('dns-rp-builder-next');
    const backBtn = document.getElementById('dns-rp-builder-back');
    const sendBtn = document.getElementById('dns-rp-builder-send');

    const step1 = document.getElementById('dns-rp-builder-step-1');
    const step2 = document.getElementById('dns-rp-builder-step-2');

    const hostnameEl = document.getElementById('builder-hostname');
    const domainEl = document.getElementById('builder-domain');
    const targetProtocolEl = document.getElementById('builder-target-protocol');
    const targetHostEl = document.getElementById('builder-target-host');
    const targetPortEl = document.getElementById('builder-target-port');
    const dnsRecordTypeEl = document.getElementById('builder-dns-record-type');
    const dnsRecordValueEl = document.getElementById('builder-dns-record-value');

    const rpPayloadEl = document.getElementById('builder-rp-payload');
    const dnsPayloadEl = document.getElementById('builder-dns-payload');

    function showStep1() {
      step1.classList.remove('hidden');
      step2.classList.add('hidden');
      nextBtn.classList.remove('hidden');
      sendBtn.classList.add('hidden');
      backBtn.classList.add('hidden');
    }

    function showStep2() {
      step1.classList.add('hidden');
      step2.classList.remove('hidden');
      nextBtn.classList.add('hidden');
      sendBtn.classList.remove('hidden');
      backBtn.classList.remove('hidden');
    }

    async function prefillBuilderDefaults() {
      const res = await fetch('/api/dns-reverse-proxy/builder/defaults');
      if (!res.ok) {
        throw new Error('Failed to load builder defaults');
      }
      const data = await res.json();
      hostnameEl.value = data.hostname || '';
      domainEl.value = data.domain || '';
      targetProtocolEl.value = data.target_protocol || 'http';
      targetHostEl.value = data.target_host || '';
      targetPortEl.value = String(data.target_port || 80);
      dnsRecordTypeEl.value = data.dns_record_type || 'A';
      dnsRecordValueEl.value = data.dns_record_value || '';
    }

    function getBuilderInput() {
      return {
        hostname: hostnameEl.value.trim(),
        domain: domainEl.value.trim(),
        target_protocol: targetProtocolEl.value,
        target_host: targetHostEl.value.trim(),
        target_port: Number(targetPortEl.value || 0),
        dns_record_type: dnsRecordTypeEl.value,
        dns_record_value: dnsRecordValueEl.value.trim(),
      };
    }

    function openBuilder() {
      showStep1();
      prefillBuilderDefaults().catch((err) => {
        alert(`Failed to load defaults: ${err.message}`);
      });
      openModal(modal);
    }

    function closeBuilder() {
      closeModal(modal);
    }

    newBtn.addEventListener('click', openBuilder);
    [closeBtn, cancelBtn].forEach((btn) => btn && btn.addEventListener('click', closeBuilder));
    backBtn.addEventListener('click', showStep1);

    nextBtn.addEventListener('click', async () => {
      try {
        const res = await fetch('/api/dns-reverse-proxy/builder/preview', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(getBuilderInput()),
        });
        const data = await res.json();
        if (!res.ok || !data.ok) {
          throw new Error(data.error || 'Failed to generate preview payloads');
        }
        rpPayloadEl.value = data.reverse_proxy_payload_text || '';
        dnsPayloadEl.value = data.dns_payload_text || '';
        showStep2();
      } catch (err) {
        alert(`Preview failed: ${err.message}`);
      }
    });

    sendBtn.addEventListener('click', async () => {
      try {
        const res = await fetch('/api/dns-reverse-proxy/builder/send', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(getBuilderInput()),
        });
        const data = await res.json();
        if (!res.ok || !data.ok) {
          throw new Error(data.error || 'Failed to send payloads');
        }
        alert('Created reverse proxy + DNS records successfully.');
        closeBuilder();
        await loadMappings();
      } catch (err) {
        alert(`Send failed: ${err.message}`);
      }
    });

    targetProtocolEl.addEventListener('change', () => {
      const protocol = targetProtocolEl.value;
      if (protocol === 'https' && (!targetPortEl.value || targetPortEl.value === '80')) {
        targetPortEl.value = '443';
      }
      if (protocol === 'http' && (!targetPortEl.value || targetPortEl.value === '443')) {
        targetPortEl.value = '80';
      }
    });
  }

  window.addEventListener('DOMContentLoaded', () => {
    const refreshBtn = document.getElementById('dns-rp-refresh');
    if (refreshBtn) {
      refreshBtn.addEventListener('click', loadMappings);
    }
    loadModuleConfig()
      .then(() => {
        bindSettingsUi();
        bindBuilderUi();
        bindEditModalUi();
        bindProviderConfigUi();
        return loadMappings();
      })
      .catch((err) => {
        const statusEl = document.getElementById('dns-rp-status');
        if (statusEl) {
          statusEl.textContent = `Failed to initialize DNS/Proxy page: ${err.message}`;
        }
      });
  });
})();
