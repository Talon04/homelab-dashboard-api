let IP_FOR_INTERNAL_LINKS = "127.0.0.1";
let IP_FOR_EXPOSED_LINKS = "127.0.0.1";
let expandedCompose = null;
let composeMap = {};
window.addEventListener("DOMContentLoaded", async () => {
  // Load IP config first
  try {
    const configRes = await fetch("/api/config");
    const configData = await configRes.json();
    IP_FOR_INTERNAL_LINKS = configData.internal_ip;
    IP_FOR_EXPOSED_LINKS = configData.external_ip;
  } catch (err) {
    console.warn("Failed to load IP config, using defaults");
  }


  // Build a map based on docker compose projects
  const res = await fetch("/api/containers");
  const data = await res.json();
  composeMap = {};
  const containerList = document.getElementById("container-list");
  containerList.innerHTML = "";
  data.forEach(container => {
    const composeName = container.labels?.["com.docker.compose.project"] || "undefined";
    if (!composeMap[composeName]) {
      composeMap[composeName] = [];
    }
    composeMap[composeName].push(container);
  });

  // Render each compose project with its  containers (icons) 
window.renderComposeList = async function() {
  const containerList = document.getElementById("container-list");
  containerList.innerHTML = "";
  for (const [composeName, containers] of Object.entries(composeMap)) {
    // Compose line
    const composeLine = document.createElement("div");
    composeLine.className = "flex items-center justify-between bg-gray-100 rounded p-3 mb-2 shadow";
    
    // Compose name 
    const left = document.createElement("div");
    left.className = "flex items-center gap-4";
    const nameSpan = document.createElement("span");
    nameSpan.className = "font-semibold text-lg";
    nameSpan.textContent = composeName;
    left.appendChild(nameSpan);
    
    // Container Images
    containers.forEach(c => {
      const imgSpan = document.createElement("span");
      imgSpan.className = "ml-2 px-2 py-1 bg-blue-200 rounded text-xs";
      imgSpan.textContent = c.image || c.name;
      left.appendChild(imgSpan);
    });
    composeLine.appendChild(left);

    // Expand Toggle button
    const toggleBtn = document.createElement("button");
    toggleBtn.className = "ml-4 px-2 py-1 bg-blue-500 text-white rounded hover:bg-blue-600 focus:outline-none";
    toggleBtn.textContent = expandedCompose === composeName ? "▲" : "▼";
    toggleBtn.title = expandedCompose === composeName ? "Collapse" : "Expand";
    toggleBtn.onclick = async () => {
      expandedCompose = expandedCompose === composeName ? null : composeName;
      await window.renderComposeList();
    };
    composeLine.appendChild(toggleBtn);

    containerList.appendChild(composeLine);

    // Expanded details - AWAIT the async rendering
    if (expandedCompose === composeName) {
      const detailsDiv = document.createElement("div");
      detailsDiv.className = "mb-6 pl-8";
      
      // Use for...of to properly await each container
      for (const container of containers) {
        await renderContainerDetails(container, detailsDiv);
      }
      
      containerList.appendChild(detailsDiv);
    }
  }
}
await window.renderComposeList();


  async function renderContainerDetails(container, parentDiv) {
    let portText = "No ports exposed";
    const hostPorts = [];
    const containerPorts = [];
    let hostIp = "";
    const portEntries = [];

    // Get ports for container
    try {
      const portRes = await fetch(`/api/containers/ports/${container.id}`);
      const portData = await portRes.json();
      
      if (portData.length > 0) {
        // Create ports list with clickable items
        portText = "<div class='flex flex-wrap gap-1 mt-1'>";
        portData.forEach(port => {
          hostPorts.push(port.host_port);
          containerPorts.push(port.container_port);
          hostIp = port.host_ip;
          
          // Create clickable port badge
          portText += `<span class="port-badge px-2 py-1 bg-gray-100 hover:bg-blue-100 rounded text-xs cursor-pointer" 
                          data-port="${port.host_port}" 
                          data-container="${container.id}"
                          onclick="setPreferredPort('${container.id}', '${port.host_port}')"
                          title="Click to set as preferred port">
                          ${hostIp}:${port.host_port} → ${port.container_port}
                       </span>`;
        });
        portText += "</div>";
      }else {
        console.warn(`No ports found for container ${container.name}`);
      }
    } catch (err) {
      console.warn(`Failed to fetch ports for ${container.name}`, err);
    }

    // Getting/initialising preferred Port
    let preferredPort = hostPorts[0];
    try {
      const preferredPortRes = await fetch(`/api/config/preferred_ports/${container.id}`);
      const preferredPortData = await preferredPortRes.json();
      if (preferredPortData.preferred_port !== undefined) {
        preferredPort = preferredPortData.preferred_port;
      }
    } catch (err) {
      console.info(`Failed to fetch preferredPort for ${container.id}`, err);
    }
        
    // Check if container is exposed
    let isExposed = false;
    try {
      const exposedRes = await fetch("/api/config/exposed_containers");
      const exposedContainers = await exposedRes.json();
      isExposed = exposedContainers.includes(container.id);
    } catch (err) {
      console.warn("Error getting exposed containers:", err);
    }

    // Check for custom link bodies (internal and external separately)
    let customInternalLinkBody = null;
    let customExternalLinkBody = null;
    
    try {
      const internalLinkRes = await fetch(`/api/config/link_bodies/${container.id}`);
      const internalLinkData = await internalLinkRes.json();
      
      console.log(`DEBUG: Internal link data for ${container.id}:`, internalLinkData, typeof internalLinkData);
      
      if (typeof internalLinkData === 'string' && internalLinkData.trim() !== "") {
        customInternalLinkBody = internalLinkData;
        console.log(`DEBUG: Using custom internal link: ${customInternalLinkBody}`);
      }
    } catch (err) {
      console.info("No custom internal link body found for", container.id, err);
    }
    
    try {
      const externalLinkRes = await fetch(`/api/config/external_link_bodies/${container.id}`);
      const externalLinkData = await externalLinkRes.json();
      
      console.log(`DEBUG: External link data for ${container.id}:`, externalLinkData, typeof externalLinkData);
      
      if (typeof externalLinkData === 'string' && externalLinkData.trim() !== "") {
        customExternalLinkBody = externalLinkData;
        console.log(`DEBUG: Using custom external link: ${customExternalLinkBody}`);
      }
    } catch (err) {
      console.info("No custom external link body found for", container.id, err);
    }    // Adding links based on preferred port and exposed status
    let internalLinkHTML = "";
    if (preferredPort !== undefined) {
      const internalUrl = customInternalLinkBody || `http://${IP_FOR_INTERNAL_LINKS}:${preferredPort}`;
      internalLinkHTML = `Internal Link: <a href="${internalUrl}" target="_blank" class="text-blue-600 underline">${internalUrl}</a>
      <button onclick="editLink('${container.id}', 'internal')" class="ml-2 text-gray-500 hover:text-blue-600" title="Edit custom link">
        ✏️
      </button>`;
    }
    let externalLinkHTML = "";
    if (preferredPort !== undefined && isExposed) {
      const externalUrl = customExternalLinkBody || `http://${IP_FOR_EXPOSED_LINKS}:${preferredPort}`;
      externalLinkHTML = `<br>External Link: <a href="${externalUrl}" target="_blank" class="text-blue-600 underline">${externalUrl}</a>
      <button onclick="editLink('${container.id}', 'external')" class="ml-2 text-gray-500 hover:text-blue-600" title="Edit custom link">
        ✏️
      </button>`;
    }

    // Actual container div
    const div = document.createElement("div");
    div.className = "bg-white p-4 rounded-lg shadow-md mb-2";

    // Create exposed toggle button (inline next to status)
    const exposedToggleBtn = `<button 
      class="ml-2 px-2 py-1 text-xs rounded ${isExposed ? 'bg-green-500 text-white' : 'bg-gray-300'}" 
      onclick="toggleExposed('${container.id}', ${!isExposed})">
      ${isExposed ? 'Exposed' : 'Not Exposed'}
    </button>`;

    div.innerHTML = `
      <strong>${container.name}</strong> - ${container.status} ${exposedToggleBtn}<br>
      <div class="mb-1">Image: <span class='font-mono text-xs'>${container.image || "-"}</span></div>
      <div class="mb-1">Ports: ${portText}</div>
      <div class="mt-2">${internalLinkHTML}</div>
      <div>${externalLinkHTML}</div>
    `;
    parentDiv.appendChild(div);
  }

  // Initial render
  renderComposeList();
});

