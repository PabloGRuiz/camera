import uvicorn
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from database import SessionLocal, LogEvent

app = FastAPI(title="Central Server - Logs")

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
