window.addEventListener("DOMContentLoaded", async () => {
  // Load initial data
  await loadBackupStats();
  await loadSmartStats();
  
  // Event listeners
  document.getElementById("refresh-backup").addEventListener("click", loadBackupStats);
  document.getElementById("refresh-smart").addEventListener("click", loadSmartStats);
});

async function loadBackupStats() {
  const backupContent = document.getElementById("backup-content");
  
  try {
    // Show loading state
    backupContent.innerHTML = `
      <div class="text-center py-8 text-gray-500">
        <div class="animate-spin h-8 w-8 border-b-2 border-blue-500 rounded-full mx-auto mb-2"></div>
        Loading backup information...
      </div>
    `;
    
    // TODO: Replace with actual backup API endpoint when available
    // For now, simulate backup data
    await new Promise(resolve => setTimeout(resolve, 1000)); // Simulate loading
    
    // Mock backup data - replace with real API call
    const backupData = {
      last_backup: "2024-09-03 14:30:00",
      backup_size: "2.4 GB",
      status: "healthy",
      next_scheduled: "2024-09-04 02:00:00",
      backups_count: 15,
      oldest_backup: "2024-08-01 02:00:00"
    };
    
    renderBackupStats(backupData);
    
  } catch (err) {
    console.error("Failed to load backup stats:", err);
    backupContent.innerHTML = `
      <div class="text-center py-8 text-red-500">
        <p>❌ Failed to load backup information</p>
        <p class="text-sm mt-2">${err.message}</p>
      </div>
    `;
  }
}

async function loadSmartStats() {
  const smartContent = document.getElementById("smart-content");
  
  try {
    // Show loading state
    smartContent.innerHTML = `
      <div class="text-center py-8 text-gray-500">
        <div class="animate-spin h-8 w-8 border-b-2 border-green-500 rounded-full mx-auto mb-2"></div>
        Loading system information...
      </div>
    `;
    
    // TODO: Replace with actual smartctl API endpoint when available
    // For now, simulate SMART data
    await new Promise(resolve => setTimeout(resolve, 1200)); // Simulate loading
    
    // Mock SMART data - replace with real API call
    const smartData = {
      drives: [
        {
          device: "/dev/sda",
          model: "Samsung SSD 970 EVO Plus 1TB",
          health: "PASSED",
          temperature: "42°C",
          power_on_hours: "8760",
          total_lbas_written: "15,420,892"
        },
        {
          device: "/dev/sdb", 
          model: "WD Red 4TB WD40EFAX",
          health: "PASSED",
          temperature: "38°C",
          power_on_hours: "12,450",
          total_lbas_written: "8,920,341"
        }
      ],
      system: {
        uptime: "15 days, 4 hours",
        cpu_temp: "52°C",
        memory_usage: "68%",
        disk_usage: "45%"
      }
    };
    
    renderSmartStats(smartData);
    
  } catch (err) {
    console.error("Failed to load SMART stats:", err);
    smartContent.innerHTML = `
      <div class="text-center py-8 text-red-500">
        <p>❌ Failed to load system information</p>
        <p class="text-sm mt-2">${err.message}</p>
      </div>
    `;
  }
}

function renderBackupStats(data) {
  const backupContent = document.getElementById("backup-content");
  
  const statusColor = data.status === 'healthy' ? 'text-green-600' : 'text-red-600';
  const statusIcon = data.status === 'healthy' ? '✅' : '❌';
  
  backupContent.innerHTML = `
    <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
      <div class="bg-gray-50 rounded-lg p-4">
        <h3 class="text-sm font-medium text-gray-500 mb-1">Status</h3>
        <p class="text-lg font-semibold ${statusColor}">${statusIcon} ${data.status.toUpperCase()}</p>
      </div>
      <div class="bg-gray-50 rounded-lg p-4">
        <h3 class="text-sm font-medium text-gray-500 mb-1">Last Backup</h3>
        <p class="text-lg font-semibold">${data.last_backup}</p>
      </div>
      <div class="bg-gray-50 rounded-lg p-4">
        <h3 class="text-sm font-medium text-gray-500 mb-1">Backup Size</h3>
        <p class="text-lg font-semibold">${data.backup_size}</p>
      </div>
    </div>
    
    <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
      <div class="bg-gray-50 rounded-lg p-4">
        <h3 class="text-sm font-medium text-gray-500 mb-1">Next Scheduled</h3>
        <p class="text-lg font-semibold">${data.next_scheduled}</p>
      </div>
      <div class="bg-gray-50 rounded-lg p-4">
        <h3 class="text-sm font-medium text-gray-500 mb-1">Total Backups</h3>
        <p class="text-lg font-semibold">${data.backups_count}</p>
      </div>
      <div class="bg-gray-50 rounded-lg p-4">
        <h3 class="text-sm font-medium text-gray-500 mb-1">Oldest Backup</h3>
        <p class="text-lg font-semibold">${data.oldest_backup}</p>
      </div>
    </div>
  `;
}

function renderSmartStats(data) {
  const smartContent = document.getElementById("smart-content");
  
  // System overview
  let systemHtml = `
    <div class="mb-6">
      <h3 class="text-lg font-medium mb-3">System Overview</h3>
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div class="bg-gray-50 rounded-lg p-3">
          <p class="text-sm text-gray-500">Uptime</p>
          <p class="font-semibold">${data.system.uptime}</p>
        </div>
        <div class="bg-gray-50 rounded-lg p-3">
          <p class="text-sm text-gray-500">CPU Temp</p>
          <p class="font-semibold">${data.system.cpu_temp}</p>
        </div>
        <div class="bg-gray-50 rounded-lg p-3">
          <p class="text-sm text-gray-500">Memory</p>
          <p class="font-semibold">${data.system.memory_usage}</p>
        </div>
        <div class="bg-gray-50 rounded-lg p-3">
          <p class="text-sm text-gray-500">Disk Usage</p>
          <p class="font-semibold">${data.system.disk_usage}</p>
        </div>
      </div>
    </div>
  `;
  
  // Drive details
  let drivesHtml = `
    <div>
      <h3 class="text-lg font-medium mb-3">Drive Health</h3>
      <div class="space-y-4">
  `;
  
  data.drives.forEach(drive => {
    const healthColor = drive.health === 'PASSED' ? 'text-green-600' : 'text-red-600';
    const healthIcon = drive.health === 'PASSED' ? '✅' : '❌';
    
    drivesHtml += `
      <div class="border rounded-lg p-4 bg-gray-50">
        <div class="flex items-center justify-between mb-2">
          <h4 class="font-medium">${drive.device} - ${drive.model}</h4>
          <span class="text-sm ${healthColor} font-semibold">${healthIcon} ${drive.health}</span>
        </div>
        <div class="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
          <div>
            <p class="text-gray-500">Temperature</p>
            <p class="font-medium">${drive.temperature}</p>
          </div>
          <div>
            <p class="text-gray-500">Power On Hours</p>
            <p class="font-medium">${drive.power_on_hours}</p>
          </div>
          <div>
            <p class="text-gray-500">Total LBAs Written</p>
            <p class="font-medium">${drive.total_lbas_written}</p>
          </div>
        </div>
      </div>
    `;
  });
  
  drivesHtml += `
      </div>
    </div>
  `;
  
  smartContent.innerHTML = systemHtml + drivesHtml;
}