// Helpers 
window.setPreferredPort = async function(containerId, port) {
  try {
    const res = await fetch("/api/config/preferred_ports", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        container_id: containerId,
        port: port
      })
    });
    
    if (!res.ok) {
      const errorData = await res.json().catch(() => ({}));
      throw new Error(errorData.error || "Failed to update preferred port");
    }
    
    // Store current expanded state and refresh
    const currentExpanded = expandedCompose;
    expandedCompose = currentExpanded;
    await window.renderComposeList();
    
    window.toastManager.success(`Preferred port set to ${port}`);
  } catch (err) {
    console.error("Error setting preferred port:", err);
    window.toastManager.error('Failed to set preferred port: ' + err.message);
  }
};

window.toggleExposed = async function(containerId, exposed) {
  try {
    const res = await fetch("/api/config/exposed_containers", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        container_id: containerId,
        exposed: exposed
      })
    });
    
    if (!res.ok) {
      const errorData = await res.json().catch(() => ({}));
      throw new Error(errorData.error || "Failed to update exposed status");
    }
    
    // Store current expanded state and refresh
    const currentExpanded = expandedCompose;
    expandedCompose = currentExpanded;
    await window.renderComposeList();
    
    window.toastManager.success(`Container ${exposed ? 'exposed' : 'hidden'}`);
  } catch (err) {
    console.error("Error toggling exposed status:", err);
    window.toastManager.error('Failed to update exposed status: ' + err.message);
  }
};

