// notifications.js - Bell icon notification panel with settings
// Dynamically injects all UI elements
(function () {
    let pollInterval = 30000; // default 30 seconds
    let pollTimer = null;
    let isEnabled = false;

    // ─────────────────────────────────────────────────────────────────────────
    // HTML Templates
    // ─────────────────────────────────────────────────────────────────────────

    function createNotificationHTML() {
        return `
      <div id="notification-bell-container" class="relative">
        <button id="notification-bell-btn" class="relative p-1 text-gray-600 hover:text-gray-800 focus:outline-none">
          <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"></path>
          </svg>
          <span id="notification-badge" class="hidden absolute -top-1 -right-1 bg-red-500 text-white text-xs rounded-full h-5 w-5 flex items-center justify-center">0</span>
        </button>
        <div id="notification-panel" class="hidden absolute right-0 mt-2 w-96 bg-white rounded-lg shadow-xl z-50 border border-gray-200">
          <div id="notification-main-content">
            <div class="flex items-center justify-between p-3 border-b border-gray-200">
              <h3 class="font-semibold text-gray-900">Notifications</h3>
              <div class="flex items-center gap-2">
                <button id="notification-ack-all" class="text-xs text-blue-600 hover:text-blue-800">Mark all read</button>
                <button id="notification-delete-all" class="p-1 text-red-500 hover:text-red-700" title="Delete all notifications">
                  <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                  </svg>
                </button>
                <button id="notification-settings-btn" class="p-1 text-gray-500 hover:text-gray-700" title="Settings">
                  <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"></path>
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path>
                  </svg>
                </button>
              </div>
            </div>
            <div id="notification-list" class="max-h-96 overflow-y-auto"></div>
          </div>
          <div id="notification-settings-panel" class="hidden">
            <div class="flex items-center gap-2 p-3 border-b border-gray-200">
              <button id="notification-settings-back" class="p-1 text-gray-500 hover:text-gray-700">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"></path>
                </svg>
              </button>
              <h3 class="font-semibold text-gray-900">Notification Settings</h3>
            </div>
            <div class="p-3 max-h-96 overflow-y-auto">
              <div class="mb-4">
                <div class="flex items-center justify-between mb-2">
                  <h4 class="font-medium text-sm text-gray-700">Delivery Channels</h4>
                  <button id="add-channel-btn" class="text-xs text-blue-600 hover:text-blue-800">+ Add</button>
                </div>
                <div id="notification-channels-list"></div>
              </div>
              <div>
                <div class="flex items-center justify-between mb-2">
                  <h4 class="font-medium text-sm text-gray-700">Severity Rules</h4>
                  <button id="add-rule-btn" class="text-xs text-blue-600 hover:text-blue-800">+ Add</button>
                </div>
                <p class="text-xs text-gray-500 mb-2">Common: 1=Info, 2=Warning, 3=Critical, 4=Emergency</p>
                <div id="notification-rules-list"></div>
              </div>
            </div>
          </div>
        </div>
      </div>
    `;
    }

    function createChannelModalHTML() {
        return `
      <div id="notification-channel-modal" class="hidden fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
        <div class="bg-white rounded-lg shadow-xl w-96 p-4">
          <h3 id="channel-modal-title" class="font-semibold text-lg mb-4">Add Channel</h3>
          <input type="hidden" id="channel-id">
          <div class="mb-3">
            <label class="block text-sm font-medium text-gray-700 mb-1">Name</label>
            <input type="text" id="channel-name" class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500">
          </div>
          <div class="mb-3">
            <label class="block text-sm font-medium text-gray-700 mb-1">Type</label>
            <select id="channel-type" class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500">
              <option value="discord">Discord</option>
              <option value="email">Email</option>
              <option value="push">Push</option>
              <option value="webhook">Webhook</option>
            </select>
          </div>
          <div class="mb-4">
            <label class="block text-sm font-medium text-gray-700 mb-1">Config (JSON)</label>
            <textarea id="channel-config" rows="4" class="w-full px-3 py-2 border border-gray-300 rounded-md font-mono text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">{}</textarea>
          </div>
          <div class="flex justify-end gap-2">
            <button id="channel-cancel-btn" class="px-4 py-2 text-gray-600 hover:text-gray-800">Cancel</button>
            <button id="channel-save-btn" class="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600">Save</button>
          </div>
        </div>
      </div>
    `;
    }

    function createRuleModalHTML() {
        return `
      <div id="notification-rule-modal" class="hidden fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
        <div class="bg-white rounded-lg shadow-xl w-80 p-4">
          <h3 class="font-semibold text-lg mb-4">Add Severity Rule</h3>
          <div class="mb-3">
            <label class="block text-sm font-medium text-gray-700 mb-1">Channel</label>
            <select id="rule-channel" class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"></select>
          </div>
          <div class="mb-3">
            <label class="block text-sm font-medium text-gray-700 mb-1">Min Severity</label>
            <input type="number" id="rule-min-severity" min="1" value="1" class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500">
          </div>
          <div class="mb-4">
            <label class="block text-sm font-medium text-gray-700 mb-1">Max Severity (optional)</label>
            <input type="number" id="rule-max-severity" min="1" placeholder="No limit" class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500">
            <p class="text-xs text-gray-500 mt-1">Leave empty for no upper limit. Common: 1=Info, 2=Warning, 3=Critical, 4=Emergency</p>
          </div>
          <div class="flex justify-end gap-2">
            <button id="rule-cancel-btn" class="px-4 py-2 text-gray-600 hover:text-gray-800">Cancel</button>
            <button id="rule-save-btn" class="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600">Save</button>
          </div>
        </div>
      </div>
    `;
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Initialization
    // ─────────────────────────────────────────────────────────────────────────

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

        if (!isEnabled) return;

        // Load module config for poll interval
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

        // Inject HTML into the page
        injectHTML();

        // Setup event listeners
        setupEventListeners();

        // Initial fetch and start polling
        await updateUnreadCount();
        startPolling();
    }

    function injectHTML() {
        // Find the right nav area (look for nav-right-link or nav-right-arrow or fallback to justify-self-end div)
        const rightLink = document.getElementById('nav-right-link');
        const rightArrow = document.getElementById('nav-right-arrow');

        // Create a container for the bell
        const bellWrapper = document.createElement('div');
        bellWrapper.innerHTML = createNotificationHTML();
        const bellContainer = bellWrapper.firstElementChild;

        // Insert before the right navigation link
        if (rightLink && rightLink.parentElement) {
            rightLink.parentElement.insertBefore(bellContainer, rightLink);
        } else if (rightArrow && rightArrow.parentElement) {
            rightArrow.parentElement.insertBefore(bellContainer, rightArrow);
        } else {
            // Fallback: find the right nav area by class
            const rightNavDiv = document.querySelector('.justify-self-end.flex');
            if (rightNavDiv && rightNavDiv.firstChild) {
                rightNavDiv.insertBefore(bellContainer, rightNavDiv.firstChild);
            } else if (rightNavDiv) {
                rightNavDiv.appendChild(bellContainer);
            } else {
                // Last resort: append to body (modals will still work)
                document.body.appendChild(bellContainer);
            }
        }

        // Inject modals into body
        const modalsWrapper = document.createElement('div');
        modalsWrapper.innerHTML = createChannelModalHTML() + createRuleModalHTML();
        while (modalsWrapper.firstChild) {
            document.body.appendChild(modalsWrapper.firstChild);
        }
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

        // Close panel when clicking outside
        document.addEventListener('click', (e) => {
            const bellContainer = document.getElementById('notification-bell-container');
            if (panel && bellContainer && !bellContainer.contains(e.target)) {
                panel.classList.add('hidden');
            }
        });
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Polling
    // ─────────────────────────────────────────────────────────────────────────

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

    // ─────────────────────────────────────────────────────────────────────────
    // API Calls
    // ─────────────────────────────────────────────────────────────────────────

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
            // Fetch both acknowledged and unacknowledged, combine and sort by timestamp
            const [unacked, acked] = await Promise.all([
                fetchEvents(false),
                fetchEvents(true)
            ]);
            const all = [...unacked, ...acked];
            // Sort by timestamp descending (newest first)
            all.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
            return all.slice(0, 50); // Limit to 50 total
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
        if (!confirm('Delete all notifications? This cannot be undone.')) return;

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

        // Fetch all events (both acknowledged and unacknowledged)
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

        // Attach event listeners (source button uses event delegation, not inline)
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

        // Load channels for dropdown
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
    // Public API (for backwards compatibility, though not needed now)
    // ─────────────────────────────────────────────────────────────────────────

    window.notificationModule = {
        init,
        acknowledgeEvent,
        deleteEvent
    };

    // Auto-initialize on DOM ready
    document.addEventListener('DOMContentLoaded', init);
})();
