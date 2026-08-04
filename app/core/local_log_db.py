import os
import sqlite3
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

logger = logging.getLogger("LocalLogDB")

class LocalLogDatabase:
    """
    Gestor de almacenamiento persistente local para capturas registradas en el nodo Edge.
    Almacena el historial diario completo con imágenes Base64 en SQLite (data/local_logs.db).
    """

    def __init__(self, db_path: str = "data/local_logs.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self):
        return sqlite3.connect(str(self.db_path), check_same_thread=False)

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS local_captures (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    date_str TEXT NOT NULL,
                    time_str TEXT NOT NULL,
                    camera_id TEXT NOT NULL,
                    track_id INTEGER,
                    name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    event_type TEXT DEFAULT 'Persona',
                    image_b64 TEXT NOT NULL
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_date_str ON local_captures(date_str)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_camera_id ON local_captures(camera_id)")
            conn.commit()
        logger.info(f"Base de Datos Local de Capturas SQLite inicializada en: {self.db_path.resolve()}")

    def add_log(self, camera_id: str, track_id: Optional[int], name: str, status: str, event_type: str, image_b64: str) -> int:
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M:%S")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO local_captures (date_str, time_str, camera_id, track_id, name, status, event_type, image_b64)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (date_str, time_str, camera_id, track_id, name, status, event_type, image_b64))
            conn.commit()
            return cursor.lastrowid

    def get_logs(self, limit: int = 200, date_str: Optional[str] = None, camera_id: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT id, date_str, time_str, camera_id, track_id, name, status, event_type, image_b64, timestamp FROM local_captures"
            params = []
            conditions = []

            if date_str:
                conditions.append("date_str = ?")
                params.append(date_str)
            if camera_id:
                conditions.append("camera_id = ?")
                params.append(camera_id)

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            query += " ORDER BY id DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()

            result = []
            for row in rows:
                result.append({
                    "id": row[0],
                    "date": row[1],
                    "timestamp": row[2],
                    "camera_id": row[3],
                    "track_id": row[4],
                    "name": row[5],
                    "status": row[6],
                    "event_type": row[7],
                    "image": row[8] if row[8].startswith("data:image") else f"data:image/jpeg;base64,{row[8]}",
                    "full_timestamp": row[9]
                })
            return result

    def clear_logs(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM local_captures")
            conn.commit()
        logger.info("Historial de capturas locales vaciado con éxito.")

    def purge_old_logs(self, days_to_keep: int = 7):
        cutoff_date = (datetime.now() - timedelta(days=days_to_keep)).strftime("%Y-%m-%d")
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM local_captures WHERE date_str < ?", (cutoff_date,))
            conn.commit()

local_log_db = LocalLogDatabase()
