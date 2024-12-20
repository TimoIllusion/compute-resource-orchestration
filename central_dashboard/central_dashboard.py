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


class GPUProcess(BaseModel):
    pid: int
    user: str
    mem_usage: float


class GPUInfo(BaseModel):
    max_mem: float
    mem_usage: float
    processes: List[GPUProcess]


class NodeStatusUpdate(BaseModel):
    node_id: str
    cpu_usage: float
    mem_usage: float
    timestamp: float
    gpus: Dict[str, GPUInfo]  # Changed from Dict[int, Dict[str, float]]


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
            "reservation": node_reservations.get(update.node_id, None),
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
    user_name: str


@app.post("/api/reserve_node")
def reserve_node(req: ReservationRequest):
    if req.node_id not in node_data:
        raise HTTPException(status_code=404, detail="Node not found")
    node_reservations[req.node_id] = req.user_name
    node_data[req.node_id]["reservation"] = req.user_name
    return {"status": "reserved", "node_id": req.node_id, "user": req.user_name}


class GPURequest(BaseModel):
    node_id: str
    user_name: str
    mem_required: float
    session_type: str


@app.post("/api/request_gpu")
def request_gpu(req: GPURequest):
    if req.node_id not in node_data:
        raise HTTPException(status_code=404, detail="Node not found")

    node_info = node_data[req.node_id]
    for gpu_id, gpu_info in node_info.get("gpus", {}).items():
        if gpu_info["mem_usage"] + req.mem_required <= gpu_info["max_mem"]:
            gpu_info["mem_usage"] += req.mem_required
            gpu_info["processes"].append(
                {
                    "pid": int(time.time()),
                    "user": req.user_name,
                    "mem_usage": req.mem_required,
                }
            )
            return {"status": "ok", "node_id": req.node_id, "gpu_id": gpu_id}

    return {"status": "error", "message": "No suitable GPU found"}
