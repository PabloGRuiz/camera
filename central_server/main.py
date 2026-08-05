import uvicorn
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from database import SessionLocal, LogEvent, RegisteredNode

app = FastAPI(title="Central Server - Logs & Node Management")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

from pydantic import BaseModel, Field

class LogEventCreate(BaseModel):
    camera_id: str = Field(..., max_length=50)
    person_name: str = Field(..., max_length=100)
    role: str = Field(..., max_length=50)
    event_type: Optional[str] = Field("Persona", max_length=30)
    image_b64: Optional[str] = Field(None, max_length=2000000)

class NodeRegisterModel(BaseModel):
    node_id: str = Field(..., max_length=60)
    node_name: str = Field(..., max_length=100)
    ip_address: Optional[str] = None
    active_cameras_count: Optional[int] = 1

class NodeHeartbeatModel(BaseModel):
    node_id: str = Field(..., max_length=60)
    current_fps: float = 0.0
    inference_latency_ms: float = 0.0
    pending_logs_count: int = 0
    active_cameras_count: int = 1
    ip_address: Optional[str] = None

@app.post("/api/report_log")
def report_log(log: LogEventCreate, db: Session = Depends(get_db)):
    db_log = LogEvent(
        camera_id=log.camera_id,
        person_name=log.person_name,
        role=log.role,
        event_type=log.event_type or "Persona",
        image_b64=log.image_b64,
        timestamp=datetime.now()
    )
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    return {"status": "success", "id": db_log.id}

@app.post("/api/nodes/register")
def register_node(node: NodeRegisterModel, db: Session = Depends(get_db)):
    existing = db.query(RegisteredNode).filter(RegisteredNode.node_id == node.node_id).first()
    if existing:
        existing.node_name = node.node_name
        existing.last_seen = datetime.now()
        existing.status = "ONLINE"
        if node.ip_address:
            existing.ip_address = node.ip_address
        if node.active_cameras_count is not None:
            existing.active_cameras_count = node.active_cameras_count
    else:
        existing = RegisteredNode(
            node_id=node.node_id,
            node_name=node.node_name,
            status="ONLINE",
            last_seen=datetime.now(),
            ip_address=node.ip_address,
            active_cameras_count=node.active_cameras_count or 1
        )
        db.add(existing)
    db.commit()
    return {"status": "registered", "node_id": node.node_id}

@app.post("/api/nodes/heartbeat")
def node_heartbeat(hb: NodeHeartbeatModel, db: Session = Depends(get_db)):
    node = db.query(RegisteredNode).filter(RegisteredNode.node_id == hb.node_id).first()
    now = datetime.now()
    if not node:
        node = RegisteredNode(
            node_id=hb.node_id,
            node_name=f"Node {hb.node_id}",
            status="ONLINE",
            last_seen=now,
            current_fps=hb.current_fps,
            inference_latency_ms=hb.inference_latency_ms,
            pending_logs_count=hb.pending_logs_count,
            active_cameras_count=hb.active_cameras_count,
            ip_address=hb.ip_address
        )
        db.add(node)
    else:
        node.last_seen = now
        node.status = "ONLINE"
        node.current_fps = hb.current_fps
        node.inference_latency_ms = hb.inference_latency_ms
        node.pending_logs_count = hb.pending_logs_count
        node.active_cameras_count = hb.active_cameras_count
        if hb.ip_address:
            node.ip_address = hb.ip_address
    db.commit()
    return {"status": "ok", "timestamp": now.isoformat()}

@app.get("/api/nodes/status")
def get_nodes_status(db: Session = Depends(get_db)):
    nodes = db.query(RegisteredNode).all()
    result = []
    now = datetime.now()
    for n in nodes:
        seconds_diff = (now - n.last_seen).total_seconds()
        calc_status = "ONLINE" if seconds_diff <= 30 else "OFFLINE"
        if calc_status == "ONLINE" and n.pending_logs_count > 0:
            calc_status = "SYNCING"
            
        result.append({
            "node_id": n.node_id,
            "node_name": n.node_name,
            "status": calc_status,
            "last_seen": n.last_seen.strftime("%Y-%m-%d %H:%M:%S"),
            "seconds_since_last_seen": int(seconds_diff),
            "current_fps": n.current_fps,
            "inference_latency_ms": n.inference_latency_ms,
            "pending_logs_count": n.pending_logs_count,
            "active_cameras_count": n.active_cameras_count,
            "ip_address": n.ip_address or "Local"
        })
    return result

@app.get("/api/logs")
def get_logs(limit: int = 50, db: Session = Depends(get_db)):
    logs = db.query(LogEvent).order_by(LogEvent.timestamp.desc()).limit(limit).all()
    return logs

@app.delete("/api/logs")
def wipe_logs(db: Session = Depends(get_db)):
    try:
        db.query(LogEvent).delete()
        db.commit()
        return {"status": "success", "message": "Database wiped successfully"}
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": str(e)}
