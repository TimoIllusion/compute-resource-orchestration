from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Optional
import time

app = FastAPI()

# In-memory stores
node_data = {}
node_reservations = {}

class NodeStatusUpdate(BaseModel):
    node_id: str
    cpu_usage: float
    mem_usage: float
    timestamp: float

@app.post("/api/update_node_status")
def update_node_status(update: NodeStatusUpdate):
    node_data[update.node_id] = {
        "cpu_usage": update.cpu_usage,
        "mem_usage": update.mem_usage,
        "timestamp": update.timestamp,
        "reservation": node_reservations.get(update.node_id, None)
    }
    return {"status": "ok"}

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
