import pytest
import numpy as np
from app.core.face_db import FaceDatabase

def test_face_db_registration_and_matching(tmp_path):
    # Usar base de datos temporal
    db_file = tmp_path / "test_faces.db"
    db = FaceDatabase(db_path=str(db_file))

    # Crear 2 vectores sintéticos de 128-D distintos
    vector_juan = np.random.randn(128).astype(np.float32)
    vector_juan = vector_juan / np.linalg.norm(vector_juan)

    vector_maria = np.random.randn(128).astype(np.float32)
    vector_maria = vector_maria / np.linalg.norm(vector_maria)

    # 1. Registrar personas
    assert db.register_person("Juan Perez", "12345678", "Empleado", vector_juan) is True
    assert db.register_person("Maria Gomez", "87654321", "VIP", vector_maria) is True

    # 2. Consultar lista
    persons = db.get_all_persons()
    assert len(persons) == 2

    # 3. Probar Match idéntico (100% de similitud para Juan)
    match_juan = db.match_face(vector_juan, threshold=0.50)
    assert match_juan is not None
    assert match_juan["name"] == "Juan Perez"
    assert match_juan["similarity"] >= 99.0

    # 4. Probar vector con pequeño ruido (Similitud alta)
    noise_vector = vector_juan + np.random.randn(128) * 0.05
    match_noisy = db.match_face(noise_vector, threshold=0.50)
    assert match_noisy is not None
    assert match_noisy["name"] == "Juan Perez"

    # 5. Eliminar persona
    assert db.delete_person(match_juan["id"]) is True
    assert len(db.get_all_persons()) == 1
