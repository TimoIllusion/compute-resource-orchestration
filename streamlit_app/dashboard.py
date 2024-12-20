import streamlit as st
import requests
from pydantic import BaseModel

# Point to the central dashboard
CENTRAL_DASHBOARD_URL = "http://central_dashboard:8000"

st.title("Cluster CPU/Memory/GPU Dashboard")

# Fetch node data
try:
    st.write("Fetching node data...")
    response = requests.get(f"{CENTRAL_DASHBOARD_URL}/api/list_nodes", timeout=5)
    data = response.json()
    st.write("Node data fetched successfully.")
except Exception as e:
    st.error(f"Failed to fetch node data: {e}")
    st.stop()

for node_id, info in data.items():
    st.subheader(f"Node: {node_id}")
    st.write(f"CPU Usage: {info['cpu_usage']:.2f}%")
    st.write(f"Memory Usage: {info['mem_usage']:.2f} GB")
    current_res = info["reservation"] if info["reservation"] else "None"
    st.write(f"Reserved By: {current_res}")

    # Display GPU information
    for gpu_id, gpu_info in info.get("gpus", {}).items():
        st.write(f"GPU {gpu_id}:")
        st.write(
            f"  Memory Usage: {gpu_info['mem_usage']:.2f} GB / {gpu_info['max_mem']:.2f} GB"
        )
        st.write("  Processes:")
        for process in gpu_info["processes"]:
            st.write(
                f"    - PID: {process['pid']}, User: {process['user']}, Memory: {process['mem_usage']:.2f} GB"
            )

    # Reservation form
    with st.form(key=f"reserve_form_{node_id}"):
        user = st.text_input("Your name", value="", key=f"user_{node_id}")
        mem_required = st.number_input(
            "Memory required (GB)", min_value=0.1, step=0.1, key=f"mem_{node_id}"
        )
        session_type = st.selectbox(
            "Session type", ["interactive", "job"], key=f"session_{node_id}"
        )
        submit = st.form_submit_button("Request GPU resources")
        if submit and user.strip():
            try:
                st.write("Submitting GPU request...")
                r = requests.post(
                    f"{CENTRAL_DASHBOARD_URL}/api/request_gpu",
                    json={
                        "node_id": node_id,
                        "user_name": user,
                        "mem_required": mem_required,
                        "session_type": session_type,
                    },
                    timeout=5,
                )
                st.write(f"Request status code: {r.status_code}")
                if r.status_code == 200:
                    response = r.json()
                    if response["status"] == "ok":
                        st.success(
                            f"GPU reserved successfully on Node {response['node_id']} GPU {response['gpu_id']}!"
                        )
                        st.rerun()  # Refresh the page to see the updated status
                    else:
                        st.error(response["message"])
                else:
                    st.error("Failed to request GPU resources.")
            except Exception as e:
                st.error(f"Error requesting GPU resources: {e}")
