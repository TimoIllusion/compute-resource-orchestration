import streamlit as st
import time
import sqlite3


# -------------------------------------------------------------------
# Database Setup / Functions
# -------------------------------------------------------------------
@st.cache_resource
def get_connection():
    """Create or get a connection to a local SQLite database."""
    conn = sqlite3.connect("reservations.db", check_same_thread=False)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS reservations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            node_id TEXT NOT NULL,
            gpu_id TEXT NOT NULL,
            user_name TEXT NOT NULL,
            mem_reserved REAL NOT NULL,
            timestamp REAL NOT NULL
        )
        """
    )
    return conn


def add_reservation_to_db(node_id, gpu_id, user_name, mem_required):
    """Insert a new reservation into the database."""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO reservations (node_id, gpu_id, user_name, mem_reserved, timestamp)
        VALUES (?, ?, ?, ?, ?)
        """,
        (node_id, gpu_id, user_name, mem_required, time.time()),
    )
    conn.commit()


def get_reservations_from_db():
    """Retrieve all reservations from the database."""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        SELECT node_id, gpu_id, user_name, mem_reserved, timestamp
        FROM reservations
        """
    )
    rows = c.fetchall()
    return rows


def clear_reservations_in_db():
    """Remove all reservations from the database."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM reservations")
    conn.commit()


# -------------------------------------------------------------------
# Classes
# -------------------------------------------------------------------
class Process:
    def __init__(self, pid, user, mem_usage):
        self.pid = pid
        self.user = user
        self.mem_usage = mem_usage


class Reservation:
    def __init__(self, user, mem_reserved, session_active=True):
        self.user = user
        self.mem_reserved = mem_reserved
        self.timestamp = time.time()
        self.session_active = session_active


class GPU:
    def __init__(self, max_mem, mem_usage, processes=None, reservations=None):
        self.max_mem = max_mem
        # mem_usage can be used as an initial usage "baseline," if needed
        self.mem_usage = mem_usage
        self.processes = processes or []
        self.reservations = reservations or []

    def total_usage(self):
        # GPU usage = sum of memory used by processes + sum of memory in reservations
        return sum(p.mem_usage for p in self.processes) + sum(
            r.mem_reserved for r in self.reservations
        )

    def available_memory(self, buffer_per_reservation):
        # Available memory = max_mem - total_usage - (buffer * number_of_reservations)
        return (
            self.max_mem
            - self.total_usage()
            - (buffer_per_reservation * len(self.reservations))
        )


class Node:
    def __init__(self, cpu_usage, mem_usage, gpus=None):
        self.cpu_usage = cpu_usage
        self.mem_usage = mem_usage
        self.timestamp = time.time()
        self.gpus = gpus or {}


# -------------------------------------------------------------------
# Global constants and sample cluster data
# -------------------------------------------------------------------
MEMORY_BUFFER_PER_RESERVATION = 1.0

# We keep 'node_data' static for demonstration. Processes are in-memory only.
# However, we do NOT store Reservations here, because we load them from DB each time.
node_data_static = {
    "node1": Node(
        cpu_usage=30.0,
        mem_usage=32.0,
        gpus={
            "0": GPU(
                max_mem=16.0,
                mem_usage=2.0,
                processes=[Process(1000, "user1", 2.0)],
                reservations=[],  # We'll load from DB later
            ),
            "1": GPU(
                max_mem=16.0,
                mem_usage=4.0,
                processes=[Process(1001, "user2", 4.0)],
                reservations=[],
            ),
        },
    ),
    "node2": Node(
        cpu_usage=25.0,
        mem_usage=16.0,
        gpus={
            "0": GPU(
                max_mem=8.0,
                mem_usage=1.0,
                processes=[Process(2000, "user3", 1.0)],
                reservations=[],
            )
        },
    ),
}


# -------------------------------------------------------------------
# Helper / Business Logic
# -------------------------------------------------------------------
def list_nodes():
    """
    Return a fresh copy of all nodes and attach reservations from DB
    so they are reflected in the GPU objects.
    """
    # Copy our static structure so we don't mutate node_data_static
    # (since it's our "template").
    import copy

    data = copy.deepcopy(node_data_static)

    # Fetch all reservations from the DB
    db_reservations = get_reservations_from_db()

    # Attach reservations from DB to the appropriate GPU in data
    for node_id, gpu_id, user_name, mem_reserved, ts in db_reservations:
        if node_id in data and gpu_id in data[node_id].gpus:
            data[node_id].gpus[gpu_id].reservations.append(
                Reservation(
                    user=user_name, mem_reserved=mem_reserved, session_active=True
                )
            )

    return data


