import uvicorn
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import cluster
import db
from typing import List, Dict, Optional, Any
import sqlite3  # Import sqlite3 for exception handling
import logging
import time
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="Compute Resource Orchestrator API")

# Allow CORS for frontend development (adjust in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "*"
    ],  # Or specify your frontend origin e.g., "http://localhost:8080"
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store for real-time GPU metrics
gpu_metrics = {}
registered_workers = {}


# Dependency to get DB connection
def get_db_conn():
    conn = db.create_connection()
    if conn is None:
        # This should ideally not happen if db.py handles errors, but good practice
        raise HTTPException(status_code=500, detail="Database connection failed")
    try:
        yield conn
    finally:
        if conn:
            conn.close()


@app.on_event("startup")
def on_startup():
    """Initialize the database on startup."""
    conn = None
    try:
        conn = db.create_connection()
        if conn:
            db.create_tables(conn)
        else:
            logger.error("Could not create database connection on startup.")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
    finally:
        if conn:
            conn.close()
    # Initialize cluster state (optional, depending on desired startup behavior)
    # cluster.initialize_cluster_state() # You might want this


@app.get("/status", response_model=List[Dict])
def get_cluster_status():
    """Get the current status of all GPUs in the cluster."""
    try:
        # Get basic cluster status info
        status_info = cluster.get_gpu_status()

        # Enhance with real-time metrics when available
        for i, gpu in enumerate(status_info):
            node_id = gpu["node_id"]
            gpu_id = gpu["gpu_id"]

            # Add real-time metrics if available
            metric_key = f"{node_id}_{gpu_id}"
            if metric_key in gpu_metrics:
                # Add the real-time metrics
                gpu["real_metrics"] = gpu_metrics[metric_key]

        return status_info
    except Exception as e:
        logger.error(f"Failed to get cluster status: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get cluster status: {str(e)}"
        )


@app.post("/reserve", response_model=Dict[str, str])
def reserve_gpu(
    user: str = "default_user",
    duration_hours: int = 1,
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    """Find the best available GPU and reserve it."""
    # In the future, 'user' will come from authentication
    try:
        best_gpu_id = cluster.find_best_gpu()
        if best_gpu_id is None:
            raise HTTPException(status_code=404, detail="No suitable GPU available")

        # Correctly call reserve_gpu with parameters
        reservation_id = cluster.reserve_gpu(conn, best_gpu_id, user, duration_hours)
        return {
            "message": f"GPU {best_gpu_id} reserved successfully",
            "reservation_id": str(reservation_id),
            "gpu_id": best_gpu_id,
        }
    except (
        ValueError
    ) as e:  # Specific exception from cluster.reserve_gpu if already reserved
        logger.warning(f"GPU reservation conflict: {e}")
        raise HTTPException(
            status_code=409, detail=str(e)
        )  # Conflict if already reserved
    except HTTPException as e:  # Re-raise HTTP exceptions
        raise e
    except Exception as e:
        logger.error(f"Failed to reserve GPU: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reserve GPU: {str(e)}")


@app.post("/cancel/{reservation_id}", response_model=Dict[str, str])
def cancel_reservation_endpoint(
    reservation_id: int, conn: sqlite3.Connection = Depends(get_db_conn)
):
    """Cancel an existing reservation."""
    # Add user check here later based on authentication
    try:
        success = cluster.cancel_reservation_wrapper(conn, reservation_id)
        if success:
            return {"message": f"Reservation {reservation_id} cancelled successfully."}
        else:
            # This might happen if the reservation doesn't exist or doesn't belong to the user (future)
            raise HTTPException(
                status_code=404,
                detail=f"Reservation {reservation_id} not found or could not be cancelled.",
            )
    except HTTPException as e:  # Re-raise HTTP exceptions
        raise e
    except Exception as e:
        logger.error(f"Failed to cancel reservation: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to cancel reservation: {str(e)}"
        )


@app.get("/reservations", response_model=List[Dict])
def get_all_reservations(
    user: Optional[str] = None, conn: sqlite3.Connection = Depends(get_db_conn)
):
    """Get all active reservations, optionally filtered by user."""
    # Filter by user will be important with authentication
    try:
        reservations = db.get_active_reservations(conn, user_filter=user)
        # Convert tuples to dicts for easier JSON serialization
        return [
            {
                "id": r[0],
                "gpu_id": r[1],
                "user": r[2],
                "start_time": r[3],
                "end_time": r[4],
            }
            for r in reservations
        ]
    except Exception as e:
        logger.error(f"Failed to retrieve reservations: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve reservations: {str(e)}"
        )


@app.post("/reset", response_model=Dict[str, str])
def reset_cluster_endpoint(conn: sqlite3.Connection = Depends(get_db_conn)):
    """Reset the cluster state and clear all reservations."""
    try:
        cluster.reset_reservations(conn)
        # Re-initialize cluster state if needed
        # cluster.initialize_cluster_state() # Consider if this is needed
        return {"message": "Cluster reset successfully."}
    except Exception as e:
        logger.error(f"Failed to reset cluster: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to reset cluster: {str(e)}"
        )


@app.get("/find_best", response_model=Dict[str, str])
def find_best_gpu_endpoint():
    """Find the best available GPU without reserving it."""
    try:
        best_gpu_id = cluster.find_best_gpu()
        if best_gpu_id is None:
            raise HTTPException(status_code=404, detail="No suitable GPU available")
        return {"best_gpu_id": best_gpu_id}
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Failed to find best GPU: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to find best GPU: {str(e)}"
        )


