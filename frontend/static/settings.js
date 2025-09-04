let currentSettings = {};

window.addEventListener("DOMContentLoaded", async () => {
  await loadSettings();
  
  // Event listeners
  document.getElementById("save-settings").addEventListener("click", saveSettings);
  document.getElementById("complete-setup").addEventListener("click", completeSetup);
  document.getElementById("reset-settings").addEventListener("click", resetSettings);
  
  // Backup view toggle
  document.getElementById("backup-view-enabled").addEventListener("change", function() {
    const subSettings = document.getElementById("backup-sub-settings");
    if (this.checked) {
      subSettings.classList.remove("hidden");
    } else {
      subSettings.classList.add("hidden");
    }
  });
});

async function loadSettings() {
  try {
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
    
    // Load backup view configuration
    const backupViewRes = await fetch("/api/config/backup_view_enabled");
    const backupViewData = await backupViewRes.json();

    // Load backup configuration settings
    let backupConfigData = { backup_config: {} };
    try {
      const backupConfigRes = await fetch("/api/config/backup_config");
      if (backupConfigRes.ok) {
        backupConfigData = await backupConfigRes.json();
      }
    } catch (err) {
      console.warn("Failed to load backup config, using defaults:", err);
    }

    document.getElementById("internal-ip").value = internalIpData.internal_ip || "127.0.0.1";
    document.getElementById("external-ip").value = externalIpData.external_ip || "127.0.0.1";
    document.getElementById("proxy-count").value = proxyData.proxy_count || 0;
    document.getElementById("backup-view-enabled").checked = backupViewData.backup_view_enabled || false;
    
    // Load backup configuration fields
    const config = backupConfigData.backup_config || {};
    
    // Date/Time format
    document.getElementById("backup-datetime-format").value = config.datetime_format || "%Y-%m-%d %H:%M:%S";
    
    // BorgBackup keywords
    document.getElementById("keyword-archive-name").value = config.keywords?.archive_name || "Archive name";
    document.getElementById("keyword-repository").value = config.keywords?.repository || "Repository";
    document.getElementById("keyword-location").value = config.keywords?.location || "Location";
    document.getElementById("keyword-backup-size").value = config.keywords?.backup_size || "This archive";
    document.getElementById("keyword-original-size").value = config.keywords?.original_size || "Original size";
    document.getElementById("keyword-compressed-size").value = config.keywords?.compressed_size || "Compressed size";
    document.getElementById("keyword-deduplicated-size").value = config.keywords?.deduplicated_size || "Deduplicated size";
    document.getElementById("keyword-number-files").value = config.keywords?.number_files || "Number of files";
    document.getElementById("keyword-added-files").value = config.keywords?.added_files || "Added files";
    document.getElementById("keyword-modified-files").value = config.keywords?.modified_files || "Modified files";
    document.getElementById("keyword-unchanged-files").value = config.keywords?.unchanged_files || "Unchanged files";
    document.getElementById("keyword-duration").value = config.keywords?.duration || "Duration";
    document.getElementById("keyword-start-time").value = config.keywords?.start_time || "Start time";
    document.getElementById("keyword-end-time").value = config.keywords?.end_time || "End time";
    document.getElementById("keyword-status").value = config.keywords?.status || "terminating with";
    
    // Auto-refresh settings
    document.getElementById("backup-auto-refresh").checked = config.backup_auto_refresh || false;
    document.getElementById("backup-refresh-interval").value = config.backup_refresh_interval || 5;
    document.getElementById("smart-auto-refresh").checked = config.smart_auto_refresh || false;
    document.getElementById("smart-refresh-interval").value = config.smart_refresh_interval || 10;
    
    // SMART data settings
    document.getElementById("smart-log-format").value = config.smart_log_format || "smartctl-json";
    document.getElementById("smart-datetime-format").value = config.smart_datetime_format || "%Y-%m-%d %H:%M:%S";
    document.getElementById("smart-temp-monitoring").checked = config.smart_temp_monitoring !== false;
    document.getElementById("smart-health-monitoring").checked = config.smart_health_monitoring !== false;
    document.getElementById("smart-attribute-monitoring").checked = config.smart_attribute_monitoring !== false;
    
    // Show/hide backup sub-settings based on enabled state
    const subSettings = document.getElementById("backup-sub-settings");
    if (backupViewData.backup_view_enabled) {
      subSettings.classList.remove("hidden");
    } else {
      subSettings.classList.add("hidden");
    }

    // Store current settings
    currentSettings = {
      internal_ip: internalIpData.internal_ip || "127.0.0.1",
      external_ip: externalIpData.external_ip || "127.0.0.1",
      proxy_count: proxyData.proxy_count || 0,
      backup_view_enabled: backupViewData.backup_view_enabled || false,
      backup_config: config
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
    const backupViewEnabled = document.getElementById("backup-view-enabled").checked;
    
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
    
    // Save backup view enabled
    const backupViewRes = await fetch("/api/config/backup_view_enabled", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        backup_view_enabled: backupViewEnabled
      })
    });
    
    if (!backupViewRes.ok) {
      throw new Error("Failed to save backup view settings");
    }

    // Save backup configuration if backup view is enabled
    if (backupViewEnabled) {
      const backupConfig = {
        datetime_format: document.getElementById("backup-datetime-format").value || "%Y-%m-%d %H:%M:%S",
        keywords: {
          archive_name: document.getElementById("keyword-archive-name").value || "Archive name",
          repository: document.getElementById("keyword-repository").value || "Repository",
          location: document.getElementById("keyword-location").value || "Location",
          backup_size: document.getElementById("keyword-backup-size").value || "This archive",
          original_size: document.getElementById("keyword-original-size").value || "Original size",
          compressed_size: document.getElementById("keyword-compressed-size").value || "Compressed size",
          deduplicated_size: document.getElementById("keyword-deduplicated-size").value || "Deduplicated size",
          number_files: document.getElementById("keyword-number-files").value || "Number of files",
          added_files: document.getElementById("keyword-added-files").value || "Added files",
          modified_files: document.getElementById("keyword-modified-files").value || "Modified files",
          unchanged_files: document.getElementById("keyword-unchanged-files").value || "Unchanged files",
          duration: document.getElementById("keyword-duration").value || "Duration",
          start_time: document.getElementById("keyword-start-time").value || "Start time",
          end_time: document.getElementById("keyword-end-time").value || "End time",
          status: document.getElementById("keyword-status").value || "terminating with"
        },
        backup_auto_refresh: document.getElementById("backup-auto-refresh").checked,
        backup_refresh_interval: parseInt(document.getElementById("backup-refresh-interval").value) || 5,
        smart_auto_refresh: document.getElementById("smart-auto-refresh").checked,
        smart_refresh_interval: parseInt(document.getElementById("smart-refresh-interval").value) || 10,
        smart_log_format: document.getElementById("smart-log-format").value || "smartctl-json",
        smart_datetime_format: document.getElementById("smart-datetime-format").value || "%Y-%m-%d %H:%M:%S",
        smart_temp_monitoring: document.getElementById("smart-temp-monitoring").checked,
        smart_health_monitoring: document.getElementById("smart-health-monitoring").checked,
        smart_attribute_monitoring: document.getElementById("smart-attribute-monitoring").checked
      };

      const backupConfigRes = await fetch("/api/config/backup_config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          backup_config: backupConfig
        })
      });

      if (!backupConfigRes.ok) {
        throw new Error("Failed to save backup configuration");
      }
    }

    // Update current settings
    currentSettings = {
      internal_ip: internalIp,
      external_ip: externalIp,
      proxy_count: proxyCount,
      backup_view_enabled: backupViewEnabled
    };
    
    showStatus("Settings saved successfully!", "success");
    
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
      window.location.href = "/";
    }, 2000);
    
  } catch (err) {
    console.error("Failed to complete setup:", err);
    showStatus("Failed to complete setup: " + err.message, "error");
  }
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
    
    // Reset backup view to disabled
    const backupViewRes = await fetch("/api/config/backup_view_enabled", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        backup_view_enabled: false
      })
    });
    
    if (!backupViewRes.ok) {
      throw new Error("Failed to reset backup view settings");
    }

    // Reset backup configuration to defaults
    const defaultBackupConfig = {
      datetime_format: "%Y-%m-%d %H:%M:%S",
      keywords: {
        archive_name: "Archive name",
        repository: "Repository",
        location: "Location",
        backup_size: "This archive",
        original_size: "Original size",
        compressed_size: "Compressed size",
        deduplicated_size: "Deduplicated size",
        number_files: "Number of files",
        added_files: "Added files",
        modified_files: "Modified files",
        unchanged_files: "Unchanged files",
        duration: "Duration",
        start_time: "Start time",
        end_time: "End time",
        status: "terminating with"
      },
      backup_auto_refresh: false,
      backup_refresh_interval: 5,
      smart_auto_refresh: false,
      smart_refresh_interval: 10,
      smart_log_format: "smartctl-json",
      smart_datetime_format: "%Y-%m-%d %H:%M:%S",
      smart_temp_monitoring: true,
      smart_health_monitoring: true,
      smart_attribute_monitoring: true
    };

    const backupConfigRes = await fetch("/api/config/backup_config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        backup_config: defaultBackupConfig
      })
    });

    if (!backupConfigRes.ok) {
      throw new Error("Failed to reset backup configuration");
    }

    // Reset form values
    document.getElementById("internal-ip").value = "127.0.0.1";
    document.getElementById("external-ip").value = "127.0.0.1";
    document.getElementById("proxy-count").value = 0;
    document.getElementById("backup-view-enabled").checked = false;
    
    // Reset backup configuration form values
    document.getElementById("backup-datetime-format").value = "%Y-%m-%d %H:%M:%S";
    document.getElementById("keyword-archive-name").value = "Archive name";
    document.getElementById("keyword-repository").value = "Repository";
    document.getElementById("keyword-location").value = "Location";
    document.getElementById("keyword-backup-size").value = "This archive";
    document.getElementById("keyword-original-size").value = "Original size";
    document.getElementById("keyword-compressed-size").value = "Compressed size";
    document.getElementById("keyword-deduplicated-size").value = "Deduplicated size";
    document.getElementById("keyword-number-files").value = "Number of files";
    document.getElementById("keyword-added-files").value = "Added files";
    document.getElementById("keyword-modified-files").value = "Modified files";
    document.getElementById("keyword-unchanged-files").value = "Unchanged files";
    document.getElementById("keyword-duration").value = "Duration";
    document.getElementById("keyword-start-time").value = "Start time";
    document.getElementById("keyword-end-time").value = "End time";
    document.getElementById("keyword-status").value = "terminating with";
    document.getElementById("backup-auto-refresh").checked = false;
    document.getElementById("backup-refresh-interval").value = 5;
    document.getElementById("smart-auto-refresh").checked = false;
    document.getElementById("smart-refresh-interval").value = 10;
    document.getElementById("smart-log-format").value = "smartctl-json";
    document.getElementById("smart-datetime-format").value = "%Y-%m-%d %H:%M:%S";
    document.getElementById("smart-temp-monitoring").checked = true;
    document.getElementById("smart-health-monitoring").checked = true;
    document.getElementById("smart-attribute-monitoring").checked = true;
    
    // Hide backup sub-settings
    document.getElementById("backup-sub-settings").classList.add("hidden");
    
    currentSettings = {
      internal_ip: "127.0.0.1",
      external_ip: "127.0.0.1",
      proxy_count: 0,
      backup_view_enabled: false
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
