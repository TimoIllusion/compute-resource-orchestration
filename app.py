# main.py
import streamlit as st
from cluster import (
    list_nodes,
    find_best_gpu,
    reserve_gpu,
    reset_cluster,
)

# We only need the cluster methods for logic; DB is handled behind the scenes in cluster.py

# ---------------------------------------
# Streamlit App
# ---------------------------------------

# Maintain some UI states
if "reservation_pending" not in st.session_state:
    st.session_state.reservation_pending = False
    st.session_state.pending_reservation = None

st.title("Monolithic CPU/Memory/GPU Orchestration App")

tabs = st.tabs(["GPU Requests", "Cluster Status"])

# ---------------- GPU Requests Tab ----------------
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
                # Store response in session state so we can confirm/cancel
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

    # If a reservation is "pending," show confirmation
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


# ---------------- Cluster Status Tab ----------------
with tabs[1]:
    st.header("Cluster Status")

    # RESET button
    if st.button("Reset All Reservations and Processes"):
        reset_cluster()
        st.success("All reservations and processes cleared!")
        st.experimental_rerun()

    data = list_nodes()
    for node_id, node_info in data.items():
        with st.expander(f"Node: {node_id}", expanded=True):
            cpu_col, mem_col = st.columns(2)
            with cpu_col:
                st.write(f"**CPU Usage:** {node_info.cpu_usage:.2f}%")
            with mem_col:
                st.write(f"**Memory Usage:** {node_info.mem_usage:.2f} GB")

            for gpu_id, gpu_info in node_info.gpus.items():
                st.write(f"---\n**GPU {gpu_id}:**")
                col_gpu_mem, col_reservations = st.columns([1, 1])
                with col_gpu_mem:
                    total_usage = gpu_info.total_usage()
                    st.write(
                        f"Memory Usage: {total_usage:.2f} GB / {gpu_info.max_mem:.2f} GB"
                    )
                    st.write(
                        f"Available Memory: {(gpu_info.max_mem - total_usage):.2f} GB"
                    )
                with col_reservations:
                    st.write("**Reservations:**")
                    if gpu_info.reservations:
                        for reservation in gpu_info.reservations:
                            st.write(
                                f"- {reservation.user}: {reservation.mem_reserved:.1f} GB"
                            )
                    else:
                        st.write("No reservations.")

                st.write("**Processes:**")
                if gpu_info.processes:
                    for process in gpu_info.processes:
                        st.write(
                            f"- PID: {process.pid}, "
                            f"User: {process.user}, "
                            f"Memory: {process.mem_usage:.2f} GB"
                        )
                else:
                    st.write("No active processes.")