window.editLink = async function(containerId, linkType) {
  try {
    // Get current custom link body based on type
    let currentUrl = "";
    let hasCustomLink = false;
    
    const apiEndpoint = linkType === 'internal' 
      ? `/api/config/link_bodies/${containerId}`
      : `/api/config/external_link_bodies/${containerId}`;
    
    try {
      const linkRes = await fetch(apiEndpoint);
      const linkData = await linkRes.json();
      
      console.log(`DEBUG: Edit ${linkType} link data for ${containerId}:`, linkData, typeof linkData);
      
      if (typeof linkData === 'string' && linkData.trim() !== "") {
        currentUrl = linkData;
        hasCustomLink = true;
        console.log(`DEBUG: Edit using existing custom ${linkType} link: ${currentUrl}`);
      }
    } catch (err) {
      console.info(`No existing custom ${linkType} link found`);
    }
    
    // If no custom link, use default format
    if (!currentUrl) {
      // Get preferred port for default URL
      try {
        const portRes = await fetch(`/api/config/preferred_ports/${containerId}`);
        const portData = await portRes.json();
        const port = portData.preferred_port;
        currentUrl = linkType === 'internal' 
          ? `http://${IP_FOR_INTERNAL_LINKS}:${port}`
          : `http://${IP_FOR_EXPOSED_LINKS}:${port}`;
      } catch (err) {
        currentUrl = linkType === 'internal' 
          ? `http://${IP_FOR_INTERNAL_LINKS}:8080`
          : `http://${IP_FOR_EXPOSED_LINKS}:8080`;
      }
    }
    
    const title = hasCustomLink ? 'Edit Custom Link' : 'Set Custom Link';
    const message = hasCustomLink 
      ? `Editing custom ${linkType} link. Leave empty to reset to default.`
      : `Enter a custom ${linkType} link for this container.`;
    
    window.modalManager.prompt(
      title,
      message,
      currentUrl,
      async (newUrl) => {
        // Handle the user's input
        if (newUrl.trim() === "" && hasCustomLink) {
          // User wants to reset to default - clear the custom link
          await clearCustomLink(containerId, linkType);
          window.toastManager.success(`${linkType.charAt(0).toUpperCase() + linkType.slice(1)} link reset to default`);
        } else if (newUrl && newUrl !== currentUrl) {
          // User entered a new URL
          await setCustomLink(containerId, newUrl, linkType);
          window.toastManager.success(`Custom ${linkType} link saved`);
        }
      },
      null, // onCancel - do nothing
      {
        label: `${linkType.charAt(0).toUpperCase() + linkType.slice(1)} Link URL`,
        placeholder: 'Enter URL (e.g., http://example.com or mydomain.local)',
        confirmText: 'Save Link'
      }
    );
    
  } catch (err) {
    console.error("Error editing link:", err);
    window.toastManager.error('Failed to edit link: ' + err.message);
  }
};

async function setCustomLink(containerId, customUrl, linkType) {
  try {
    // Ensure URL has a protocol
    let normalizedUrl = customUrl.trim();
    if (normalizedUrl && !normalizedUrl.startsWith('http://') && !normalizedUrl.startsWith('https://')) {
      normalizedUrl = 'http://' + normalizedUrl;
    }
    
    const apiEndpoint = linkType === 'internal' 
      ? "/api/config/link_bodies"
      : "/api/config/external_link_bodies";
    
    const res = await fetch(apiEndpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        container_id: containerId,
        link_body: normalizedUrl
      })
    });
    
    if (!res.ok) {
      const errorData = await res.json().catch(() => ({}));
      throw new Error(errorData.error || `Failed to update custom ${linkType} link`);
    }
    
    // Store current expanded state and refresh
    const currentExpanded = expandedCompose;
    expandedCompose = currentExpanded;
    await window.renderComposeList();
  } catch (err) {
    console.error(`Error setting custom ${linkType} link:`, err);
    window.toastManager.error(`Failed to save custom ${linkType} link: ` + err.message);
    throw err; // Re-throw so caller can handle it
  }
};

async function clearCustomLink(containerId, linkType) {
  try {
    const apiEndpoint = linkType === 'internal' 
      ? "/api/config/link_bodies"
      : "/api/config/external_link_bodies";
    
    const res = await fetch(apiEndpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        container_id: containerId,
        link_body: "" // Send empty string to clear
      })
    });
    
    if (!res.ok) {
      const errorData = await res.json().catch(() => ({}));
      throw new Error(errorData.error || `Failed to clear custom ${linkType} link`);
    }
    
    // Store current expanded state and refresh
    const currentExpanded = expandedCompose;
    expandedCompose = currentExpanded;
    await window.renderComposeList();
  } catch (err) {
    console.error(`Error clearing custom ${linkType} link:`, err);
    window.toastManager.error(`Failed to reset ${linkType} link: ` + err.message);
    throw err;
  }
};