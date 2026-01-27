/**
 * Notification Panel Module
 *
 * Handles the notification bell UI, event display, polling, and
 * channel/rule management settings panel.
 *
 * HTML templates: _notifications.html, _notifications_modals.html
 */
(function () {
  let pollInterval = 30000;
  let pollTimer = null;
  let isEnabled = false;

  // ===========================================================================
  // Initialization
  // ===========================================================================

  async function init() {
    // Check if notifications module is enabled
    try {
      const res = await fetch('/api/config/modules');
      if (res.ok) {
        const data = await res.json();
        isEnabled = (data.modules || []).includes('notifications');
      }
    } catch (e) {
      console.warn('Failed to check notification module status:', e);
    }

    if (!isEnabled) {
      const bellContainer = document.getElementById('notification-bell-container');
      if (bellContainer) bellContainer.classList.add('hidden');
      return;
    }

    // Load poll interval from config
    try {
      const res = await fetch('/api/config/module/notifications');
      if (res.ok) {
        const config = await res.json();
        if (config.poll_interval) {
          pollInterval = config.poll_interval * 1000;
        }
      }
    } catch (e) {
      console.warn('Failed to load notification config:', e);
    }

    setupEventListeners();
    await updateUnreadCount();
    startPolling();
  }

  function setupEventListeners() {
    const bellBtn = document.getElementById('notification-bell-btn');
    const panel = document.getElementById('notification-panel');
    const settingsBtn = document.getElementById('notification-settings-btn');
    const backBtn = document.getElementById('notification-settings-back');
    const ackAllBtn = document.getElementById('notification-ack-all');
    const deleteAllBtn = document.getElementById('notification-delete-all');
    const addChannelBtn = document.getElementById('add-channel-btn');
    const addRuleBtn = document.getElementById('add-rule-btn');
    const channelCancelBtn = document.getElementById('channel-cancel-btn');
    const channelSaveBtn = document.getElementById('channel-save-btn');
    const ruleCancelBtn = document.getElementById('rule-cancel-btn');
    const ruleSaveBtn = document.getElementById('rule-save-btn');
    const channelType = document.getElementById('channel-type');
    const testNotificationBtn = document.getElementById('test-notification-btn');

    if (bellBtn) {
      bellBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        togglePanel();
      });
    }

    if (settingsBtn) {
      settingsBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        showSettingsPanel();
      });
    }

    if (backBtn) {
      backBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        hideSettingsPanel();
      });
    }

    if (ackAllBtn) {
      ackAllBtn.addEventListener('click', acknowledgeAll);
    }

    if (deleteAllBtn) {
      deleteAllBtn.addEventListener('click', deleteAllEvents);
    }

    if (addChannelBtn) {
      addChannelBtn.addEventListener('click', showAddChannelModal);
    }

    if (addRuleBtn) {
      addRuleBtn.addEventListener('click', showAddRuleModal);
    }

    if (channelCancelBtn) {
      channelCancelBtn.addEventListener('click', closeChannelModal);
    }

    if (channelSaveBtn) {
      channelSaveBtn.addEventListener('click', saveChannel);
    }

    if (ruleCancelBtn) {
      ruleCancelBtn.addEventListener('click', closeRuleModal);
    }

    if (ruleSaveBtn) {
      ruleSaveBtn.addEventListener('click', saveRule);
    }

    if (channelType) {
      channelType.addEventListener('change', updateConfigPlaceholder);
    }

    if (testNotificationBtn) {
      testNotificationBtn.addEventListener('click', sendTestNotification);
    }

    // Close panel when clicking outside
    document.addEventListener('click', (e) => {
      const bellContainer = document.getElementById('notification-bell-container');
      if (panel && bellContainer && !bellContainer.contains(e.target)) {
        panel.classList.add('hidden');
      }
    });
  }

  // ===========================================================================
  // Polling
  // ===========================================================================

  function startPolling() {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(updateUnreadCount, pollInterval);
  }

  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  }

  // ===========================================================================
  // API Calls
  // ===========================================================================

  async function updateUnreadCount() {
    try {
      const res = await fetch('/api/notifications/events/unread_count');
      if (res.ok) {
        const data = await res.json();
        const badge = document.getElementById('notification-badge');
        if (badge) {
          if (data.count > 0) {
            badge.textContent = data.count > 99 ? '99+' : data.count;
            badge.classList.remove('hidden');
          } else {
            badge.classList.add('hidden');
          }
        }
      }
    } catch (e) {
      console.warn('Failed to fetch unread count:', e);
    }
  }

  async function fetchEvents(acknowledged = false) {
    try {
      const url = `/api/notifications/events?acknowledged=${acknowledged}&limit=20`;
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        return data.events || [];
      }
    } catch (e) {
      console.warn('Failed to fetch events:', e);
    }
    return [];
  }

  async function fetchAllEvents() {
    try {
      const [unacked, acked] = await Promise.all([
        fetchEvents(false),
        fetchEvents(true)
      ]);
      const all = [...unacked, ...acked];
      all.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
      return all.slice(0, 50);
    } catch (e) {
      console.warn('Failed to fetch all events:', e);
    }
    return [];
  }

  async function acknowledgeEvent(eventId) {
    try {
      const res = await fetch(`/api/notifications/events/${eventId}/acknowledge`, {
        method: 'POST'
      });
      if (res.ok) {
        await refreshEventList();
        await updateUnreadCount();
      }
    } catch (e) {
      console.warn('Failed to acknowledge event:', e);
    }
  }

  async function acknowledgeAll() {
    try {
      const res = await fetch('/api/notifications/events/acknowledge_all', {
        method: 'POST'
      });
      if (res.ok) {
        await refreshEventList();
        await updateUnreadCount();
      }
    } catch (e) {
      console.warn('Failed to acknowledge all events:', e);
    }
  }

  async function deleteEvent(eventId) {
    try {
      const res = await fetch(`/api/notifications/events/${eventId}`, {
        method: 'DELETE'
      });
      if (res.ok) {
        await refreshEventList();
        await updateUnreadCount();
      }
    } catch (e) {
      console.warn('Failed to delete event:', e);
    }
  }

  async function deleteAllEvents() {
    if (!confirm('Delete all events? This cannot be undone.')) return;

    try {
      const res = await fetch('/api/notifications/events/delete_all', {
        method: 'DELETE'
      });
      if (res.ok) {
        await refreshEventList();
        await updateUnreadCount();
      }
    } catch (e) {
      console.warn('Failed to delete all events:', e);
    }
  }

  async function sendTestNotification() {
    // Prompt for severity with common values hint
    const severityInput = prompt(
      'Enter severity level (1=Info, 2=Warning, 3=Critical, 4=Emergency):',
      '2'
    );

    if (severityInput === null) return;

    const severity = parseInt(severityInput) || 2;

    try {
      const res = await fetch('/api/notifications/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          severity: severity,
          title: `Test Event (Severity ${severity})`,
          message: `This is a test event with severity level ${severity}.`
        })
      });
      if (res.ok) {
        await updateUnreadCount();
        await refreshEventList();
      }
    } catch (e) {
      console.warn('Failed to send test event:', e);
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Panel UI
  // ─────────────────────────────────────────────────────────────────────────

  function togglePanel() {
    const panel = document.getElementById('notification-panel');
    if (panel) {
      const isHidden = panel.classList.toggle('hidden');
      if (!isHidden) {
        refreshEventList();
      }
    }
  }

  async function refreshEventList() {
    const listEl = document.getElementById('notification-list');
    if (!listEl) return;

    listEl.innerHTML = '<div class="text-center text-gray-500 py-4">Loading...</div>';

    const events = await fetchAllEvents();

    if (events.length === 0) {
      listEl.innerHTML = '<div class="text-center text-gray-500 py-4">No notifications</div>';
      return;
    }

    listEl.innerHTML = '';
    for (const event of events) {
      const item = createEventItem(event);
      listEl.appendChild(item);
    }
  }

  function createEventItem(event) {
    const div = document.createElement('div');
    const isAcknowledged = event.acknowledged;
    div.className = `p-3 border-b border-gray-200 hover:bg-gray-50 transition-colors ${isAcknowledged ? 'opacity-50 bg-gray-50' : ''}`;

    const severityColors = {
      1: 'bg-blue-100 text-blue-800',
      2: 'bg-yellow-100 text-yellow-800',
      3: 'bg-red-100 text-red-800',
      4: 'bg-purple-100 text-purple-800'
    };
    const severityNames = { 1: 'Info', 2: 'Warning', 3: 'Critical', 4: 'Emergency' };
    const severityClass = severityColors[event.severity] || 'bg-pink-100 text-pink-800';
    const severityName = event.severity
      ? `Level ${event.severity}: ${severityNames[event.severity] || 'Custom'}`
      : 'Unknown';

    const timestamp = event.timestamp ? new Date(event.timestamp).toLocaleString() : '';

    div.innerHTML = `
      <div class="flex items-start justify-between gap-2">
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2 mb-1">
            <span class="px-2 py-0.5 text-xs font-medium rounded ${severityClass}">${severityName}</span>
            <span class="text-xs text-gray-500">${escapeHtml(event.source)}</span>
          </div>
          <div class="font-medium text-sm text-gray-900 truncate">${escapeHtml(event.title)}</div>
          <div class="text-xs text-gray-600 truncate">${escapeHtml(event.message)}</div>
          <div class="text-xs text-gray-400 mt-1">${timestamp}</div>
        </div>
        <div class="flex flex-col gap-1">
          <button class="ack-btn text-green-600 hover:text-green-800 p-1" data-id="${event.id}" title="Acknowledge">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
            </svg>
          </button>
          <button class="del-btn text-red-600 hover:text-red-800 p-1" data-id="${event.id}" title="Delete">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
            </svg>
          </button>
        </div>
      </div>
    `;

    div.querySelector('.ack-btn').addEventListener('click', () => acknowledgeEvent(event.id));
    div.querySelector('.del-btn').addEventListener('click', () => deleteEvent(event.id));

    return div;
  }

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text || '';
    return div.innerHTML;
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Settings Panel
  // ─────────────────────────────────────────────────────────────────────────

  function showSettingsPanel() {
    const mainContent = document.getElementById('notification-main-content');
    const settingsPanel = document.getElementById('notification-settings-panel');

    if (mainContent) mainContent.classList.add('hidden');
    if (settingsPanel) {
      settingsPanel.classList.remove('hidden');
      loadSettingsData();
    }
  }

  function hideSettingsPanel() {
    const mainContent = document.getElementById('notification-main-content');
    const settingsPanel = document.getElementById('notification-settings-panel');

    if (settingsPanel) settingsPanel.classList.add('hidden');
    if (mainContent) mainContent.classList.remove('hidden');
  }

  async function loadSettingsData() {
    await Promise.all([loadChannels(), loadRules()]);
  }

  async function loadChannels() {
    const container = document.getElementById('notification-channels-list');
    if (!container) return;

    container.innerHTML = '<div class="text-gray-500 text-sm">Loading...</div>';

    try {
      const res = await fetch('/api/notifications/channels');
      if (!res.ok) throw new Error('Failed to fetch channels');
      const data = await res.json();

      if (data.channels.length === 0) {
        container.innerHTML = '<div class="text-gray-500 text-sm">No channels configured</div>';
        return;
      }

      container.innerHTML = '';
      for (const channel of data.channels) {
        const item = createChannelItem(channel);
        container.appendChild(item);
      }
    } catch (e) {
      container.innerHTML = '<div class="text-red-500 text-sm">Failed to load channels</div>';
    }
  }

  function createChannelItem(channel) {
    const div = document.createElement('div');
    div.className = 'flex items-center justify-between p-2 bg-gray-50 rounded mb-2';

    const typeIcons = {
      discord: '💬',
      email: '📧',
      push: '📱',
      webhook: '🔗'
    };

    div.innerHTML = `
      <div class="flex items-center gap-2">
        <span>${typeIcons[channel.channel_type] || '📨'}</span>
        <span class="font-medium text-sm">${escapeHtml(channel.name)}</span>
        <span class="text-xs text-gray-500">(${channel.channel_type})</span>
      </div>
      <div class="flex items-center gap-2">
        <label class="flex items-center gap-1 text-xs">
          <input type="checkbox" class="toggle-channel" data-id="${channel.id}" ${channel.enabled ? 'checked' : ''}>
          <span>On</span>
        </label>
        <button class="edit-channel text-blue-600 hover:text-blue-800 text-xs" data-id="${channel.id}">Edit</button>
        <button class="delete-channel text-red-600 hover:text-red-800 text-xs" data-id="${channel.id}">Delete</button>
      </div>
    `;

    div.querySelector('.toggle-channel').addEventListener('change', (e) => toggleChannel(channel.id, e.target.checked));
    div.querySelector('.edit-channel').addEventListener('click', () => editChannel(channel.id));
    div.querySelector('.delete-channel').addEventListener('click', () => deleteChannel(channel.id));

    return div;
  }

  async function loadRules() {
    const container = document.getElementById('notification-rules-list');
    if (!container) return;

    container.innerHTML = '<div class="text-gray-500 text-sm">Loading...</div>';

    try {
      const res = await fetch('/api/notifications/rules');
      if (!res.ok) throw new Error('Failed to fetch rules');
      const data = await res.json();

      if (data.rules.length === 0) {
        container.innerHTML = '<div class="text-gray-500 text-sm">No rules configured</div>';
        return;
      }

      container.innerHTML = '';
      for (const rule of data.rules) {
        const item = createRuleItem(rule);
        container.appendChild(item);
      }
    } catch (e) {
      container.innerHTML = '<div class="text-red-500 text-sm">Failed to load rules</div>';
    }
  }

  function createRuleItem(rule) {
    const div = document.createElement('div');
    div.className = 'flex items-center justify-between p-2 bg-gray-50 rounded mb-2';

    const severityNames = { 1: 'Info', 2: 'Warning', 3: 'Critical', 4: 'Emergency' };
    const minHint = severityNames[rule.min_severity] ? ` (${severityNames[rule.min_severity]})` : '';
    const maxHint = rule.max_severity && severityNames[rule.max_severity] ? ` (${severityNames[rule.max_severity]})` : '';

    let severityDisplay;
    if (rule.max_severity) {
      severityDisplay = `${rule.min_severity}${minHint} - ${rule.max_severity}${maxHint}`;
    } else {
      severityDisplay = `≥ ${rule.min_severity}${minHint}`;
    }

    div.innerHTML = `
      <div class="flex items-center gap-2 text-sm">
        <span class="font-medium">Severity ${severityDisplay}</span>
        <span class="text-gray-500">→</span>
        <span>${escapeHtml(rule.channel_name || 'Unknown')} (${rule.channel_type || '?'})</span>
      </div>
      <div class="flex items-center gap-2">
        <label class="flex items-center gap-1 text-xs">
          <input type="checkbox" class="toggle-rule" data-id="${rule.id}" ${rule.enabled ? 'checked' : ''}>
          <span>On</span>
        </label>
        <button class="delete-rule text-red-600 hover:text-red-800 text-xs" data-id="${rule.id}">Delete</button>
      </div>
    `;

    div.querySelector('.toggle-rule').addEventListener('change', (e) => toggleRule(rule.id, e.target.checked));
    div.querySelector('.delete-rule').addEventListener('click', () => deleteRule(rule.id));

    return div;
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Channel Management
  // ─────────────────────────────────────────────────────────────────────────

  async function toggleChannel(channelId, enabled) {
    try {
      await fetch(`/api/notifications/channels/${channelId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled })
      });
    } catch (e) {
      console.warn('Failed to toggle channel:', e);
    }
  }

  async function deleteChannel(channelId) {
    if (!confirm('Delete this channel? Associated rules will also be deleted.')) return;
    try {
      await fetch(`/api/notifications/channels/${channelId}`, { method: 'DELETE' });
      await loadChannels();
      await loadRules();
    } catch (e) {
      console.warn('Failed to delete channel:', e);
    }
  }

  function showAddChannelModal() {
    const modal = document.getElementById('notification-channel-modal');
    if (modal) {
      document.getElementById('channel-modal-title').textContent = 'Add Channel';
      document.getElementById('channel-id').value = '';
      document.getElementById('channel-name').value = '';
      document.getElementById('channel-type').value = 'discord';
      document.getElementById('channel-config').value = '{}';
      updateConfigPlaceholder();
      modal.classList.remove('hidden');
    }
  }

  async function editChannel(channelId) {
    try {
      const res = await fetch('/api/notifications/channels');
      if (!res.ok) return;
      const data = await res.json();
      const channel = data.channels.find(c => c.id === channelId);
      if (!channel) return;

      const modal = document.getElementById('notification-channel-modal');
      if (modal) {
        document.getElementById('channel-modal-title').textContent = 'Edit Channel';
        document.getElementById('channel-id').value = channel.id;
        document.getElementById('channel-name').value = channel.name;
        document.getElementById('channel-type').value = channel.channel_type;
        document.getElementById('channel-config').value = JSON.stringify(channel.config, null, 2);
        modal.classList.remove('hidden');
      }
    } catch (e) {
      console.warn('Failed to load channel for edit:', e);
    }
  }

  function updateConfigPlaceholder() {
    const typeEl = document.getElementById('channel-type');
    const configEl = document.getElementById('channel-config');
    if (!typeEl || !configEl) return;

    const placeholders = {
      discord: '{\n  "webhook_url": "https://discord.com/api/webhooks/..."\n}',
      email: '{\n  "smtp_server": "smtp.gmail.com",\n  "smtp_port": 587,\n  "use_tls": true,\n  "username": "your-email@gmail.com",\n  "password": "your-app-password",\n  "from_email": "your-email@gmail.com",\n  "to_email": "recipient@example.com"\n}',
      push: '{\n  "endpoint": "...",\n  "auth_key": "..."\n}',
      webhook: '{\n  "url": "https://example.com/webhook",\n  "method": "POST",\n  "headers": {}\n}'
    };

    if (!document.getElementById('channel-id').value) {
      configEl.value = placeholders[typeEl.value] || '{}';
    }
  }

  async function saveChannel() {
    const id = document.getElementById('channel-id').value;
    const name = document.getElementById('channel-name').value;
    const channelType = document.getElementById('channel-type').value;
    let config = {};

    try {
      config = JSON.parse(document.getElementById('channel-config').value || '{}');
    } catch (e) {
      alert('Invalid JSON in config field');
      return;
    }

    const payload = { name, channel_type: channelType, config };

    try {
      const url = id ? `/api/notifications/channels/${id}` : '/api/notifications/channels';
      const method = id ? 'PUT' : 'POST';

      const res = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (res.ok) {
        closeChannelModal();
        await loadChannels();
      } else {
        const err = await res.json();
        alert(err.error || 'Failed to save channel');
      }
    } catch (e) {
      console.warn('Failed to save channel:', e);
      alert('Failed to save channel');
    }
  }

  function closeChannelModal() {
    const modal = document.getElementById('notification-channel-modal');
    if (modal) modal.classList.add('hidden');
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Rule Management
  // ─────────────────────────────────────────────────────────────────────────

  async function toggleRule(ruleId, enabled) {
    try {
      await fetch(`/api/notifications/rules/${ruleId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled })
      });
    } catch (e) {
      console.warn('Failed to toggle rule:', e);
    }
  }

  async function deleteRule(ruleId) {
    if (!confirm('Delete this rule?')) return;
    try {
      await fetch(`/api/notifications/rules/${ruleId}`, { method: 'DELETE' });
      await loadRules();
    } catch (e) {
      console.warn('Failed to delete rule:', e);
    }
  }

  async function showAddRuleModal() {
    const modal = document.getElementById('notification-rule-modal');
    const channelSelect = document.getElementById('rule-channel');

    if (!modal || !channelSelect) return;

    try {
      const res = await fetch('/api/notifications/channels');
      if (res.ok) {
        const data = await res.json();
        channelSelect.innerHTML = data.channels.map(c =>
          `<option value="${c.id}">${escapeHtml(c.name)} (${c.channel_type})</option>`
        ).join('');
      }
    } catch (e) {
      console.warn('Failed to load channels for rule modal:', e);
    }

    document.getElementById('rule-min-severity').value = '1';
    document.getElementById('rule-max-severity').value = '';
    modal.classList.remove('hidden');
  }

  async function saveRule() {
    const channelId = document.getElementById('rule-channel').value;
    const minSeverityVal = document.getElementById('rule-min-severity').value;
    const maxSeverityVal = document.getElementById('rule-max-severity').value;

    if (!channelId) {
      alert('Please select a channel');
      return;
    }

    const minSeverity = parseInt(minSeverityVal, 10);
    if (isNaN(minSeverity) || minSeverity < 1) {
      alert('Min severity must be a positive integer');
      return;
    }

    let maxSeverity = null;
    if (maxSeverityVal && maxSeverityVal.trim() !== '') {
      maxSeverity = parseInt(maxSeverityVal, 10);
      if (isNaN(maxSeverity) || maxSeverity < 1) {
        alert('Max severity must be a positive integer or empty');
        return;
      }
      if (maxSeverity < minSeverity) {
        alert('Max severity must be greater than or equal to min severity');
        return;
      }
    }

    try {
      const res = await fetch('/api/notifications/rules', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          channel_id: parseInt(channelId),
          min_severity: minSeverity,
          max_severity: maxSeverity
        })
      });

      if (res.ok) {
        closeRuleModal();
        await loadRules();
      } else {
        const err = await res.json();
        alert(err.error || 'Failed to save rule');
      }
    } catch (e) {
      console.warn('Failed to save rule:', e);
      alert('Failed to save rule');
    }
  }

  function closeRuleModal() {
    const modal = document.getElementById('notification-rule-modal');
    if (modal) modal.classList.add('hidden');
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Public API
  // ─────────────────────────────────────────────────────────────────────────

  window.notificationModule = {
    init,
    acknowledgeEvent,
    deleteEvent
  };

  // Auto-initialize on DOM ready
  document.addEventListener('DOMContentLoaded', init);
})();