# New endpoints for GPU worker support and monitoring


@app.post("/register_worker")
def register_worker(worker_info: Dict[str, Any]):
    """Register a GPU worker with the orchestration system."""
    try:
        worker_id = worker_info.get("worker_id")
        node_id = worker_info.get("node_id")
        gpu_id = worker_info.get("gpu_id")

        if not all([worker_id, node_id, gpu_id]):
            raise HTTPException(
                status_code=400, detail="Missing required worker information"
            )

        worker_key = f"{worker_id}"
        metric_key = f"{node_id}_{gpu_id}"

        registered_workers[worker_key] = {
            "worker_id": worker_id,
            "node_id": node_id,
            "gpu_id": gpu_id,
            "registered_at": datetime.now().isoformat(),
            "last_seen": datetime.now().isoformat(),
            "capabilities": worker_info.get("capabilities", {}),
        }

        logger.info(f"Registered new worker: {worker_id} on {node_id} GPU {gpu_id}")

        return {"status": "registered", "worker_id": worker_id}
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Failed to register worker: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to register worker: {str(e)}"
        )


@app.post("/gpu_metrics")
def receive_gpu_metrics(metrics: Dict[str, Any]):
    """Receive GPU metrics from workers."""
    try:
        node_id = metrics.get("node_id")
        gpu_id = metrics.get("gpu_id")

        if not all([node_id, gpu_id]):
            raise HTTPException(
                status_code=400, detail="Missing required metric information"
            )

        # Store the latest metrics
        metric_key = f"{node_id}_{gpu_id}"
        gpu_metrics[metric_key] = {
            "timestamp": metrics.get("timestamp", time.time()),
            "memory": metrics.get("memory", {"total": 0, "used": 0, "free": 0}),
            "utilization": metrics.get("utilization", {"gpu": 0, "memory": 0}),
            "temperature": metrics.get("temperature", 0),
            "power": metrics.get("power", 0),
            "processes": metrics.get("processes", []),
            "managed_processes": metrics.get("managed_processes", []),
        }

        # Update worker last seen time if we can identify the worker
        for worker_id, worker_info in registered_workers.items():
            if worker_info["node_id"] == node_id and worker_info["gpu_id"] == gpu_id:
                worker_info["last_seen"] = datetime.now().isoformat()

        return {"status": "received"}
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Failed to process GPU metrics: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to process GPU metrics: {str(e)}"
        )


@app.get("/workers", response_model=List[Dict])
def get_workers():
    """Get information about registered GPU workers."""
    try:
        return list(registered_workers.values())
    except Exception as e:
        logger.error(f"Failed to retrieve worker information: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve worker information: {str(e)}"
        )


