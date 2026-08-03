import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./central_logs.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class LogEvent(Base):
    __tablename__ = "log_events"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.now)
    camera_id = Column(String, index=True)
    person_name = Column(String, index=True)
    role = Column(String)
    event_type = Column(String, default="Persona", index=True)
    image_b64 = Column(String, nullable=True)

Base.metadata.create_all(bind=engine)

# Auto migration for missing column in existing SQLite databases
with engine.connect() as conn:
    try:
        from sqlalchemy import text
        conn.execute(text("ALTER TABLE log_events ADD COLUMN event_type VARCHAR DEFAULT 'Persona'"))
        conn.commit()
    except Exception:
        pass
