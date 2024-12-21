import streamlit as st
import requests
from pydantic import BaseModel

CENTRAL_CONTROLLER_URL = "http://central_controller:8000"

if "reservation_pending" not in st.session_state:
    st.session_state.reservation_pending = False
    st.session_state.pending_reservation = None

st.title("Cluster CPU/Memory/GPU Dashboard")

try:
    response = requests.get(f"{CENTRAL_CONTROLLER_URL}/api/list_nodes", timeout=5)
    data = response.json()
except Exception as e:
    st.error(f"Failed to fetch node data: {e}")
    st.stop()

tabs = st.tabs(["GPU Requests", "Cluster Status"])

with tabs[0]:
    st.header("Request GPU Resources")
    with st.form(key="gpu_request_form"):
        col1, col2, col3 = st.columns(3)
        with col1:
            user = st.text_input("Your name", value="")
        with col2:
            mem_required = st.number_input(
                "Memory required (GB)", min_value=1, step=1, value=5
            )
        with col3:
            session_type = st.selectbox("Session type", ["interactive", "job"])

        submit = st.form_submit_button("Find Best Available GPU")

        if submit and user.strip():
            try:
                r = requests.post(
                    f"{CENTRAL_CONTROLLER_URL}/api/find_best_gpu",
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
                    f"{CENTRAL_CONTROLLER_URL}/api/reserve_gpu",
                    json={
                        "node_id": res["node_id"],
                        "gpu_id": res["gpu_id"],
                        "user_name": res["user_name"],
                        "mem_required": res["mem_required"],
                    },
                    timeout=5,
                )
                if confirm.status_code == 200:
                    st.session_state.reservation_pending = False
                    st.session_state.pending_reservation = None
                    st.success("GPU Reserved successfully!")
                    st.rerun()
                else:
                    st.error(f"Failed to reserve GPU: {confirm.text}")

        with col2:
            if st.button("Cancel"):
                st.session_state.reservation_pending = False
                st.session_state.pending_reservation = None
                st.rerun()

with tabs[1]:
    st.header("Cluster Status")
    for node_id, info in data.items():
        with st.expander(f"Node: {node_id}", expanded=True):
            cpu_col, mem_col = st.columns(2)
            with cpu_col:
                st.write(f"**CPU Usage:** {info['cpu_usage']:.2f}%")
            with mem_col:
                st.write(f"**Memory Usage:** {info['mem_usage']:.2f} GB")

            gpu_container = st.container()
            for gpu_id, gpu_info in info.get("gpus", {}).items():
                with gpu_container:
                    st.write(f"**GPU {gpu_id}:**")
                    col_gpu_mem, col_reservations = st.columns([1, 1])
                    with col_gpu_mem:
                        st.write(
                            f"Memory Usage: {gpu_info['mem_usage']:.2f} GB / {gpu_info['max_mem']:.2f} GB"
                        )
                    with col_reservations:
                        st.write("**Reservations:**")
                        for reservation in gpu_info.get("reservations", []):
                            st.write(
                                f"- {reservation['user']}: {reservation['mem_reserved']:.1f} GB"
                            )

                    st.write("Processes:")
                    for process in gpu_info["processes"]:
                        st.write(
                            f"- PID: {process['pid']}, User: {process['user']}, "
                            f"Memory: {process['mem_usage']:.2f} GB"
                        )
