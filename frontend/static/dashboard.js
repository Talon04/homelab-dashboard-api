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

    // Adding links based on preferred port and exposed status
    let internalLinkHTML = "";
    if (preferredPort !== undefined) {
      internalLinkHTML = `Internal Link: <a href="http://${IP_FOR_INTERNAL_LINKS}:${preferredPort}" target="_blank" class="text-blue-600 underline">${IP_FOR_INTERNAL_LINKS}:${preferredPort}</a>`;
    }
    let externalLinkHTML = "";
    if (preferredPort !== undefined && isExposed) {
      externalLinkHTML = `<br>External Link: <a href="http://${IP_FOR_EXPOSED_LINKS}:${preferredPort}" target="_blank" class="text-blue-600 underline">${IP_FOR_EXPOSED_LINKS}:${preferredPort}</a>`;
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
    
    if (!res.ok) throw new Error("Failed to update preferred port");
    
    // Store current expanded state and refresh
    const currentExpanded = expandedCompose;
    expandedCompose = currentExpanded;
    await window.renderComposeList();
  } catch (err) {
    console.error("Error setting preferred port:", err);
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
    
    if (!res.ok) throw new Error("Failed to update exposed status");
    
    // Store current expanded state and refresh
    const currentExpanded = expandedCompose;
    expandedCompose = currentExpanded;
    await window.renderComposeList();
  } catch (err) {
    console.error("Error toggling exposed status:", err);
  }
};