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
    
    // Update current settings
    currentSettings = {
      internal_ip: internalIp,
      external_ip: externalIp,
      proxy_count: proxyCount
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
