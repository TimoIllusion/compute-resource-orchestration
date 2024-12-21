import os
import time
import random
import requests

NODE_ID = os.environ.get("NODE_ID", "node_unknown")
DASHBOARD_URL = os.environ.get("CONTROLLER_URL", "http://central_controller:8000")


# Fixed GPU configuration
def initialize_gpu_info():
    gpus = {}
    num_gpus = 2  # Fixed number of GPUs
    for gpu_id in range(num_gpus):
        max_mem = 16.0  # Fixed max memory in GB
        mem_usage = 2.0  # Initial memory usage in GB
        processes = [
            {
                "pid": 1000 + gpu_id,
                "user": f"user{gpu_id + 1}",
                "mem_usage": 2.0,
            }
        ]
        gpus[str(gpu_id)] = {
            "max_mem": max_mem,
            "mem_usage": mem_usage,
            "processes": processes,
            "reservation": None,
        }
    return gpus


# Initialize GPU configuration once
gpus = initialize_gpu_info()

# We'll just run a loop and POST every 5 seconds
while True:
    cpu_usage = 30.0  # Fixed CPU usage %
    mem_usage = 32.0  # Fixed memory usage in GB
    timestamp = time.time()

    data = {
        "node_id": NODE_ID,
        "cpu_usage": cpu_usage,
        "mem_usage": mem_usage,
        "timestamp": timestamp,
        "gpus": gpus,
    }
    try:
        requests.post(f"{DASHBOARD_URL}/api/update_node_status", json=data, timeout=5)
    except Exception as e:
        print(f"Failed to send update: {e}")
    time.sleep(5)
