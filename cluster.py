import copy
import time
from typing import Dict, Any, List, Optional
import sqlite3
from datetime import datetime, timedelta

# We import the DB operations from db.py
from db import (
    get_reservations_from_db,
    add_reservation_to_db,
    clear_reservations_in_db,
    cancel_reservation,
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
DEFAULT_MEMORY_REQUIREMENT = 2.0  # Default memory requirement if not specified


def get_gpu_status() -> List[Dict[str, Any]]:
    """
    Returns the status of all GPUs in the cluster.
    """
    data = list_nodes()
    result = []

    for node_id, node in data.items():
        for gpu_id, gpu in node.gpus.items():
            result.append(
                {
                    "node_id": node_id,
                    "gpu_id": gpu_id,
                    "max_memory": gpu.max_mem,
                    "used_memory": gpu.total_usage(),
                    "available_memory": gpu.available_memory(
                        MEMORY_BUFFER_PER_RESERVATION
                    ),
                    "num_processes": len(gpu.processes),
                    "num_reservations": len(gpu.reservations),
                }
            )

    return result


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


def find_best_gpu() -> Optional[str]:
    """
    Find the best available GPU across all nodes.
    Returns the GPU ID if found, None if not available.

    This simplified version matches the app.py signature.
    """
    data = list_nodes()
    best_node = None
    best_gpu_id = None
    most_available = -1

    for node_id, node in data.items():
        for gpu_id, gpu in node.gpus.items():
            mem_available = gpu.available_memory(MEMORY_BUFFER_PER_RESERVATION)
            if (
                mem_available >= DEFAULT_MEMORY_REQUIREMENT
                and mem_available > most_available
            ):
                best_node = node_id
                best_gpu_id = gpu_id
                most_available = mem_available

    # For now, return just the GPU ID as that's what app.py expects
    return best_gpu_id


def reserve_gpu(
    conn: sqlite3.Connection, gpu_id: str, user_name: str, duration_hours: int = 1
) -> int:
    """
    Create a new reservation for the given GPU and user.
    Returns the reservation ID if successful.

    This matches how it's called from app.py
    """
    # Map GPU ID to node_id and gpu_id from our in-memory data
    data = list_nodes()
    node_id = None
    found_gpu_id = None

    # Find which node contains this GPU
    for n_id, node in data.items():
        if gpu_id in node.gpus:
            node_id = n_id
            found_gpu_id = gpu_id
            break

    if node_id is None:
        raise ValueError(f"GPU with ID {gpu_id} not found in any node")

    gpu = data[node_id].gpus[found_gpu_id]

    # Check if enough memory is available
    if gpu.available_memory(MEMORY_BUFFER_PER_RESERVATION) < DEFAULT_MEMORY_REQUIREMENT:
        raise ValueError(f"Insufficient memory available on GPU {gpu_id}")

    # Add the reservation to the database
    try:
        reservation_id = add_reservation_to_db(
            node_id, found_gpu_id, user_name, DEFAULT_MEMORY_REQUIREMENT, duration_hours
        )
        return reservation_id
    except Exception as e:
        # Log the error
        print(f"Error during reservation: {str(e)}")
        raise


def cancel_reservation_wrapper(conn: sqlite3.Connection, reservation_id: int) -> bool:
    """
    Cancel a reservation by ID.
    Returns True if successful, False if not found.

    This bridges the app.py call to db.py functionality.
    """
    return cancel_reservation(conn, reservation_id)


def reset_reservations(conn: sqlite3.Connection) -> None:
    """
    1) Clears all processes in memory from node_data_static
    2) Clears all reservations in the DB

    This matches the signature needed by app.py
    """
    # Clear all processes in memory
    for _, node in node_data_static.items():
        for _, gpu in node.gpus.items():
            gpu.processes.clear()
            gpu.reservations.clear()

    # Clear all reservations in DB
    clear_reservations_in_db()