@app.post("/start_process", response_model=Dict[str, str])
def start_process(
    background_tasks: BackgroundTasks,
    gpu_id: str,
    memory_usage: float = 1.0,
    duration_minutes: int = 30,
):
    """Start a GPU process on a worker."""
    try:
        # Find the corresponding worker for this GPU
        worker_id = None
        for worker, info in registered_workers.items():
            if info["gpu_id"] == gpu_id:
                worker_id = worker
                break

        if not worker_id:
            raise HTTPException(
                status_code=404, detail=f"No worker found for GPU {gpu_id}"
            )

        # Construct worker URL based on node/GPU ID
        node_id = registered_workers[worker_id]["node_id"]
        worker_url = f"http://gpu_worker_{int(gpu_id) + 1}:8000"  # Assumes worker containers are named gpu_worker_1, gpu_worker_2, etc.

        # In a real implementation, we'd make an HTTP request to the worker
        # For now, we'll simulate success and rely on the worker's automatic reporting
        process_id = f"proc_{int(time.time())}"

        return {
            "status": "started",
            "process_id": process_id,
            "gpu_id": gpu_id,
            "memory_usage": str(memory_usage),
            "duration_minutes": str(duration_minutes),
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Failed to start GPU process: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to start GPU process: {str(e)}"
        )


@app.post("/stop_process/{process_id}", response_model=Dict[str, str])
def stop_process(process_id: str):
    """Stop a running GPU process."""
    try:
        # Find which worker is running this process
        target_worker = None
        for metric_key, metrics in gpu_metrics.items():
            for proc in metrics.get("managed_processes", []):
                if proc.get("process_id") == process_id:
                    node_id, gpu_id = metric_key.split("_")
                    target_worker = f"gpu_worker_{int(gpu_id) + 1}"
                    break
            if target_worker:
                break

        if not target_worker:
            raise HTTPException(
                status_code=404, detail=f"Process {process_id} not found"
            )

        # In a real implementation, we'd make an HTTP request to the worker
        # For now, we'll simulate success
        return {"status": "stopped", "process_id": process_id}
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Failed to stop GPU process: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to stop GPU process: {str(e)}"
        )


@app.get("/processes", response_model=List[Dict])
def get_processes():
    """Get information about all running GPU processes."""
    try:
        all_processes = []

        # Collect processes from all GPU metrics
        for metric_key, metrics in gpu_metrics.items():
            node_id, gpu_id = metric_key.split("_")

            # Add system processes
            for proc in metrics.get("processes", []):
                proc_info = {
                    "gpu_id": gpu_id,
                    "node_id": node_id,
                    "pid": proc.get("pid"),
                    "name": proc.get("name"),
                    "memory_usage": proc.get("memory_usage"),
                    "command": proc.get("command", ""),
                    "type": "system",
                }
                all_processes.append(proc_info)

            # Add managed processes
            for proc in metrics.get("managed_processes", []):
                proc_info = {
                    "gpu_id": gpu_id,
                    "node_id": node_id,
                    "process_id": proc.get("process_id"),
                    "memory_allocated": proc.get("memory_allocated"),
                    "runtime": proc.get("runtime"),
                    "duration": proc.get("duration"),
                    "type": "managed",
                }
                all_processes.append(proc_info)

        return all_processes
    except Exception as e:
        logger.error(f"Failed to retrieve process information: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve process information: {str(e)}"
        )


if __name__ == "__main__":
    # Make sure DB exists and tables are created before starting
    # This is already handled by the startup event, but can be kept for running directly
    conn = None
    try:
        conn = db.create_connection()
        if conn:
            db.create_tables(conn)
        else:
            logger.error("Could not create database connection before starting server.")
            # Decide if you want to exit here if DB connection fails
    except Exception as e:
        logger.error(f"Database check/creation failed before start: {e}")
    finally:
        if conn:
            conn.close()

    logger.info("Starting API server on http://0.0.0.0:8000")
    # Ensure host and port are correct for Docker exposure
    uvicorn.run(app, host="0.0.0.0", port=8000)
