import os
import time
import random
import requests

NODE_ID = os.environ.get("NODE_ID", "node_unknown")
DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "http://central_dashboard:8000")

# We'll just run a loop and POST every 5 seconds
while True:
    cpu_usage = random.uniform(0, 100)  # Fake CPU usage %
    mem_usage = random.uniform(0, 64)  # Fake memory usage in GB (or whatever scale)
    timestamp = time.time()
    data = {
        "node_id": NODE_ID,
        "cpu_usage": cpu_usage,
        "mem_usage": mem_usage,
        "timestamp": timestamp,
    }
    try:
        requests.post(f"{DASHBOARD_URL}/api/update_node_status", json=data, timeout=5)
    except Exception as e:
        print(f"Failed to send update: {e}")
    time.sleep(5)
