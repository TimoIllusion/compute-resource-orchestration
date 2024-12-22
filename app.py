import streamlit as st
import time

# In-memory simulation of multiple nodes
node_data = {
    "node1": {
        "cpu_usage": 30.0,
        "mem_usage": 32.0,
        "timestamp": time.time(),
        "gpus": {
            "0": {
                "max_mem": 16.0,
                "mem_usage": 2.0,
                "processes": [{"pid": 1000, "user": "user1", "mem_usage": 2.0}],
                "reservations": [],
            },
            "1": {
                "max_mem": 16.0,
                "mem_usage": 4.0,
                "processes": [{"pid": 1001, "user": "user2", "mem_usage": 4.0}],
                "reservations": [],
            },
        },
    },
    "node2": {
        "cpu_usage": 25.0,
        "mem_usage": 16.0,
        "timestamp": time.time(),
        "gpus": {
            "0": {
                "max_mem": 8.0,
                "mem_usage": 1.0,
                "processes": [{"pid": 2000, "user": "user3", "mem_usage": 1.0}],
                "reservations": [],
            }
        },
    },
}

MEMORY_BUFFER_PER_RESERVATION = 1.0

# ------------------------------------------------------------------------------
# Controller-like logic (local functions instead of REST endpoints)
# ------------------------------------------------------------------------------


def list_nodes():
    return node_data


def find_best_gpu(user_name, mem_required, session_type):
    best_gpu = None
    best_node = None
    most_available_mem = -1

    for node_id, info in node_data.items():
        for gpu_id, gpu_info in info["gpus"].items():
            # Skip any GPU that already has at least one reservation
            if len(gpu_info["reservations"]) > 0:
                continue

            total_reserved = sum(
                r["mem_reserved"] + MEMORY_BUFFER_PER_RESERVATION
                for r in gpu_info["reservations"]
            )
            available_mem = gpu_info["max_mem"] - total_reserved

            if (
                available_mem >= (mem_required + MEMORY_BUFFER_PER_RESERVATION)
                and available_mem > most_available_mem
            ):
                most_available_mem = available_mem
                best_gpu = gpu_id
                best_node = node_id

    if best_node is None:
        return {"status": "error", "message": "No GPU with sufficient memory available"}

    return {
        "status": "ok",
        "node_id": best_node,
        "gpu_id": best_gpu,
        "available_mem": most_available_mem,
    }


def reserve_gpu(node_id, gpu_id, user_name, mem_required):
    if node_id not in node_data:
        return {"status": "error", "message": "Node not found"}
    if gpu_id not in node_data[node_id]["gpus"]:
        return {"status": "error", "message": "GPU not found"}

    gpu_info = node_data[node_id]["gpus"][gpu_id]
    total_reserved = sum(
        r["mem_reserved"] + MEMORY_BUFFER_PER_RESERVATION
        for r in gpu_info["reservations"]
    )
    if (
        total_reserved + mem_required + MEMORY_BUFFER_PER_RESERVATION
        > gpu_info["max_mem"]
    ):
        return {"status": "error", "message": "Insufficient GPU memory for reservation"}

    gpu_info["reservations"].append({"user": user_name, "mem_reserved": mem_required})
    return {
        "status": "reserved",
        "node_id": node_id,
        "gpu_id": gpu_id,
        "user": user_name,
        "mem_reserved": mem_required,
    }


# ------------------------------------------------------------------------------
# Streamlit UI
# ------------------------------------------------------------------------------
if "reservation_pending" not in st.session_state:
    st.session_state.reservation_pending = False
    st.session_state.pending_reservation = None

st.title("Monolithic CPU/Memory/GPU Orchestration App")

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
            response = find_best_gpu(user, mem_required, session_type)
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
                st.experimental_rerun()
            else:
                st.error(response["message"])

    if st.session_state.reservation_pending:
        res = st.session_state.pending_reservation
        st.success(
            f"Found GPU on Node {res['node_id']} GPU {res['gpu_id']}! "
            f"Available memory: {res['available_mem']:.1f} GB"
        )
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Confirm Reservation"):
                confirm = reserve_gpu(
                    res["node_id"],
                    res["gpu_id"],
                    res["user_name"],
                    res["mem_required"],
                )
                if confirm["status"] == "reserved":
                    st.session_state.reservation_pending = False
                    st.session_state.pending_reservation = None
                    st.success("GPU Reserved successfully!")
                    st.experimental_rerun()
                else:
                    st.error(confirm["message"])

        with col2:
            if st.button("Cancel"):
                st.session_state.reservation_pending = False
                st.session_state.pending_reservation = None
                st.experimental_rerun()

with tabs[1]:
    st.header("Cluster Status")
    data = list_nodes()
    for node_id, info in data.items():
        with st.expander(f"Node: {node_id}", expanded=True):
            cpu_col, mem_col = st.columns(2)
            with cpu_col:
                st.write(f"**CPU Usage:** {info['cpu_usage']:.2f}%")
            with mem_col:
                st.write(f"**Memory Usage:** {info['mem_usage']:.2f} GB")

            for gpu_id, gpu_info in info["gpus"].items():
                st.write(f"---\n**GPU {gpu_id}:**")
                col_gpu_mem, col_reservations = st.columns([1, 1])
                with col_gpu_mem:
                    st.write(
                        f"Memory Usage: {gpu_info['mem_usage']:.2f} GB "
                        f"/ {gpu_info['max_mem']:.2f} GB"
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
                        f"- PID: {process['pid']}, "
                        f"User: {process['user']}, "
                        f"Memory: {process['mem_usage']:.2f} GB"
                    )
