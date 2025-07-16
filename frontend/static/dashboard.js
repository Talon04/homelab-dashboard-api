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

    containers.forEach(container => {
        const div = document.createElement("div");
        div.className = "bg-white p-4 rounded-lg shadow-md mb-2";
        div.innerHTML = `
        <strong>${container.name}</strong> - ${container.status}<br>
        Port: ${container.ports}
        `;
        section.appendChild(div);
    });

  document.getElementById("container-list").appendChild(section);
}})
