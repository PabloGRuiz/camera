import cv2
import numpy as np
import logging
from typing import Dict, Any, Optional, Tuple, List
from app.core.symbol_db import symbol_db

logger = logging.getLogger("SymbolRecognizer")

class SymbolRecognizer:
    """
    Extractor y Reconocedor de Símbolos, Insignias, Rangos Militares y Logos.
    Genera huellas digitales visuales (Feature Embeddings) invariantes a escala y luminosidad.
    """

    def __init__(self):
        self.target_size = (64, 64)

    def extract_embedding(self, patch: np.ndarray) -> Optional[np.ndarray]:
        """
        Extrae un vector de características de 256 dimensiones desde un recorte (Crop) de imagen.
        Combina histograma de color en espacio HSV con descriptores de textura HOG/gradientes.
        """
        if patch is None or patch.size == 0 or patch.shape[0] < 10 or patch.shape[1] < 10:
            return None

        try:
            # 1. Normalizar tamaño
            resized = cv2.resize(patch, self.target_size, interpolation=cv2.INTER_AREA)

            # 2. Convertir a HSV para invarianza a cambios menores de iluminación
            hsv = cv2.cvtColor(resized, cv2.COLOR_BGR2HSV)
            
            # Histograma HSV (32 bins para H, 16 para S, 16 para V)
            hist_h = cv2.calcHist([hsv], [0], None, [32], [0, 180])
            hist_s = cv2.calcHist([hsv], [1], None, [16], [0, 256])
            hist_v = cv2.calcHist([hsv], [2], None, [16], [0, 256])
            
            hist_feat = np.concatenate([hist_h.flatten(), hist_s.flatten(), hist_v.flatten()])
            hist_feat /= (np.linalg.norm(hist_feat) + 1e-10)

            # 3. Gradientes Estructurales (Textura/Formas del Logo/Insignia)
            gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
            gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
            gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
            magnitude, angle = cv2.cartToPolar(gx, gy, angleInDegrees=True)
            
            # Histograma de orientación de gradientes (192 bins)
            grad_hist, _ = np.histogram(angle, bins=192, range=(0, 360), weights=magnitude)
            grad_feat = grad_hist.astype(np.float32)
            grad_feat /= (np.linalg.norm(grad_feat) + 1e-10)

            # 4. Concatenar Vector (64 bins HSV + 192 bins Gradiente = 256 dimensions)
            embedding = np.concatenate([hist_feat, grad_feat])
            embedding /= (np.linalg.norm(embedding) + 1e-10)

            return embedding.astype(np.float32)

        except Exception as e:
            logger.error(f"Error extrayendo embedding de símbolo: {e}")
            return None

    def recognize_symbol_in_bbox(self, frame: np.ndarray, bbox: List[float], threshold: float = 0.35) -> Optional[Dict[str, Any]]:
        """
        Extrae la región de interés (bbox) en el frame y sus sub-regiones (pecho/hombros para rangos militar),
        calcula sus embeddings y consulta la base de datos de símbolos.
        """
        try:
            x1, y1, x2, y2 = [int(c) for c in bbox]
            h, w = frame.shape[:2]
            
            x1_c, y1_c = max(0, x1), max(0, y1)
            x2_c, y2_c = min(w, x2), min(h, y2)

            crop_full = frame[y1_c:y2_c, x1_c:x2_c]
            if crop_full.size == 0:
                return None

            best_match = None
            best_sim = -1.0

            # 1. Probar Crop Completo
            emb_full = self.extract_embedding(crop_full)
            if emb_full is not None:
                match_full = symbol_db.match_symbol(emb_full, threshold=threshold)
                if match_full and match_full["similarity"] > best_sim:
                    best_sim = match_full["similarity"]
                    best_match = match_full

            # 2. Probar Sub-Región Torso / Pecho (donde se ubican rangos e insignias militares)
            bh = y2_c - y1_c
            if bh > 40:
                y1_chest = y1_c + int(bh * 0.15)
                y2_chest = y1_c + int(bh * 0.60)
                crop_chest = frame[y1_chest:y2_chest, x1_c:x2_c]
                emb_chest = self.extract_embedding(crop_chest)
                if emb_chest is not None:
                    match_chest = symbol_db.match_symbol(emb_chest, threshold=threshold)
                    if match_chest and match_chest["similarity"] > best_sim:
                        best_sim = match_chest["similarity"]
                        best_match = match_chest

            return best_match

        except Exception as e:
            logger.error(f"Error procesando reconocimiento de símbolo en bbox: {e}")

        return None

symbol_recognizer = SymbolRecognizer()
