import docker

def list_containers():
    try:
        client = docker.from_env()
        containers = client.containers.list(all=True)
        return [
            {
                "name": c.name,
                "status": c.status,
                "ports": c.attrs['NetworkSettings']['Ports']
            }
            for c in containers
        ]
    except Exception as e:
        print("[WARN] Docker not available, using mock data:", e)
        return [
            {
                "name": "mock_container_1",
                "status": "running",
                "ports": {"80/tcp": [{"HostIp": "127.0.0.1", "HostPort": "8080"}]},
                "labels": {"exposed": "true", "com.docker.compose.project": "mock_project"}
            },
            {
                "name": "mock_container_2",
                "status": "exited",
                "ports": {},
                "labels": {"com.docker.compose.project": "mock_project"}
            },
            {
                "name": "mock_container_3",
                "status": "exited",
                "ports": {},
                "labels": {}
            },
        ]
def get_container_ports(container_name):
    try:
        client = docker.from_env()
        container = client.containers.get(container_name)
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
        return [{
            "container_port": "80/tcp",
            "host_ip": "127.0.0.1",
            "host_port": "8080"
        }]
