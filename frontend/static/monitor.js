/**
 * =============================================================================
 * MONITOR.JS - Container and VM monitoring interface
 * =============================================================================
 * 
 * Handles the monitor module UI, including selection of containers/VMs,
 * enabling/disabling monitoring, and configuring event severity settings.
 */

// monitor.js - Monitor module with settings/view panels

(function () {
  // Current selection state
  let currentSelection = null; // { type: 'container'|'vm'|'monitor', id: string, name: string, data: object }
  let currentView = 'settings'; // 'settings' or 'view'

  window.addEventListener('DOMContentLoaded', async () => {
    const root = document.getElementById('monitor-root');
    if (!root) return;

    await populateDropdowns();
    setupEventListeners();
  });

  // ─────────────────────────────────────────────────────────────────────────
  // Dropdown Population
  // ─────────────────────────────────────────────────────────────────────────

  async function populateDropdowns() {
    const containerSelect = document.getElementById('monitor-container-select');
    const vmSelect = document.getElementById('monitor-vm-select');
    const activeSelect = document.getElementById('monitor-active-select');

    // Load active monitors first so we can mark containers/VMs as monitored
    let monitorBodies = [];
    try {
      const res = await fetch('/api/monitor/bodies');
      if (res.ok) {
        monitorBodies = await res.json();
      }
    } catch (e) {
      console.error('Failed to load monitor bodies', e);
    }

    // Create lookup sets for monitored containers/VMs
    const monitoredContainerIds = new Set();
    const monitoredVmIds = new Set();
    monitorBodies.forEach(body => {
      if (body.container_id) monitoredContainerIds.add(body.container_id);
      if (body.vm_id) monitoredVmIds.add(body.vm_id);
    });

    // Populate containers dropdown
    if (containerSelect) {
      try {
        const res = await fetch('/api/containers');
        if (res.ok) {
          const containers = await res.json();
          containers.forEach(c => {
            const opt = document.createElement('option');
            opt.value = c.id;
            const isMonitored = monitorBodies.some(m => m.container_id && c.id === c.id);
            opt.textContent = c.name || c.id;
            if (isMonitored) opt.textContent += ' ✓';
            opt.dataset.name = c.name || c.id;
            opt.dataset.image = c.image || '';
            opt.dataset.state = c.state || 'unknown';
            containerSelect.appendChild(opt);
          });
        }
      } catch (e) {
        console.error('Failed to load containers for monitor dropdown', e);
      }
    }

    // Populate VMs dropdown
    if (vmSelect) {
      try {
        const res = await fetch('/api/vms');
        if (res.ok) {
          const vms = await res.json();
          vms.forEach(vm => {
            const opt = document.createElement('option');
            opt.value = vm.id;
            opt.textContent = vm.name || vm.id;
            opt.dataset.name = vm.name || vm.id;
            vmSelect.appendChild(opt);
          });
        }
      } catch (e) {
        console.error('Failed to load VMs for monitor dropdown', e);
      }
    }

    // Populate active monitors dropdown
    if (activeSelect) {
      monitorBodies.forEach(body => {
        if (body.enabled) {
          const opt = document.createElement('option');
          opt.value = body.id;
          opt.name = body.id;
          const target = body.name || body.container_id || body.vm_id || `id:${body.id}`;
          opt.textContent = `${target} (${body.monitor_type || 'monitor'})`;
          opt.dataset.body = JSON.stringify(body);
          activeSelect.appendChild(opt);
        }
      });
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Event Listeners
  // ─────────────────────────────────────────────────────────────────────────

  function setupEventListeners() {
    const containerSelect = document.getElementById('monitor-container-select');
    const vmSelect = document.getElementById('monitor-vm-select');
    const activeSelect = document.getElementById('monitor-active-select');
    const toggleViewBtn = document.getElementById('monitor-toggle-view');
    const saveBtn = document.getElementById('monitor-save-btn');
    const enabledToggle = document.getElementById('monitor-enabled-toggle');

    if (containerSelect) {
      containerSelect.addEventListener('change', async (e) => {
        if (!e.target.value) return;
        // Clear other selects
        if (vmSelect) vmSelect.value = '';
        if (activeSelect) activeSelect.value = '';

        const opt = e.target.selectedOptions[0];
        await selectTarget('container', e.target.value, opt.dataset.name, {
          image: opt.dataset.image,
          state: opt.dataset.state
        });
      });
    }

    if (vmSelect) {
      vmSelect.addEventListener('change', async (e) => {
        if (!e.target.value) return;
        if (containerSelect) containerSelect.value = '';
        if (activeSelect) activeSelect.value = '';

        const opt = e.target.selectedOptions[0];
        await selectTarget('vm', e.target.value, opt.dataset.name, {});
      });
    }

    if (activeSelect) {
      activeSelect.addEventListener('change', async (e) => {
        if (!e.target.value) return;
        if (containerSelect) containerSelect.value = '';
        if (vmSelect) vmSelect.value = '';

        const opt = e.target.selectedOptions[0];
        const body = JSON.parse(opt.dataset.body || '{}');
        await selectActiveMonitor(e.target.value, body);
      });
    }

    if (toggleViewBtn) {
      toggleViewBtn.addEventListener('click', toggleView);
    }

    if (saveBtn) {
      saveBtn.addEventListener('click', saveMonitorSettings);
    }

    if (enabledToggle) {
      enabledToggle.addEventListener('change', () => {
        updateNotEnabledNotice();
      });
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Selection Handling
  // ─────────────────────────────────────────────────────────────────────────

  async function selectTarget(type, id, name, extraData = {}) {
    currentSelection = { type, id, name, data: extraData };

    // Fetch monitor status for this target
    let monitorData = null;
    try {
      if (type === 'container') {
        const res = await fetch(`/api/monitor/container/${encodeURIComponent(id)}`);
        if (res.ok) {
          monitorData = await res.json();
        }
      } else if (type === 'vm') {
        const res = await fetch(`/api/monitor/vm/${encodeURIComponent(id)}`);
        if (res.ok) {
          monitorData = await res.json();
        }
      }
    } catch (e) {
      console.warn('Failed to fetch monitor data:', e);
    }

    currentSelection.monitorData = monitorData;

    // Update display
    updateDisplayPanel();

    // Populate notification settings from saved data
    populateNotificationSettings(monitorData?.event_severity_settings);

    // Show settings view for non-monitored, view for monitored
    if (monitorData && monitorData.enabled) {
      showView('view');
    } else {
      showView('settings');
    }

    // Show the panel
    document.getElementById('monitor-display').classList.remove('hidden');
  }

  async function selectActiveMonitor(monitorId, body) {
    // For active monitors, we show the view panel
    currentSelection = {
      type: 'monitor',
      id: monitorId,
      name: body.name || `Monitor ${monitorId}`,
      data: body,
      monitorData: { ...body, enabled: true }
    };

    updateDisplayPanel();
    populateNotificationSettings(body.event_severity_settings);
    showView('view');  // This already calls loadMonitorViewData internally
    document.getElementById('monitor-display').classList.remove('hidden');
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Display Panel Updates
  // ─────────────────────────────────────────────────────────────────────────

  function updateDisplayPanel() {
    if (!currentSelection) return;

    const titleEl = document.getElementById('monitor-display-title');
    const subtitleEl = document.getElementById('monitor-display-subtitle');
    const iconEl = document.getElementById('monitor-display-icon');
    const statusBadge = document.getElementById('monitor-status-badge');
    const enabledToggle = document.getElementById('monitor-enabled-toggle');

    // Set title and icon based on type
    titleEl.textContent = currentSelection.name || currentSelection.id;

    if (currentSelection.type === 'container') {
      iconEl.textContent = '📦';
      subtitleEl.textContent = `docker • ${currentSelection.data.image || 'container'}`;
    } else if (currentSelection.type === 'vm') {
      iconEl.textContent = '🖥️';
      subtitleEl.textContent = 'vm • virtual machine';
    } else {
      iconEl.textContent = '📊';
      subtitleEl.textContent = `${currentSelection.data.monitor_type || 'monitor'} • active`;
    }

    // Update status badge
    const state = currentSelection.data.state || currentSelection.monitorData?.last_state;
    if (state) {
      statusBadge.classList.remove('hidden');
      statusBadge.textContent = state.charAt(0).toUpperCase() + state.slice(1);
      if (state === 'running' || state === 'online') {
        statusBadge.className = 'px-2 py-1 text-xs font-medium rounded-full bg-green-100 text-green-800';
      } else if (state === 'exited' || state === 'offline' || state === 'stopped') {
        statusBadge.className = 'px-2 py-1 text-xs font-medium rounded-full bg-red-100 text-red-800';
      } else {
        statusBadge.className = 'px-2 py-1 text-xs font-medium rounded-full bg-gray-100 text-gray-800';
      }
    } else {
      statusBadge.classList.add('hidden');
    }

    // Update enabled toggle
    if (enabledToggle) {
      enabledToggle.checked = currentSelection.monitorData?.enabled || false;
    }

    updateNotEnabledNotice();
  }

  function updateNotEnabledNotice() {
    const notice = document.getElementById('monitor-not-enabled-notice');
    const enabledToggle = document.getElementById('monitor-enabled-toggle');
    if (notice && enabledToggle) {
      notice.classList.toggle('hidden', enabledToggle.checked);
    }
  }

  function populateNotificationSettings(settings) {
    // Default settings if none provided
    const defaults = {
      offline: { enabled: true, severity: 3 },
      online: { enabled: true, severity: 1 },
      unreachable: { enabled: true, severity: 2 },
      resources: { enabled: false, severity: 2 }
    };

    const s = settings || defaults;

    // Offline
    const offlineCheck = document.getElementById('notify-offline');
    const offlineSev = document.getElementById('notify-offline-severity');
    if (offlineCheck) offlineCheck.checked = s.offline?.enabled ?? defaults.offline.enabled;
    if (offlineSev) offlineSev.value = s.offline?.severity ?? defaults.offline.severity;

    // Online
    const onlineCheck = document.getElementById('notify-online');
    const onlineSev = document.getElementById('notify-online-severity');
    if (onlineCheck) onlineCheck.checked = s.online?.enabled ?? defaults.online.enabled;
    if (onlineSev) onlineSev.value = s.online?.severity ?? defaults.online.severity;

    // Unreachable
    const unreachableCheck = document.getElementById('notify-unreachable');
    const unreachableSev = document.getElementById('notify-unreachable-severity');
    if (unreachableCheck) unreachableCheck.checked = s.unreachable?.enabled ?? defaults.unreachable.enabled;
    if (unreachableSev) unreachableSev.value = s.unreachable?.severity ?? defaults.unreachable.severity;

    // Resources
    const resourcesCheck = document.getElementById('notify-resources');
    const resourcesSev = document.getElementById('notify-resources-severity');
    if (resourcesCheck) resourcesCheck.checked = s.resources?.enabled ?? defaults.resources.enabled;
    if (resourcesSev) resourcesSev.value = s.resources?.severity ?? defaults.resources.severity;
  }

  // ─────────────────────────────────────────────────────────────────────────
  // View Toggle
  // ─────────────────────────────────────────────────────────────────────────

  function toggleView() {
    if (currentView === 'settings') {
      showView('view');
    } else {
      showView('settings');
    }
  }

  function showView(view) {
    currentView = view;

    const settingsPanel = document.getElementById('monitor-settings-panel');
    const viewPanel = document.getElementById('monitor-view-panel');
    const iconSettings = document.getElementById('icon-settings');
    const iconMonitor = document.getElementById('icon-monitor');

    if (view === 'settings') {
      settingsPanel.classList.remove('hidden');
      viewPanel.classList.add('hidden');
      // Show monitor icon (to switch to view)
      iconSettings.classList.add('hidden');
      iconMonitor.classList.remove('hidden');
    } else {
      settingsPanel.classList.add('hidden');
      viewPanel.classList.remove('hidden');
      // Show settings icon (to switch to settings)
      iconSettings.classList.remove('hidden');
      iconMonitor.classList.add('hidden');

      // Load view data - use monitor ID if we have one, otherwise use container/VM ID
      if (currentSelection) {
        const targetId = currentSelection.monitorData?.id || currentSelection.id;
        loadMonitorViewData(targetId);
      }
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Monitor View Data
  // ─────────────────────────────────────────────────────────────────────────

  async function loadMonitorViewData(monitorId) {
    const statusEl = document.getElementById('view-status');
    const uptimeEl = document.getElementById('view-uptime');
    const lastCheckEl = document.getElementById('view-last-check');
    const eventsListEl = document.getElementById('view-events-list');

    // Try to load monitor points/history
    try {
      // 
      const res = await fetch(`/api/monitor/points/latest/${encodeURIComponent(monitorId)}`);
      if (!res.ok) throw new Error('Failed to load latest monitor point');
      const data = await res.json();
      const state = data.value;
      if (statusEl) {
        statusEl.textContent = state.charAt(0).toUpperCase() + state.slice(1);
        if (state === 'running' || state === 'online') {
          statusEl.className = 'text-xl font-semibold text-green-600';
        } else if (state === 'exited' || state === 'offline' || state === 'stopped') {
          statusEl.className = 'text-xl font-semibold text-red-600';
        } else {
          statusEl.className = 'text-xl font-semibold text-gray-600';
        }
      }

      if (uptimeEl) {
        // For monitors, query the DB to get the Docker ID from the container_id (database FK)
        let dockerId;
        if (currentSelection.type === 'monitor' && currentSelection.data?.container_id) {
          // Query the backend to resolve DB container_id to Docker ID
          try {
            const dockerIdRes = await fetch(`/api/containers/docker-id/${currentSelection.data.container_id}`);
            if (dockerIdRes.ok) {
              const dockerIdData = await dockerIdRes.json();
              dockerId = dockerIdData.docker_id;
            }
          } catch (e) {
            console.warn('Failed to resolve container_id to docker_id:', e);
          }
        } else if (currentSelection.type === 'container') {
          dockerId = currentSelection.id;
        } else if (currentSelection.monitorData?.container_id) {
          // Try to resolve this too
          try {
            const dockerIdRes = await fetch(`/api/containers/docker-id/${currentSelection.monitorData.container_id}`);
            if (dockerIdRes.ok) {
              const dockerIdData = await dockerIdRes.json();
              dockerId = dockerIdData.docker_id;
            }
          } catch (e) {
            console.warn('Failed to resolve container_id to docker_id:', e);
          }
        }

        if (dockerId) {
          const res = await fetch(`/api/containers/uptime/${encodeURIComponent(dockerId)}`);
          if (res.ok) {
            const uptimeData = await res.json();
            uptimeEl.textContent = uptimeData.uptime || '--';
          } else {
            uptimeEl.textContent = 'Uptime data not available';
          }
        } else {
          uptimeEl.textContent = 'Uptime data not available';
        }
      }

      if (lastCheckEl) {
        lastCheckEl.textContent = data.timestamp ? new Date(data.timestamp).toLocaleTimeString() : 'Error, timestamp missing';
      }

      // Load events for this target
      if (eventsListEl && currentSelection) {
        let eventsRes;

        // Determine the actual target type and ID
        if (currentSelection.type === 'monitor') {
          // For monitors, check what they're monitoring (container or VM)
          if (currentSelection.data?.container_id) {
            eventsRes = await fetch(`/api/notifications/events/lastEventsByContainerId/${encodeURIComponent(currentSelection.data.container_id)}:10`);
          } else if (currentSelection.data?.vm_id) {
            eventsRes = await fetch(`/api/notifications/events/lastEventsByVmId/${encodeURIComponent(currentSelection.data.vm_id)}:10`);
          }
        } else if (currentSelection.type === 'container' || currentSelection.type === 'docker') {
          eventsRes = await fetch(`/api/notifications/events/lastEventsByContainerId/${encodeURIComponent(currentSelection.id)}:10`);
        } else if (currentSelection.type === 'vm') {
          eventsRes = await fetch(`/api/notifications/events/lastEventsByVmId/${encodeURIComponent(currentSelection.id)}:10`);
        }
        if (eventsRes && eventsRes.ok) {
          const events = await eventsRes.json();
          if (events.length === 0) {
            eventsListEl.innerHTML = `
              <div class="text-sm text-gray-500 p-2 bg-gray-50 rounded">
                No events recorded yet.
              </div>
            `;
          } else {
            eventsListEl.innerHTML = '';
            events.forEach(event => {
              const eventEl = document.createElement('div');
              eventEl.className = 'p-2 border-b last:border-b-0';
              eventEl.innerHTML = `
                <div class="text-sm font-medium">${event.type.charAt(0).toUpperCase() + event.type.slice(1)}</div>
                <div class="text-xs text-gray-500">${new Date(event.timestamp).toLocaleString()}</div>
                <div class="text-sm mt-1">${event.message}</div>
              `;
              eventsListEl.appendChild(eventEl);
            });
          }
        }
      }
    } catch (e) {
      console.warn('Failed to load monitor view data:', e);
    }
  }


  // ─────────────────────────────────────────────────────────────────────────
  // Save Settings
  // ─────────────────────────────────────────────────────────────────────────

  async function saveMonitorSettings() {
    if (!currentSelection) return;

    const enabledToggle = document.getElementById('monitor-enabled-toggle');
    const enabled = enabledToggle?.checked || false;

    // Gather notification settings
    const notificationSettings = {
      offline: {
        enabled: document.getElementById('notify-offline')?.checked || false,
        severity: parseInt(document.getElementById('notify-offline-severity')?.value) || 3
      },
      online: {
        enabled: document.getElementById('notify-online')?.checked || false,
        severity: parseInt(document.getElementById('notify-online-severity')?.value) || 1
      },
      unreachable: {
        enabled: document.getElementById('notify-unreachable')?.checked || false,
        severity: parseInt(document.getElementById('notify-unreachable-severity')?.value) || 2
      },
      resources: {
        enabled: document.getElementById('notify-resources')?.checked || false,
        severity: parseInt(document.getElementById('notify-resources-severity')?.value) || 2
      }
    };

    try {
      let url, body;

      if (currentSelection.type === 'container') {
        url = `/api/monitor/container/${encodeURIComponent(currentSelection.id)}`;
        body = {
          enabled,
          event_severity_settings: notificationSettings
        };
      } else if (currentSelection.type === 'vm') {
        url = `/api/monitor/vm/${encodeURIComponent(currentSelection.id)}`;
        body = {
          enabled,
          event_severity_settings: notificationSettings
        };
      } else {
        // For existing monitors, update in place
        url = `/api/monitor/bodies/${encodeURIComponent(currentSelection.id)}`;
        body = {
          enabled,
          event_severity_settings: notificationSettings
        };
      }

      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });

      if (res.ok) {
        const data = await res.json();
        currentSelection.monitorData = data;
        updateDisplayPanel();
        updateNotEnabledNotice();

        // Show success feedback
        const saveBtn = document.getElementById('monitor-save-btn');
        if (saveBtn) {
          const originalText = saveBtn.textContent;
          saveBtn.textContent = 'Saved!';
          saveBtn.classList.remove('bg-blue-500', 'hover:bg-blue-600');
          saveBtn.classList.add('bg-green-500');
          setTimeout(() => {
            saveBtn.textContent = originalText;
            saveBtn.classList.remove('bg-green-500');
            saveBtn.classList.add('bg-blue-500', 'hover:bg-blue-600');
          }, 2000);
        }

        // Refresh the active monitors dropdown
        await refreshActiveMonitors();
      } else {
        const err = await res.json();
        alert('Failed to save: ' + (err.error || 'Unknown error'));
      }
    } catch (e) {
      console.error('Failed to save monitor settings:', e);
      alert('Failed to save settings');
    }
  }

  async function refreshActiveMonitors() {
    const activeSelect = document.getElementById('monitor-active-select');
    if (!activeSelect) return;

    // Clear and repopulate
    activeSelect.innerHTML = '<option value="">Select an active monitor...</option>';

    try {
      const res = await fetch('/api/monitor/bodies');
      if (res.ok) {
        const bodies = await res.json();
        bodies.forEach(body => {
          if (body.enabled) {
            const opt = document.createElement('option');
            opt.value = body.id;
            const target = body.container_id || body.vm_id || `id:${body.id}`;
            opt.textContent = `${target} (${body.monitor_type || 'monitor'})`;
            opt.dataset.body = JSON.stringify(body);
            activeSelect.appendChild(opt);
          }
        });
      }
    } catch (e) {
      console.error('Failed to refresh active monitors:', e);
    }
  }
})();
