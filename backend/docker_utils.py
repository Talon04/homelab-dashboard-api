import docker

useDocker = False
def list_containers():
    if useDocker:
        print("[DEBUG] Attempting real Docker access")
        try:
            client = docker.from_env()
            containers = client.containers.list(all=True)
            return [
                {
                    "id" : c.id,
                    "name": c.name,
                    "status": c.status,
                    "ports": c.attrs['NetworkSettings']['Ports'],
                    "labels": c.attrs.get('Config', {}).get('Labels', {})
                }
                for c in containers
            ]
        except Exception as e:
            print("[WARN] Docker not available, using mock data:", e)
            return []
    else:
        return [
            {
                "id" : "dadkönfm",
                "name": "mock_container_1",
                "status": "running",
                "ports": {"80/tcp": [{"HostIp": "127.0.0.1", "HostPort": "8080"}]},
                "labels": {"exposed": "true", "com.docker.compose.project": "mock_project"}
            },
            {
                "id" : "dadköndanwlänfm",                
                "name": "mock_container_2",
                "status": "exited",
                "ports": {},
                "labels": {"com.docker.compose.project": "mock_project"}
            },
            {
                "id" : "dadköndanwlänfmdaw",
                "name": "mock_container_3",
                "status": "exited",
                "ports": {},
                "labels": {}
            },
        ]
def get_container_ports(container_id):
    if useDocker:
        print("[DEBUG] Attempting real Docker access")
        try:
            client = docker.from_env()
            container = client.containers.get(container_id)
            ports = container.attrs['NetworkSettings']['Ports']
            port_list = []
            for container_port, mappings in ports.items():
                if mappings is None:
                    continue  # no port mapped
                for m in mappings:
                    port_list.append({
                        "container_port": container_port,
                        "host_ip": m["HostIp"],
                        "host_port": m["HostPort"]
                    })
            return port_list

        except Exception as e:
            print("[WARN] Docker not available, using mock data:", e)
            return []
    else:
        return [
            {
                "container_port": "80/tcp",
                "host_ip": "127.0.0.1",
                "host_port": "8080"
            }
        ]
    
