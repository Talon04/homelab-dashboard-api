import json


def tryGenerateConfig():
    import os
    import json

    config_path = "config/config.json"
    if not os.path.exists(config_path):
        default_config = {
            "preferred_ports": {}
        }
        with open(config_path, 'w') as config_file:
            json.dump(default_config, config_file, indent=4)
        print(f"Default configuration created at {config_path}")
    else:
        print(f"Configuration file already exists at {config_path}")

def get_preferred_port(container_name):
    with open("config/config.json") as config_file:
        config = json.load(config_file)
        return config["preferred_ports"].get(container_name, "default_port")
    
def set_preferred_port(container_name, port):
    with open("config/config.json") as config_file:
        config = json.load(config_file)
        config["preferred_ports"][container_name] = port
    with open("config/config.json", 'w') as config_file:
        json.dump(config, config_file, indent=4)
    print(f"Preferred port for {container_name} set to {port}")    

