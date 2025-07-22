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

  //build a map  based on compose  projects
  data.forEach(container => {
    const composeName = container.labels?.["com.docker.compose.project"] || "undefined";

    if (!composeMap[composeName]) {
      composeMap[composeName] = [];
    }
    composeMap[composeName].push(container);

  });
  for (const [composeName, containers] of Object.entries(composeMap)) {
    //div for compose proojject
    const div = document.createElement("div");
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

      //Get ports  for container
      try {
        const portRes = await fetch(`/api/containers/ports/${container.id}`);
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

      //Getting/initialising preffered Port
      const preferredPort = hostPorts[0];
      try {
        const prefferedPortRes = await fetch(`/api/config/preferred_ports/${container.id}`)
        const prefferedPortData = await prefferedPortRes.json();
        if(prefferedPortData[container.id]!==undefined) {
          preferredPort = prefferedPortData[container.id];
        }
      } catch (err) {
        console.info(`Failed to fetch prefferedPort for ${container.id}, generating new port config`, err);
      }
      try {
        const res = await fetch("/api/config/preferred_ports", {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({
            container_id: container.id,
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

      //adding links based on preffered port and exposed toggle
      let internalLinkHTML = "";
      if (preferredPort !== undefined) {
        internalLinkHTML = `Internal Link: <a href="http://${IP_FOR_INTERNAL_LINKS}:${preferredPort}" target="_blank" class="text-blue-600 underline">${IP_FOR_INTERNAL_LINKS}:${preferredPort}</a>`;
      }
      let externalLinkHTML = "";
      if (preferredPort !== undefined && container.labels?.exposed === "true") {
        externalLinkHTML = `<br>External Link: <a href="http://${IP_FOR_EXPOSED_LINKS}:${preferredPort}" target="_blank" class="text-blue-600 underline">${IP_FOR_EXPOSED_LINKS}:${preferredPort}</a>`;
      }

      //actual  container div
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