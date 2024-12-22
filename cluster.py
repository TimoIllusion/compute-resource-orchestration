# cluster.py
import copy
import time
from typing import Dict, Any

# We import the DB operations from db.py
from db import (
    get_reservations_from_db,
    add_reservation_to_db,
    clear_reservations_in_db,
)


# -------------------------------------------------------------------
# Classes
# -------------------------------------------------------------------
class Process:
    def __init__(self, pid: int, user: str, mem_usage: float):
        self.pid = pid
        self.user = user
        self.mem_usage = mem_usage


class Reservation:
    def __init__(self, user: str, mem_reserved: float, session_active: bool = True):
        self.user = user
        self.mem_reserved = mem_reserved
        self.timestamp = time.time()
        self.session_active = session_active


class GPU:
    def __init__(
        self, max_mem: float, mem_usage: float = 0.0, processes=None, reservations=None
    ):
        self.max_mem = max_mem
        self.mem_usage = mem_usage
        self.processes = processes or []
        self.reservations = reservations or []

    def total_usage(self) -> float:
        """
        Sum memory used by processes + sum memory in reservations.
        """
        return sum(proc.mem_usage for proc in self.processes) + sum(
            r.mem_reserved for r in self.reservations
        )

    def available_memory(self, buffer_per_reservation: float) -> float:
        """
        Available memory = max_mem - total_usage - buffer * number_of_reservations
        """
        return (
            self.max_mem
            - self.total_usage()
            - (buffer_per_reservation * len(self.reservations))
        )


class Node:
    def __init__(self, cpu_usage: float, mem_usage: float, gpus=None):
        self.cpu_usage = cpu_usage
        self.mem_usage = mem_usage
        self.timestamp = time.time()
        self.gpus = gpus or {}


# -------------------------------------------------------------------
# In-memory data (for processes). Reservations are loaded from DB.
# -------------------------------------------------------------------
node_data_static = {
    "node1": Node(
        cpu_usage=30.0,
        mem_usage=32.0,
        gpus={
            "0": GPU(
                max_mem=16.0,
                mem_usage=2.0,
                processes=[Process(1000, "user1", 2.0)],
                reservations=[],
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


MEMORY_BUFFER_PER_RESERVATION = 1.0


def list_nodes() -> Dict[str, Node]:
    """
    Returns a copy of the cluster data and attaches DB reservations to each GPU.
    """
    data = copy.deepcopy(node_data_static)
    db_reservations = get_reservations_from_db()
    # db_reservations => [(node_id, gpu_id, user_name, mem_reserved, timestamp), ...]

    # Attach the reservations from DB to each GPU in the data copy
    for node_id, gpu_id, user_name, mem_reserved, ts in db_reservations:
        if node_id in data and gpu_id in data[node_id].gpus:
            data[node_id].gpus[gpu_id].reservations.append(
                Reservation(user=user_name, mem_reserved=mem_reserved)
            )

    return data


def find_best_gpu(
    user_name: str, mem_required: float, session_type: str
) -> Dict[str, Any]:
    """
    Search for a GPU across all nodes that can accommodate 'mem_required'.
    Return a dict with status and node/gpu info if found.
    """
    data = list_nodes()
    best_node = None
    best_gpu_id = None
    most_available = -1

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


def reserve_gpu(
    node_id: str, gpu_id: str, user_name: str, mem_required: float
) -> Dict[str, Any]:
    """
    Check GPU availability and then create a new reservation in the DB.
    """
    data = list_nodes()

    if node_id not in data:
        return {"status": "error", "message": "Node not found"}
    if gpu_id not in data[node_id].gpus:
        return {"status": "error", "message": "GPU not found"}

    gpu = data[node_id].gpus[gpu_id]
    if gpu.available_memory(MEMORY_BUFFER_PER_RESERVATION) < mem_required:
        return {"status": "error", "message": "Insufficient GPU memory for reservation"}

    # If sufficient memory available, add to DB
    add_reservation_to_db(node_id, gpu_id, user_name, mem_required)

    return {
        "status": "reserved",
        "node_id": node_id,
        "gpu_id": gpu_id,
        "user": user_name,
        "mem_reserved": mem_required,
    }


def reset_cluster() -> None:
    """
    1) Clears all processes in memory from node_data_static
    2) Clears all reservations in the DB
    """
    # Clear all processes in memory
    for _, node in node_data_static.items():
        for _, gpu in node.gpus.items():
            gpu.processes.clear()
            gpu.reservations.clear()

    # Clear all reservations in DB
    clear_reservations_in_db()
