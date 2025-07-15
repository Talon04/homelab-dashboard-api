const IP_FOR_INTERNAL_LINKS = "192.168.8.152";
const IP_FOR_EXPOSED_LINKS = "192.168.8.152";

window.addEventListener("DOMContentLoaded", async () => {
  const res = await fetch("/api/containers");
  const data = await res.json();

  const containerList = document.getElementById("container-list");
  data.forEach(container => {
    const div = document.createElement("div");
    
    const portEntries = [];

    container.ports && Object.entries(container.ports).forEach(([containerPort, mappings]) => {
      if (Array.isArray(mappings)) {
        mappings.forEach(m => {
          portEntries.push(`${m.HostIp}:${m.HostPort} → ${containerPort}`);
        });
      } else {
        portEntries.push(`${containerPort} (not mapped)`);
      }
    });

    const portlist = portEntries.join(", ");
    const portLine = portlist.length ? `Ports: ${portlist}` : "No ports exposed";

    let urlLine = "";
    if (portEntries.length > 0) {
      const firstMapping = Object.values(container.ports)[0][0];
      const url = `http://${IP_FOR_INTERNAL_LINKS}:${firstMapping.HostPort}`;
      urlLine = `Link: <a href="${url}" target="_blank">${url}</a>`;
    }

    let extraLine = "";
    if (container.labels?.exposed === "true") {
      const firstMapping = Object.values(container.ports)[0][0];
      const exposedUrl = `http://${IP_FOR_EXPOSED_LINKS}:${firstMapping.HostPort}`;
      extraLine = `Exposed: <a href="${exposedUrl}" target="_blank">${exposedUrl}</a>`;
    }

    div.innerHTML = `
      <strong>${container.name}</strong> - ${container.status} <br> 
      ${portLine} <br>
      ${urlLine} <br>
      ${extraLine}
    `;

    containerList.appendChild(div);
  });
});
