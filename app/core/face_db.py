import os
import sqlite3
import numpy as np
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger("FaceDB")

class FaceDatabase:
    """
    Gestor de Base de Datos Biométricas Persistente basado en SQLite.
    Guarda información de identidad y vectores faciales de 128 dimensiones.
    Realiza comparación por Similitud del Coseno (Cosine Similarity).
    """

    def __init__(self, db_path: str = "data/faces.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self):
        return sqlite3.connect(str(self.db_path))

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS enrolled_persons (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    dni TEXT UNIQUE NOT NULL,
                    role TEXT DEFAULT 'Usuario',
                    embedding BLOB NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
        logger.info(f"Base de Datos Biométrica SQLite inicializada en: {self.db_path.resolve()}")

    def register_person(self, name: str, dni: str, role: str, embedding: np.ndarray) -> bool:
        """
        Registra una nueva persona en la base de datos con su vector biométrico 128D.
        """
        try:
            # Convertir vector float32 numpy a bytes para almacenamiento BLOB
            embedding_bytes = embedding.astype(np.float32).tobytes()
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO enrolled_persons (name, dni, role, embedding)
                    VALUES (?, ?, ?, ?)
                """, (name.strip(), dni.strip(), role.strip(), embedding_bytes))
                conn.commit()
            logger.info(f"Persona enrolada exitosamente: {name} (DNI: {dni})")
            return True
        except Exception as e:
            logger.error(f"Error enrolando persona {name}: {e}")
            return False

    def get_all_persons(self) -> List[Dict[str, Any]]:
        """
        Retorna la lista de todas las personas registradas (sin retornar los datos binarios pesados).
        """
        persons = []
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, name, dni, role, created_at FROM enrolled_persons ORDER BY id DESC")
                rows = cursor.fetchall()
                for row in rows:
                    persons.append({
                        "id": row[0],
                        "name": row[1],
                        "dni": row[2],
                        "role": row[3],
                        "created_at": row[4]
                    })
        except Exception as e:
            logger.error(f"Error consultando personas registradas: {e}")
        return persons

    def delete_person(self, person_id: int) -> bool:
        """
        Elimina un registro de la base de datos por su ID.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM enrolled_persons WHERE id = ?", (person_id,))
                conn.commit()
            logger.info(f"Persona con ID {person_id} eliminada de la base de datos.")
            return True
        except Exception as e:
            logger.error(f"Error eliminando persona con ID {person_id}: {e}")
            return False

    def match_face(self, target_embedding: np.ndarray, threshold: float = 0.50) -> Optional[Dict[str, Any]]:
        """
        Compara un vector biométrico detectado contra toda la BD usando Similitud del Coseno.
        Retorna la persona con el mayor porcentaje de similitud si supera el umbral.
        """
        if target_embedding is None or len(target_embedding) == 0:
            return None

        # Normalizar vector buscado para Similitud del Coseno
        target_norm = target_embedding / (np.linalg.norm(target_embedding) + 1e-10)

        best_match = None
        highest_similarity = -1.0

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, name, dni, role, embedding FROM enrolled_persons")
                rows = cursor.fetchall()

                for row in rows:
                    p_id, name, dni, role, emb_blob = row
                    db_vector = np.frombuffer(emb_blob, dtype=np.float32)
                    
                    if len(db_vector) != len(target_norm):
                        continue

                    db_norm = db_vector / (np.linalg.norm(db_vector) + 1e-10)

                    # Similitud del Coseno: cos(theta) = (A . B) / (||A|| * ||B||)
                    similarity = float(np.dot(target_norm, db_norm.flatten()))

                    if similarity > highest_similarity:
                        highest_similarity = similarity
                        best_match = {
                            "id": p_id,
                            "name": name,
                            "dni": dni,
                            "role": role,
                            "similarity": round(max(0.0, similarity) * 100.0, 1)  # Convertir a Porcentaje (0 - 100%)
                        }

        except Exception as e:
            logger.error(f"Error realizando comparación biométrica: {e}")

        # Retornar coincidencia solo si supera el umbral mínimo de confianza (ej 50-70%)
        if best_match and (highest_similarity >= threshold):
            return best_match

        # Si se procesó un vector válido pero no superó el umbral, retornar "Desconocido"
        return {
            "id": -1,
            "name": "Desconocido",
            "dni": "N/A",
            "role": "No Registrado",
            "similarity": round(max(0.0, highest_similarity) * 100.0, 1)
        }

# Instancia Singleton de la Base de Datos Biométrica
face_db = FaceDatabase()