def find_best_gpu(user_name, mem_required, session_type):
    """
    Search for a GPU across all nodes that can accommodate the requested mem_required.
    Return the node and gpu_id with the largest mem_available if found.
    """
    best_node = None
    best_gpu_id = None
    most_available = -1

    # We'll use the updated 'list_nodes()' so that
    # it accounts for current reservations from the DB.
    data = list_nodes()

    for node_id, node in data.items():
        for gpu_id, gpu in node.gpus.items():
            mem_available = gpu.available_memory(MEMORY_BUFFER_PER_RESERVATION)
            if mem_available >= mem_required and mem_available > most_available:
                best_node = node_id
                best_gpu_id = gpu_id
                most_available = mem_available

    if best_node is None:
        return {"status": "error", "message": "No GPU with sufficient memory available"}
    else:
        return {
            "status": "ok",
            "node_id": best_node,
            "gpu_id": best_gpu_id,
            "available_mem": most_available,
        }


def reserve_gpu(node_id, gpu_id, user_name, mem_required):
    """
    Reserve GPU memory by adding a reservation row to the DB.
    """
    # Reload the cluster info from DB to ensure we check the updated usage
    data = list_nodes()

    if node_id not in data:
        return {"status": "error", "message": "Node not found"}

    if gpu_id not in data[node_id].gpus:
        return {"status": "error", "message": "GPU not found"}

    gpu = data[node_id].gpus[gpu_id]

    # Check if GPU has enough memory left
    if gpu.available_memory(MEMORY_BUFFER_PER_RESERVATION) < mem_required:
        return {"status": "error", "message": "Insufficient GPU memory for reservation"}

    # Add this reservation to the DB
    add_reservation_to_db(node_id, gpu_id, user_name, mem_required)

    return {
        "status": "reserved",
        "node_id": node_id,
        "gpu_id": gpu_id,
        "user": user_name,
        "mem_reserved": mem_required,
    }


def reset_cluster():
    """
    1) Clear all processes in memory from node_data_static
    2) Clear all reservations from the SQLite DB
    """
    # 1) Clear processes from the in-memory data
    for node_id, node in node_data_static.items():
        for gpu_id, gpu in node.gpus.items():
            gpu.processes.clear()
            # We'll also clear the GPU's reservations array,
            #   but the real source of truth is the DB
            gpu.reservations.clear()

    # 2) Remove all reservation entries from the DB
    clear_reservations_in_db()


# -------------------------------------------------------------------
# Streamlit App
# -------------------------------------------------------------------
# Initialize session state variables
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

    # If a reservation is "pending," allow the user to confirm or cancel
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

    data = list_nodes()  # This fetches reservations from DB and merges them in
    for node_id, info in data.items():
        with st.expander(f"Node: {node_id}", expanded=True):
            cpu_col, mem_col = st.columns(2)
            with cpu_col:
                st.write(f"**CPU Usage:** {info.cpu_usage:.2f}%")
            with mem_col:
                st.write(f"**Memory Usage:** {info.mem_usage:.2f} GB")

            for gpu_id, gpu_info in info.gpus.items():
                st.markdown(f"---\n**GPU {gpu_id}:**")
                col_gpu_mem, col_reservations = st.columns([1, 1])
                with col_gpu_mem:
                    total_usage = gpu_info.total_usage()
                    st.write(
                        f"Memory Usage: {total_usage:.2f} GB / {gpu_info.max_mem:.2f} GB"
                    )
                    st.write(
                        f"Available Memory: "
                        f"{(gpu_info.max_mem - total_usage):.2f} GB"
                    )
                with col_reservations:
                    st.write("**Reservations:**")
                    if gpu_info.reservations:
                        for reservation in gpu_info.reservations:
                            st.write(
                                f"- {reservation.user}: "
                                f"{reservation.mem_reserved:.1f} GB"
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
