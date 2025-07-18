let IP_FOR_INTERNAL_LINKS = "127.0.0.1";
let IP_FOR_EXPOSED_LINKS = "127.0.0.1";


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

  const res = await fetch("/api/containers");
  const data = await res.json();

  const composeMap = {};
  const containerList = document.getElementById("container-list");
  data.forEach(container => {
    const div = document.createElement("div");
    div.className = "bg-white p-4 rounded-lg shadow-md mb-4";  // Tailwind styles here


    const composeName = container.labels?.["com.docker.compose.project"] || "undefined";

    // Initialize array if it doesn't exist yet
    if (!composeMap[composeName]) {
      composeMap[composeName] = [];
    }
    // Push container into the array
    composeMap[composeName].push(container);

  });
  for (const [composeName, containers] of Object.entries(composeMap)) {
    const section = document.createElement("div");
    section.className = "mb-8";

    const header = document.createElement("h2");
    header.textContent = `Project: ${composeName}`;
    header.className = "text-xl font-bold mb-2";
    section.appendChild(header);

    containers.forEach(async container => {
      let portText = "No ports exposed";
      const hostPorts = [];
      const containerPorts = [];
      let hostIp = "";
      const portEntries = [];

      try {
        const portRes = await fetch(`/api/containers/ports/${container.name}`);
        const portData = await portRes.json();

        portData.forEach(port => {
          hostPorts.push(port.host_port);
          containerPorts.push(port.container_port);
          hostIp = port.host_ip;
          portEntries.push(`${hostIp}:${port.host_port} → ${port.container_port}`);
        });

        if (portEntries.length > 0) {
          portText = portEntries.join(", ");
        }
      } catch (err) {
        console.warn(`Failed to fetch ports for ${container.name}`, err);
      }
      const preferredPort = hostPorts[0];
      try {
        const prefferedPortRes = await fetch(`/api/config/preferred_ports/${container.name}`)
        const prefferedPortData = await prefferedPortRes.json();
        if(prefferedPortData[container.name]!==undefined) {
          preferredPort = prefferedPortData[container.name];
        }


      } catch (err) {
        console.info(`Failed to fetch prefferedPort for ${container.name}, generating new port config`, err);
      }
      try {
        const res = await fetch("/api/config/preferred_ports", {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({
            container_name: container.name,
            port: preferredPort
          })
        });

        if (!res.ok) {
          throw new Error("Failed to save preferred port");
        }
        console.log(`Preferred port saved for ${container.name}`);
      } catch (err) {
        console.warn("Error saving preferred port:", err);
      }

      let internalLinkHTML = "";
      if (preferredPort !== undefined) {
        internalLinkHTML = `Internal Link: <a href="http://${IP_FOR_INTERNAL_LINKS}:${preferredPort}" target="_blank" class="text-blue-600 underline">${IP_FOR_INTERNAL_LINKS}:${preferredPort}</a>`;
      }

      let externalLinkHTML = "";
      if (preferredPort !== undefined && container.labels?.exposed === "true") {
        externalLinkHTML = `<br>External Link: <a href="http://${IP_FOR_EXPOSED_LINKS}:${preferredPort}" target="_blank" class="text-blue-600 underline">${IP_FOR_EXPOSED_LINKS}:${preferredPort}</a>`;
      }

      const div = document.createElement("div");
      div.className = "bg-white p-4 rounded-lg shadow-md mb-2";
      div.innerHTML = `
        <strong>${container.name}</strong> - ${container.status}<br>
        Ports: ${portText}<br>
          ${internalLinkHTML}
          ${externalLinkHTML}
      `;
      section.appendChild(div);
    });

    containerList.appendChild(section);
  }
});