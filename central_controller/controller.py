from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from typing import Dict, Optional, List
import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# In-memory stores
node_data = {}
node_reservations = {}

MEMORY_BUFFER_PER_RESERVATION = 1.0  # 1GB buffer per reservation


class GPUProcess(BaseModel):
    pid: int
    user: str
    mem_usage: float


class GPUReservation(BaseModel):
    user: str
    mem_reserved: float


class GPUInfo(BaseModel):
    max_mem: float
    mem_usage: float
    processes: List[GPUProcess]
    reservations: List[GPUReservation] = []


class NodeStatusUpdate(BaseModel):
    node_id: str
    cpu_usage: float
    mem_usage: float
    timestamp: float
    gpus: Dict[str, GPUInfo]


@app.post("/api/update_node_status")
async def update_node_status(request: Request):
    try:
        body = await request.json()
        logger.info(f"Received data: {body}")
        update = NodeStatusUpdate(**body)
        node_data[update.node_id] = {
            "cpu_usage": update.cpu_usage,
            "mem_usage": update.mem_usage,
            "timestamp": update.timestamp,
            "gpus": update.dict()["gpus"],
        }
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=422, detail=str(e))


@app.get("/api/list_nodes")
def list_nodes():
    return node_data


class ReservationRequest(BaseModel):
    node_id: str
    gpu_id: str
    user_name: str
    mem_required: float


@app.post("/api/reserve_gpu")
def reserve_gpu(req: ReservationRequest):
    if req.node_id not in node_data:
        raise HTTPException(status_code=404, detail="Node not found")
    if req.gpu_id not in node_data[req.node_id]["gpus"]:
        raise HTTPException(status_code=404, detail="GPU not found")

    gpu_info = node_data[req.node_id]["gpus"][req.gpu_id]

    total_reserved = sum(
        (r["mem_reserved"] + MEMORY_BUFFER_PER_RESERVATION)
        for r in gpu_info.get("reservations", [])
    )

    if (
        total_reserved + req.mem_required + MEMORY_BUFFER_PER_RESERVATION
        > gpu_info["max_mem"]
    ):
        raise HTTPException(
            status_code=400, detail="Insufficient GPU memory for reservation"
        )

    if "reservations" not in gpu_info:
        gpu_info["reservations"] = []
    gpu_info["reservations"].append(
        {"user": req.user_name, "mem_reserved": req.mem_required}
    )

    return {
        "status": "reserved",
        "node_id": req.node_id,
        "gpu_id": req.gpu_id,
        "user": req.user_name,
        "mem_reserved": req.mem_required,
    }


@app.post("/api/finish_reservation")
def finish_reservation(req: ReservationRequest):
    if req.node_id not in node_data:
        raise HTTPException(status_code=404, detail="Node not found")
    if req.gpu_id not in node_data[req.node_id]["gpus"]:
        raise HTTPException(status_code=404, detail="GPU not found")

    gpu_info = node_data[req.node_id]["gpus"][req.gpu_id]
    current_reservations = gpu_info.get("reservations", [])

    matching = [
        r
        for r in current_reservations
        if r["user"] == req.user_name and r["mem_reserved"] == req.mem_required
    ]
    if not matching:
        raise HTTPException(status_code=404, detail="Reservation not found")

    # Remove from active GPU reservations
    current_reservations.remove(matching[0])

    # Keep old reservations in separate store
    if req.node_id not in node_reservations:
        node_reservations[req.node_id] = {}
    if req.gpu_id not in node_reservations[req.node_id]:
        node_reservations[req.node_id][req.gpu_id] = []
    node_reservations[req.node_id][req.gpu_id].append(matching[0])

    return {"status": "freed", "reservation": matching[0]}


@app.get("/api/list_reservation_history")
def list_reservation_history():
    return node_reservations


class GPURequest(BaseModel):
    node_id: str
    gpu_id: str
    user_name: str
    mem_required: float
    session_type: str


class FindGPURequest(BaseModel):
    user_name: str
    mem_required: float
    session_type: str


@app.post("/api/request_gpu")
def request_gpu(req: GPURequest):
    if req.node_id not in node_data:
        raise HTTPException(status_code=404, detail="Node not found")
    if req.gpu_id not in node_data[req.node_id]["gpus"]:
        raise HTTPException(status_code=404, detail="GPU not found")

    gpu_info = node_data[req.node_id]["gpus"][req.gpu_id]
    if gpu_info["mem_usage"] + req.mem_required <= gpu_info["max_mem"]:
        gpu_info["mem_usage"] += req.mem_required
        gpu_info["processes"].append(
            {
                "pid": int(time.time()),
                "user": req.user_name,
                "mem_usage": req.mem_required,
            }
        )
        return {"status": "ok", "node_id": req.node_id, "gpu_id": req.gpu_id}
    return {"status": "error", "message": "No suitable GPU found"}


@app.post("/api/find_best_gpu")
def find_best_gpu(req: FindGPURequest):
    best_gpu = None
    best_node = None
    most_available_mem = -1

    for node_id, node_info in node_data.items():
        for gpu_id, gpu_info in node_info.get("gpus", {}).items():
            # Skip any GPU that already has at least one reservation.
            # This ensures if there is one user already reserving a GPU,
            # we move on to a fresh GPU for another new user.
            if len(gpu_info.get("reservations", [])) > 0:
                continue

            total_reserved = sum(
                (r["mem_reserved"] + MEMORY_BUFFER_PER_RESERVATION)
                for r in gpu_info.get("reservations", [])
            )
            available_mem = gpu_info["max_mem"] - total_reserved

            if (
                available_mem >= (req.mem_required + MEMORY_BUFFER_PER_RESERVATION)
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
