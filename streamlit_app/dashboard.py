import streamlit as st
import requests
from pydantic import BaseModel

# Point to the central dashboard
CENTRAL_DASHBOARD_URL = "http://central_dashboard:8000"

# Initialize session state
if "reservation_pending" not in st.session_state:
    st.session_state.reservation_pending = False
    st.session_state.pending_reservation = None

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

# GPU Request Form - Single form for all nodes
st.header("Request GPU Resources")
with st.form(key="gpu_request_form"):
    user = st.text_input("Your name", value="")
    mem_required = st.number_input("Memory required (GB)", min_value=0.1, step=0.1)
    session_type = st.selectbox("Session type", ["interactive", "job"])
    submit = st.form_submit_button("Find Best Available GPU")

    if submit and user.strip():
        try:
            st.write("Finding best available GPU...")
            r = requests.post(
                f"{CENTRAL_DASHBOARD_URL}/api/find_best_gpu",
                json={
                    "user_name": user,
                    "mem_required": mem_required,
                    "session_type": session_type,
                },
                timeout=5,
            )
            if r.status_code == 200:
                response = r.json()
                if response["status"] == "ok":
                    st.session_state.reservation_pending = True
                    st.session_state.pending_reservation = {
                        "node_id": response["node_id"],
                        "gpu_id": response["gpu_id"],
                        "available_mem": response["available_mem"],
                        "user_name": user,
                        "mem_required": mem_required,
                        "session_type": session_type,
                    }
                    st.rerun()
                else:
                    st.error(response["message"])
            else:
                st.error("Failed to find available GPU.")
        except Exception as e:
            st.error(f"Error requesting GPU resources: {e}")

# Show confirmation outside the form
if st.session_state.reservation_pending:
    res = st.session_state.pending_reservation
    st.success(
        f"Found GPU on Node {res['node_id']} GPU {res['gpu_id']}! "
        f"Available memory: {res['available_mem']:.1f} GB"
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Confirm Reservation"):
            confirm = requests.post(
                f"{CENTRAL_DASHBOARD_URL}/api/request_gpu",
                json={
                    "node_id": res["node_id"],
                    "user_name": res["user_name"],
                    "mem_required": res["mem_required"],
                    "session_type": res["session_type"],
                },
                timeout=5,
            )
            if confirm.status_code == 200:
                st.session_state.reservation_pending = False
                st.session_state.pending_reservation = None
                st.success("GPU Reserved successfully!")
                st.rerun()

    with col2:
        if st.button("Cancel"):
            st.session_state.reservation_pending = False
            st.session_state.pending_reservation = None
            st.rerun()

# Display Cluster Status
st.header("Cluster Status")
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
