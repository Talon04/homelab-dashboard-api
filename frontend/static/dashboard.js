const IP_FOR_INTERNAL_LINKS = "192.168.8.152";
const IP_FOR_EXPOSED_LINKS = "192.168.8.152";

window.addEventListener("DOMContentLoaded", async () => {
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


      let internalLinkHTML = "";
      if (hostPorts[0] !== undefined) {
        internalLinkHTML = `Internal Link: <a href="http://${IP_FOR_INTERNAL_LINKS}:${hostPorts[0]}" target="_blank" class="text-blue-600 underline">${IP_FOR_INTERNAL_LINKS}:${hostPorts[0]}</a>`;
      }

      let externalLinkHTML = "";
      if (hostPorts[0] !== undefined && container.labels?.exposed === "true") {
        externalLinkHTML = `<br>External Link: <a href="http://${IP_FOR_EXPOSED_LINKS}:${hostPorts[0]}" target="_blank" class="text-blue-600 underline">${IP_FOR_EXPOSED_LINKS}:${hostPorts[0]}</a>`;
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