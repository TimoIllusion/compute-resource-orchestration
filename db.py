# db.py
import sqlite3
import time
from typing import List, Tuple, Optional
import datetime


def create_connection() -> sqlite3.Connection:
    """
    Creates or returns a connection to a local SQLite database named 'reservations.db'.
    This is the function called by app.py.
    """
    return get_connection()


def get_connection() -> sqlite3.Connection:
    """
    Creates or returns a connection to a local SQLite database named 'reservations.db'.
    """
    conn = sqlite3.connect("reservations.db", check_same_thread=False)
    create_table_if_not_exists(conn)
    return conn


def create_tables(conn: sqlite3.Connection):
    """
    Initialize all database tables if they don't exist.
    """
    create_table_if_not_exists(conn)


def create_table_if_not_exists(conn: sqlite3.Connection):
    """
    Initialize the 'reservations' table if it doesn't exist.
    Also adds any missing columns to support upgrades from older schema versions.
    """
    # Create the table if it doesn't exist with the base schema
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

    # Check if start_time and end_time columns exist, add them if they don't
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(reservations);")
    columns = [column[1] for column in cursor.fetchall()]

    if "start_time" not in columns:
        conn.execute("ALTER TABLE reservations ADD COLUMN start_time TEXT;")

    if "end_time" not in columns:
        conn.execute("ALTER TABLE reservations ADD COLUMN end_time TEXT;")

    conn.commit()


def add_reservation_to_db(
    node_id: str,
    gpu_id: str,
    user_name: str,
    mem_required: float,
    duration_hours: int = 1,
) -> int:
    """
    Inserts a new reservation record into the database.
    Returns the ID of the newly created reservation.
    """
    conn = get_connection()
    c = conn.cursor()

    # Calculate start and end times
    start_time = datetime.datetime.now().isoformat()
    end_time = (
        datetime.datetime.now() + datetime.timedelta(hours=duration_hours)
    ).isoformat()

    c.execute(
        """
        INSERT INTO reservations (node_id, gpu_id, user_name, mem_reserved, timestamp, start_time, end_time)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (node_id, gpu_id, user_name, mem_required, time.time(), start_time, end_time),
    )
    conn.commit()
    reservation_id = c.lastrowid
    conn.close()
    return reservation_id


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


def get_active_reservations(
    conn: sqlite3.Connection, user_filter: Optional[str] = None
) -> List[Tuple]:
    """
    Returns all active reservations, optionally filtered by user.
    Returns data as (id, gpu_id, user_name, start_time, end_time)
    """
    c = conn.cursor()

    if user_filter:
        c.execute(
            """
            SELECT id, gpu_id, user_name, start_time, end_time
            FROM reservations
            WHERE user_name = ?
            ORDER BY start_time DESC
            """,
            (user_filter,),
        )
    else:
        c.execute(
            """
            SELECT id, gpu_id, user_name, start_time, end_time
            FROM reservations
            ORDER BY start_time DESC
            """
        )

    return c.fetchall()


def cancel_reservation(conn: sqlite3.Connection, reservation_id: int) -> bool:
    """
    Cancels (deletes) a reservation by ID.
    Returns True if successful, False if not found.
    """
    c = conn.cursor()
    c.execute("DELETE FROM reservations WHERE id = ?", (reservation_id,))
    conn.commit()
    return c.rowcount > 0


def clear_reservations_in_db() -> None:
    """
    Removes all reservation rows from the database.
    """
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM reservations")
    conn.commit()
    conn.close()
