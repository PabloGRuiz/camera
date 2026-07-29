import os
import sqlite3
import numpy as np
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger("SymbolDB")

class SymbolDatabase:
    """
    Gestor de Base de Datos de Símbolos, Insignias y Logos persistente basado en SQLite.
    Almacena nombres, categorías y vectores de características (embeddings).
    Realiza comparación por Similitud del Coseno (Cosine Similarity).
    """

    def __init__(self, db_path: str = "data/symbols.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self):
        return sqlite3.connect(str(self.db_path))

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS enrolled_symbols (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    category TEXT DEFAULT 'Insignia',
                    description TEXT DEFAULT '',
                    embedding BLOB NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
        logger.info(f"Base de Datos de Símbolos SQLite inicializada en: {self.db_path.resolve()}")

    def register_symbol(self, name: str, category: str, description: str, embedding: np.ndarray) -> bool:
        """
        Registra un nuevo símbolo/insignia en la base de datos con su vector de características.
        """
        try:
            embedding_bytes = embedding.astype(np.float32).tobytes()
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO enrolled_symbols (name, category, description, embedding)
                    VALUES (?, ?, ?, ?)
                """, (name.strip(), category.strip(), description.strip(), embedding_bytes))
                conn.commit()
            logger.info(f"Símbolo/Insignia enrolado exitosamente: {name} ({category})")
            return True
        except Exception as e:
            logger.error(f"Error enrolando símbolo {name}: {e}")
            return False

    def get_all_symbols(self) -> List[Dict[str, Any]]:
        """
        Devuelve la lista de todos los símbolos e insignias registrados.
        """
        symbols = []
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, name, category, description, created_at FROM enrolled_symbols ORDER BY id DESC")
                rows = cursor.fetchall()
                for r in rows:
                    symbols.append({
                        "id": r[0],
                        "name": r[1],
                        "category": r[2],
                        "description": r[3],
                        "created_at": r[4]
                    })
        except Exception as e:
            logger.error(f"Error consultando símbolos enrolados: {e}")
        return symbols

    def delete_symbol(self, symbol_id: int) -> bool:
        """
        Elimina un símbolo por su ID.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM enrolled_symbols WHERE id = ?", (symbol_id,))
                conn.commit()
            logger.info(f"Símbolo ID {symbol_id} eliminado correctamente")
            return True
        except Exception as e:
            logger.error(f"Error eliminando símbolo ID {symbol_id}: {e}")
            return False

    def match_symbol(self, target_embedding: np.ndarray, threshold: float = 0.35) -> Optional[Dict[str, Any]]:
        """
        Compara un vector de características contra la base de datos usando Similitud del Coseno.
        Devuelve el símbolo más cercano si supera el umbral de similitud.
        """
        if target_embedding is None or target_embedding.size == 0:
            return None

        highest_similarity = -1.0
        best_match = None

        try:
            target_norm = target_embedding / (np.linalg.norm(target_embedding) + 1e-10)

            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, name, category, description, embedding FROM enrolled_symbols")
                rows = cursor.fetchall()

                for r in rows:
                    s_id, name, category, description, db_blob = r
                    db_vector = np.frombuffer(db_blob, dtype=np.float32)
                    db_norm = db_vector / (np.linalg.norm(db_vector) + 1e-10)

                    similarity = float(np.dot(target_norm, db_norm.flatten()))

                    if similarity > highest_similarity:
                        highest_similarity = similarity
                        best_match = {
                            "id": s_id,
                            "name": name,
                            "category": category,
                            "description": description,
                            "similarity": round(max(0.0, similarity) * 100.0, 1)
                        }

        except Exception as e:
            logger.error(f"Error realizando comparación de símbolo: {e}")

        if best_match and (highest_similarity >= threshold):
            return best_match

        return None

symbol_db = SymbolDatabase()
