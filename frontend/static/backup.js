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
    
    // Fetch backup summary from API
    const response = await fetch("/api/backup/summary");
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    
    const backupData = await response.json();
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
    
    // Fetch SMART data from API
    const response = await fetch("/api/smart/summary");
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    
    const smartData = await response.json();
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
  
  if (data.total_backups === 0) {
    backupContent.innerHTML = `
      <div class="text-center py-8 text-gray-500">
        <p class="text-lg mb-2">📁 No backup data found</p>
        <p class="text-sm">Place backup log files in /backend/data/backup_logs/</p>
      </div>
    `;
    return;
  }
  
  const statusColor = data.status === 'healthy' ? 'text-green-600' : 
                     data.status === 'warning' ? 'text-yellow-600' : 'text-red-600';
  const statusIcon = data.status === 'healthy' ? '✅' : 
                    data.status === 'warning' ? '⚠️' : '❌';
  
  const lastBackup = data.last_backup;
  const lastBackupTime = lastBackup?.start_time || lastBackup?.timestamp || 'Unknown';
  const backupSize = lastBackup?.backup_size || data.total_size || 'Unknown';
  const oldestBackup = data.oldest_backup?.start_time || data.oldest_backup?.timestamp || 'Unknown';
  
  backupContent.innerHTML = `
    <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
      <div class="bg-gray-50 rounded-lg p-4">
        <h3 class="text-sm font-medium text-gray-500 mb-1">Status</h3>
        <p class="text-lg font-semibold ${statusColor}">${statusIcon} ${data.status.toUpperCase()}</p>
      </div>
      <div class="bg-gray-50 rounded-lg p-4">
        <h3 class="text-sm font-medium text-gray-500 mb-1">Last Backup</h3>
        <p class="text-lg font-semibold">${lastBackupTime}</p>
      </div>
      <div class="bg-gray-50 rounded-lg p-4">
        <h3 class="text-sm font-medium text-gray-500 mb-1">Backup Size</h3>
        <p class="text-lg font-semibold">${backupSize}</p>
      </div>
    </div>
    
    <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
      <div class="bg-gray-50 rounded-lg p-4">
        <h3 class="text-sm font-medium text-gray-500 mb-1">Total Backups</h3>
        <p class="text-lg font-semibold">${data.total_backups}</p>
      </div>
      <div class="bg-gray-50 rounded-lg p-4">
        <h3 class="text-sm font-medium text-gray-500 mb-1">Successful</h3>
        <p class="text-lg font-semibold text-green-600">${data.successful_backups}</p>
      </div>
      <div class="bg-gray-50 rounded-lg p-4">
        <h3 class="text-sm font-medium text-gray-500 mb-1">Failed</h3>
        <p class="text-lg font-semibold text-red-600">${data.failed_backups}</p>
      </div>
    </div>

    <div class="bg-gray-50 rounded-lg p-4">
      <h3 class="text-sm font-medium text-gray-500 mb-1">Oldest Backup</h3>
      <p class="text-lg font-semibold">${oldestBackup}</p>
    </div>
  `;
}

function renderSmartStats(data) {
  const smartContent = document.getElementById("smart-content");
  
  if (data.total_drives === 0) {
    smartContent.innerHTML = `
      <div class="text-center py-8 text-gray-500">
        <p class="text-lg mb-2">💾 No SMART data found</p>
        <p class="text-sm">Place SMART log files in /backend/data/smart_logs/</p>
      </div>
    `;
    return;
  }

  const statusColor = data.status === 'healthy' ? 'text-green-600' : 
                     data.status === 'warning' ? 'text-yellow-600' : 'text-red-600';
  const statusIcon = data.status === 'healthy' ? '✅' : 
                    data.status === 'warning' ? '⚠️' : '❌';
  
  // System overview
  let systemHtml = `
    <div class="mb-6">
      <h3 class="text-lg font-medium mb-3">System Overview</h3>
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div class="bg-gray-50 rounded-lg p-3">
          <p class="text-sm text-gray-500">Overall Status</p>
          <p class="font-semibold ${statusColor}">${statusIcon} ${data.status.toUpperCase()}</p>
        </div>
        <div class="bg-gray-50 rounded-lg p-3">
          <p class="text-sm text-gray-500">Total Drives</p>
          <p class="font-semibold">${data.total_drives}</p>
        </div>
        <div class="bg-gray-50 rounded-lg p-3">
          <p class="text-sm text-gray-500">Healthy</p>
          <p class="font-semibold text-green-600">${data.healthy_drives}</p>
        </div>
        <div class="bg-gray-50 rounded-lg p-3">
          <p class="text-sm text-gray-500">Issues</p>
          <p class="font-semibold text-red-600">${data.failed_drives + data.warning_drives}</p>
        </div>
      </div>
      
      ${data.average_temp || data.max_temp ? `
      <div class="grid grid-cols-2 gap-4 mt-4">
        ${data.average_temp ? `
        <div class="bg-gray-50 rounded-lg p-3">
          <p class="text-sm text-gray-500">Average Temperature</p>
          <p class="font-semibold">${Math.round(data.average_temp)}°C</p>
        </div>
        ` : ''}
        ${data.max_temp ? `
        <div class="bg-gray-50 rounded-lg p-3">
          <p class="text-sm text-gray-500">Max Temperature</p>
          <p class="font-semibold">${Math.round(data.max_temp)}°C</p>
        </div>
        ` : ''}
      </div>
      ` : ''}
    </div>
  `;
  
  // Drive details
  let drivesHtml = `
    <div>
      <h3 class="text-lg font-medium mb-3">Drive Health</h3>
      <div class="space-y-4">
  `;
  
  if (data.drives && data.drives.length > 0) {
    data.drives.forEach(drive => {
      const healthColor = drive.health_status === 'healthy' ? 'text-green-600' : 
                         drive.health_status === 'warning' ? 'text-yellow-600' : 'text-red-600';
      const healthIcon = drive.health_status === 'healthy' ? '✅' : 
                        drive.health_status === 'warning' ? '⚠️' : '❌';
      
      drivesHtml += `
        <div class="border rounded-lg p-4 bg-gray-50">
          <div class="flex items-center justify-between mb-2">
            <h4 class="font-medium">${drive.device || 'Unknown'} - ${drive.model || 'Unknown Model'}</h4>
            <span class="text-sm ${healthColor} font-semibold">${healthIcon} ${drive.health_status?.toUpperCase() || 'UNKNOWN'}</span>
          </div>
          <div class="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
            ${drive.temperature ? `
            <div>
              <p class="text-gray-500">Temperature</p>
              <p class="font-medium">${drive.temperature}°C</p>
            </div>
            ` : ''}
            <div>
              <p class="text-gray-500">Serial Number</p>
              <p class="font-medium">${drive.serial || 'N/A'}</p>
            </div>
            <div>
              <p class="text-gray-500">Last Updated</p>
              <p class="font-medium">${drive.timestamp ? new Date(drive.timestamp).toLocaleDateString() : 'N/A'}</p>
            </div>
          </div>
        </div>
      `;
    });
  }
  
  drivesHtml += `
      </div>
    </div>
  `;
  
  smartContent.innerHTML = systemHtml + drivesHtml;
}
