import os
import urllib.request
import logging
import cv2
import numpy as np
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from app.core.face_db import face_db

logger = logging.getLogger("FaceRecognizer")

YUNET_MODEL_URL = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
SFACE_MODEL_URL = "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx"

class OpenVINOFaceRecognizer:
    """
    Reconocedor Facial de Ultra-Baja Latencia basado en OpenCV YuNet (Detección) y SFace (Extracción de Embeddings 128D).
    Calcula similitud de coseno contra la base de datos de personas enroladas.
    """
    def __init__(self, models_dir: str = "models"):
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        
        self.yunet_path = self.models_dir / "face_detection_yunet_2023mar.onnx"
        self.sface_path = self.models_dir / "face_recognition_sface_2021dec.onnx"
        
        self.detector = None
        self.recognizer = None
        self.is_ready = False
        self.is_initialized = False

    def _download_file(self, url: str, target_path: Path):
        if not target_path.exists() or target_path.stat().st_size == 0:
            logger.info(f"Descargando modelo facial desde {url}...")
            req = urllib.request.Request(
                url, 
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            )
            with urllib.request.urlopen(req, timeout=10) as response, open(target_path, 'wb') as out_file:
                out_file.write(response.read())
            logger.info(f"Modelo facial guardado en {target_path.resolve()}")

    def _ensure_models_and_init(self):
        try:
            # Si los modelos no existen localmente, descargarlos con timeout corto
            self._download_file(YUNET_MODEL_URL, self.yunet_path)
            self._download_file(SFACE_MODEL_URL, self.sface_path)

            if self.yunet_path.exists() and self.sface_path.exists():
                if hasattr(cv2, "FaceDetectorYN") and hasattr(cv2, "FaceRecognizerSF"):
                    self.detector = cv2.FaceDetectorYN.create(
                        model=str(self.yunet_path),
                        config="",
                        input_size=(320, 320),
                        score_threshold=0.6,
                        nms_threshold=0.3,
                        top_k=5
                    )
                    self.recognizer = cv2.FaceRecognizerSF.create(
                        model=str(self.sface_path),
                        config=""
                    )
                    self.is_ready = True
                    logger.info("Motor de Reconocimiento Facial YuNet + SFace inicializado correctamente.")
                else:
                    logger.warning("Tu versión de OpenCV no cuenta con FaceDetectorYN/FaceRecognizerSF.")
        except Exception as e:
            logger.warning(f"No se pudieron cargar los modelos de reconocimiento facial (¿red inestable/sin acceso a GitHub?): {e}")
            self.is_ready = False

    def extract_embedding(self, frame: np.ndarray, bbox: Optional[List[int]] = None) -> Optional[np.ndarray]:
        """
        Detecta el rostro principal en la imagen (o dentro del recuadro dado) y retorna su vector 128D.
        """
        if not self.is_initialized:
            self.is_initialized = True
            self._ensure_models_and_init()

        if not self.is_ready or frame is None or frame.size == 0:
            return None

        h, w = frame.shape[:2]
        
        # Si se pasa un bbox, recortar la región del sujeto
        if bbox and len(bbox) == 4:
            x1, y1, x2, y2 = [max(0, int(c)) for c in bbox]
            crop = frame[y1:min(h, y2), x1:min(w, x2)]
            if crop.size == 0:
                crop = frame
        else:
            crop = frame

        ch, cw = crop.shape[:2]
        if ch < 40 or cw < 40:
            return None

        self.detector.setInputSize((cw, ch))
        _, faces = self.detector.detect(crop)

        if faces is None or len(faces) == 0:
            return None

        # Tomar el rostro con mayor puntuación de confianza
        best_face = faces[0]

        # Alinear rostro y extraer vector 128-D mediante SFace
        aligned_face = self.recognizer.alignCrop(crop, best_face)
        feature_vector = self.recognizer.feature(aligned_face)

        return feature_vector.flatten()

    def recognize_face_in_bbox(self, frame: np.ndarray, bbox: List[int], threshold: float = 0.50) -> Optional[Dict[str, Any]]:
        """
        Extrae el rostro en la región de la persona y lo compara con la Base de Datos.
        Retorna la identidad y el % de Similitud.
        """
        embedding = self.extract_embedding(frame, bbox)
        if embedding is None:
            return None

        match_info = face_db.match_face(embedding, threshold=threshold)
        return match_info

# Instancia Singleton del Reconocedor Facial
face_recognizer = OpenVINOFaceRecognizer()
