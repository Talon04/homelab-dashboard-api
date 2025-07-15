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
                "labels": {"exposed": "true"}
            },
            {
                "name": "mock_container_2",
                "status": "exited",
                "ports": {}
            }
        ]
