// monitor.js - basic scaffolding for the Monitor module

window.addEventListener('DOMContentLoaded', async () => {
    const root = document.getElementById('monitor-root');
    if (!root) return;

    const containerSelect = document.getElementById('monitor-container-select');
    const vmSelect = document.getElementById('monitor-vm-select');
    const activeSelect = document.getElementById('monitor-active-select');

    // Populate containers dropdown from existing containers API
    if (containerSelect) {
        try {
            const res = await fetch('/api/containers');
            if (res.ok) {
                const containers = await res.json();
                containers.forEach(c => {
                    const opt = document.createElement('option');
                    opt.value = c.id;
                    opt.textContent = c.name || c.id;
                    containerSelect.appendChild(opt);
                });
            }
        } catch (e) {
            console.error('Failed to load containers for monitor dropdown', e);
        }
    }

    // Populate VMs dropdown from database-backed VMs API
    if (vmSelect) {
        try {
            const res = await fetch('/api/vms');
            if (res.ok) {
                const vms = await res.json();
                vms.forEach(vm => {
                    const opt = document.createElement('option');
                    opt.value = vm.id;
                    opt.textContent = vm.name || vm.id;
                    vmSelect.appendChild(opt);
                });
            }
        } catch (e) {
            console.error('Failed to load VMs for monitor dropdown', e);
        }
    }

    // Populate "Actives" dropdown with monitor_bodies (monitor configurations)
    if (activeSelect) {
        try {
            const res = await fetch('/api/monitor/bodies');
            if (res.ok) {
                const bodies = await res.json();
                bodies.forEach(body => {
                    const opt = document.createElement('option');
                    opt.value = body.id;
                    const target = body.container_id || body.vm_id || `id:${body.id}`;
                    opt.textContent = `${target} (${body.monitor_type || 'monitor'})`;
                    activeSelect.appendChild(opt);
                });
            }
        } catch (e) {
            console.error('Failed to load monitor bodies for actives dropdown', e);
        }
    }
});
