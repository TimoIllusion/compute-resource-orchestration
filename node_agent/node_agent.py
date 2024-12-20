import os
import time
import random
import requests

NODE_ID = os.environ.get("NODE_ID", "node_unknown")
DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "http://central_dashboard:8000")


def generate_gpu_info():
    gpus = {}
    num_gpus = random.randint(1, 3)
    for gpu_id in range(num_gpus):
        max_mem = random.uniform(8, 16)  # Max memory in GB
        mem_usage = random.uniform(0, max_mem)  # Current memory usage in GB
        processes = [
            {
                "pid": random.randint(1000, 5000),
                "user": f"user{random.randint(1, 5)}",
                "mem_usage": random.uniform(0.1, 2),
            }
            for _ in range(random.randint(0, 5))
        ]
        gpus[str(gpu_id)] = {  # Change to string key
            "max_mem": max_mem,
            "mem_usage": mem_usage,
            "processes": processes,
        }
    return gpus


# We'll just run a loop and POST every 5 seconds
while True:
    cpu_usage = random.uniform(0, 100)  # Fake CPU usage %
    mem_usage = random.uniform(0, 64)  # Fake memory usage in GB (or whatever scale)
    timestamp = time.time()
    gpus = generate_gpu_info()
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
