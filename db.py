# db.py
import sqlite3
import time
from typing import List, Tuple


def get_connection() -> sqlite3.Connection:
    """
    Creates or returns a connection to a local SQLite database named 'reservations.db'.
    """
    conn = sqlite3.connect("reservations.db", check_same_thread=False)
    create_table_if_not_exists(conn)
    return conn


def create_table_if_not_exists(conn: sqlite3.Connection):
    """
    Initialize the 'reservations' table if it doesn't exist.
    """
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS reservations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            node_id TEXT NOT NULL,
            gpu_id TEXT NOT NULL,
            user_name TEXT NOT NULL,
            mem_reserved REAL NOT NULL,
            timestamp REAL NOT NULL
        );
        """
    )
    conn.commit()


def add_reservation_to_db(
    node_id: str, gpu_id: str, user_name: str, mem_required: float
) -> None:
    """
    Inserts a new reservation record into the database.
    """
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
    conn.close()


def get_reservations_from_db() -> List[Tuple[str, str, str, float, float]]:
    """
    Returns all reservations in the form of (node_id, gpu_id, user_name, mem_reserved, timestamp).
    """
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        SELECT node_id, gpu_id, user_name, mem_reserved, timestamp
        FROM reservations
        """
    )
    rows = c.fetchall()
    conn.close()
    return rows


def clear_reservations_in_db() -> None:
    """
    Removes all reservation rows from the database.
    """
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM reservations")
    conn.commit()
    conn.close()
