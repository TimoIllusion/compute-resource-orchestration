import uvicorn
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
import cluster
import db
from typing import List, Dict, Optional
import sqlite3  # Import sqlite3 for exception handling
import logging

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
        return cluster.get_gpu_status()
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


# Add a find_best endpoint if needed separately from reserve
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

# Removed all Streamlit related code.
