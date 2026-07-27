import cv2
import numpy as np
import logging
from typing import Dict, Any, List, Tuple, Optional
from app.core.config import settings

logger = logging.getLogger("AutoFramingEngine")

class AutoFramingEngine:
    """
    Motor de Encuadre Dinámico Centrado en el Sujeto con Suavizado Exponencial (EMA).
    Calcula el recorte óptimo (Crop) para mantener al sujeto en el centro del encuadre
    con movimientos de cámara suaves y estables.
    """

    def __init__(self,
                 ema_alpha: float = settings.DEFAULT_EMA_ALPHA,
                 padding: float = settings.DEFAULT_PADDING,
                 aspect_ratio: str = settings.DEFAULT_ASPECT_RATIO,
                 target_id: Optional[int] = settings.TARGET_OBJECT_ID):
        
        self.ema_alpha = ema_alpha
        self.padding = padding
        self.aspect_ratio = aspect_ratio
        self.target_id = target_id

        # Estado interno del suavizado EMA (None cuando no hay objetivo)
        self.smooth_cx: Optional[float] = None
        self.smooth_cy: Optional[float] = None
        self.smooth_w: Optional[float] = None
        self.smooth_h: Optional[float] = None

        self.last_active_target_id: Optional[int] = None
        self.lost_frames_count: int = 0
        self.max_lost_frames: int = 15  # Retener la posición 15 cuadros antes de reiniciar

    def set_parameters(self, ema_alpha: Optional[float] = None,
                       padding: Optional[float] = None,
                       aspect_ratio: Optional[str] = None,
                       target_id: Optional[int] = None):
        """Actualización en vivo de los parámetros del motor."""
        if ema_alpha is not None:
            self.ema_alpha = max(0.01, min(1.0, float(ema_alpha)))
        if padding is not None:
            self.padding = max(0.0, min(1.0, float(padding)))
        if aspect_ratio is not None:
            self.aspect_ratio = str(aspect_ratio).upper()
        if target_id is not None:
            # -1 o 0 se interpreta como selección automática
            self.target_id = None if target_id in [-1, 0, None] else int(target_id)
            if self.target_id != self.last_active_target_id:
                # Reiniciar el estado de suavizado al cambiar de objetivo manualmente
                self._reset_smoothing()

    def _reset_smoothing(self):
        self.smooth_cx = None
        self.smooth_cy = None
        self.smooth_w = None
        self.smooth_h = None

    def _parse_aspect_ratio(self, ratio_str: str) -> Optional[float]:
        if ratio_str == "16:9":
            return 16.0 / 9.0
        elif ratio_str == "9:16":
            return 9.0 / 16.0
        elif ratio_str == "1:1":
            return 1.0
        return None  # Modo FREE

    def select_target(self, tracked_objects: List[Dict[str, Any]], frame_shape: Tuple[int, int]) -> Optional[Dict[str, Any]]:
        """
        Selecciona el objetivo según la preferencia del usuario o por dominancia/cercanía al centro.
        """
        if not tracked_objects:
            return None

        # Si hay un ID objetivo especificado manualmente, buscarlo
        if self.target_id is not None:
            for obj in tracked_objects:
                if obj.get("track_id") == self.target_id:
                    return obj

        # Selección automática: Buscar el objeto más cercano al centro con mayor área
        frame_h, frame_w = frame_shape[:2]
        center_x, center_y = frame_w / 2.0, frame_h / 2.0

        best_obj = None
        best_score = -float('inf')

        for obj in tracked_objects:
            bbox = obj.get("bbox", [])
            if len(bbox) != 4:
                continue
            x1, y1, x2, y2 = bbox
            obj_cx = (x1 + x2) / 2.0
            obj_cy = (y1 + y2) / 2.0
            area = (x2 - x1) * (y2 - y1)

            # Distancia euclidiana normalizada al centro
            dist = np.sqrt(((obj_cx - center_x) / frame_w) ** 2 + ((obj_cy - center_y) / frame_h) ** 2)
            
            # Puntuación combinación de área y cercanía al centro
            score = area / (dist + 0.1)

            if score > best_score:
                best_score = score
                best_obj = obj

        return best_obj

    def process_frame(self, frame: np.ndarray, tracked_objects: List[Dict[str, Any]], draw_overlay: bool = True) -> Tuple[np.ndarray, np.ndarray, Dict[str, Any]]:
        """
        Procesa el fotograma actual:
        1. Selecciona o actualiza el objeto objetivo.
        2. Aplica filtro EMA sobre (cx, cy, w, h).
        3. Calcula el recuadro de recorte (Crop Box) ajustado a la relación de aspecto.
        4. Genera el frame recortado (Auto-Framed) y el frame de previsualización anotado.
        """
        frame_h, frame_w = frame.shape[:2]
        target_obj = self.select_target(tracked_objects, (frame_h, frame_w))

        if target_obj is not None:
            self.lost_frames_count = 0
            self.last_active_target_id = target_obj.get("track_id")
            x1, y1, x2, y2 = target_obj["bbox"]
            raw_cx = (x1 + x2) / 2.0
            raw_cy = (y1 + y2) / 2.0
            raw_w = x2 - x1
            raw_h = y2 - y1

            # Inicialización o actualización por Media Móvil Exponencial (EMA)
            if self.smooth_cx is None:
                self.smooth_cx = raw_cx
                self.smooth_cy = raw_cy
                self.smooth_w = raw_w
                self.smooth_h = raw_h
            else:
                alpha = self.ema_alpha
                self.smooth_cx = alpha * raw_cx + (1.0 - alpha) * self.smooth_cx
                self.smooth_cy = alpha * raw_cy + (1.0 - alpha) * self.smooth_cy
                self.smooth_w = alpha * raw_w + (1.0 - alpha) * self.smooth_w
                self.smooth_h = alpha * raw_h + (1.0 - alpha) * self.smooth_h
        else:
            self.lost_frames_count += 1
            if self.lost_frames_count > self.max_lost_frames:
                # Si se perdió el objetivo por más de max_lost_frames, volver suavemente al centro del video
                if self.smooth_cx is not None:
                    alpha = 0.05
                    self.smooth_cx = alpha * (frame_w / 2.0) + (1.0 - alpha) * self.smooth_cx
                    self.smooth_cy = alpha * (frame_h / 2.0) + (1.0 - alpha) * self.smooth_cy
                    self.smooth_w = alpha * (frame_w * 0.5) + (1.0 - alpha) * self.smooth_w
                    self.smooth_h = alpha * (frame_h * 0.5) + (1.0 - alpha) * self.smooth_h
                else:
                    self.smooth_cx = frame_w / 2.0
                    self.smooth_cy = frame_h / 2.0
                    self.smooth_w = frame_w * 0.5
                    self.smooth_h = frame_h * 0.5

        # 3. Aplicar Padding a las dimensiones del sujeto
        padded_w = self.smooth_w * (1.0 + self.padding)
        padded_h = self.smooth_h * (1.0 + self.padding)

        # 4. Ajuste por Relación de Aspecto Target
        target_ratio = self._parse_aspect_ratio(self.aspect_ratio)
        if target_ratio is not None:
            current_ratio = padded_w / max(1.0, padded_h)
            if current_ratio < target_ratio:
                # Expandir ancho para cumplir con la relación de aspecto
                padded_w = padded_h * target_ratio
            else:
                # Expandir alto para cumplir con la relación de aspecto
                padded_h = padded_w / target_ratio

        # Asegurar tamaño mínimo razonable para evitar encuadre distorsionado
        padded_w = max(padded_w, frame_w * 0.2)
        padded_h = max(padded_h, frame_h * 0.2)

        # 5. Calcuar coordenadas del Crop Box centrado en (smooth_cx, smooth_cy)
        crop_x1 = int(round(self.smooth_cx - padded_w / 2.0))
        crop_y1 = int(round(self.smooth_cy - padded_h / 2.0))
        crop_x2 = int(round(self.smooth_cx + padded_w / 2.0))
        crop_y2 = int(round(self.smooth_cy + padded_h / 2.0))

        # 6. Restricciones de Límites (Clamp to Boundary)
        # Si el recuadro se sale de los bordes del video, desplazar sin cambiar tamaño si es posible
        if crop_x1 < 0:
            crop_x2 = min(frame_w, crop_x2 - crop_x1)
            crop_x1 = 0
        if crop_y1 < 0:
            crop_y2 = min(frame_h, crop_y2 - crop_y1)
            crop_y1 = 0
        if crop_x2 > frame_w:
            crop_x1 = max(0, crop_x1 - (crop_x2 - frame_w))
            crop_x2 = frame_w
        if crop_y2 > frame_h:
            crop_y1 = max(0, crop_y1 - (crop_y2 - frame_h))
            crop_y2 = frame_h

        # Recorte de la imagen
        cropped_frame = frame[crop_y1:crop_y2, crop_x1:crop_x2]
        if cropped_frame.size == 0:
            cropped_frame = frame.copy()

        # Redimensionar salida a resolución estándar (ej. 1280x720 o manteniendo relación)
        out_w = settings.OUTPUT_WIDTH
        out_h = int(out_w / target_ratio) if target_ratio else settings.OUTPUT_HEIGHT
        auto_framed_output = cv2.resize(cropped_frame, (out_w, out_h), interpolation=cv2.INTER_LINEAR)

        # 7. Renderizar Overlays Informativos en el Frame Original y en el Encuadre
        annotated_frame = frame.copy()
        if draw_overlay:
            self._render_overlays(annotated_frame, tracked_objects, target_obj, (crop_x1, crop_y1, crop_x2, crop_y2))
            
            # Dibujar la retícula del centroide y etiqueta sobre el encuadre recortado (auto_framed_output)
            out_center_x, out_center_y = out_w // 2, out_h // 2
            cv2.drawMarker(auto_framed_output, (out_center_x, out_center_y), (0, 255, 180), cv2.MARKER_CROSS, 24, 2)
            if target_obj:
                face_id = target_obj.get("face_identity")
                if face_id:
                    tgt_label = f"IDENTIFICADO: {face_id['name']} ({face_id['similarity']}%)"
                else:
                    tgt_label = f"TARGET ID:{target_obj.get('track_id')} ({target_obj.get('class_name')})"
                cv2.putText(auto_framed_output, tgt_label, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 180), 2)
            else:
                cv2.putText(auto_framed_output, f"AUTO-FRAME ({self.aspect_ratio})", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 230, 0), 2)

        telemetry = {
            "active_target_id": target_obj.get("track_id") if target_obj else self.last_active_target_id,
            "active_target_class": target_obj.get("class_name") if target_obj else "N/A",
            "smooth_center": [int(self.smooth_cx), int(self.smooth_cy)],
            "crop_box": [crop_x1, crop_y1, crop_x2, crop_y2],
            "padding_applied": self.padding,
            "ema_alpha_applied": self.ema_alpha,
            "aspect_ratio": self.aspect_ratio
        }

        return auto_framed_output, annotated_frame, telemetry

    def _render_overlays(self, frame: np.ndarray, tracked_objects: List[Dict[str, Any]],
                         target_obj: Optional[Dict[str, Any]], crop_box: Tuple[int, int, int, int]):
        """Renderiza bounding boxes de tracking y la retícula de auto-framing."""
        # Dibujar recuadro de Auto-Framing (Verde Neón / Cian)
        cx1, cy1, cx2, cy2 = crop_box
        cv2.rectangle(frame, (cx1, cy1), (cx2, cy2), (255, 230, 0), 2)
        cv2.putText(frame, f"AUTO-FRAME ({self.aspect_ratio})", (cx1 + 10, cy1 + 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 230, 0), 2)

        # Dibujar objetos rastreados
        for obj in tracked_objects:
            track_id = obj.get("track_id")
            cls_name = obj.get("class_name", "obj")
            face_id = obj.get("face_identity")
            x1, y1, x2, y2 = [int(c) for c in obj["bbox"]]
            is_target = (target_obj is not None) and (track_id == target_obj.get("track_id"))

            color = (0, 255, 0) if is_target else (180, 180, 180)
            thickness = 3 if is_target else 1

            # Si hay reconocimiento facial, cambiar color a Verde Neón o Azul y mostrar etiqueta biométrica
            if face_id:
                color = (0, 255, 120)  # Verde esmeralda para coincidencia
                label = f"ID:{track_id} {face_id['name']} ({face_id['similarity']}%)"
            else:
                label = f"ID:{track_id} {cls_name}" if track_id else f"{cls_name}"

            cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)
            
            # Fondo para etiqueta
            (w, h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(frame, (x1, y1 - 22), (x1 + w + 10, y1), color, -1)
            cv2.putText(frame, label, (x1 + 5, y1 - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)

        # Dibujar centroide suavizado
        if self.smooth_cx is not None and self.smooth_cy is not None:
            scx, scy = int(self.smooth_cx), int(self.smooth_cy)
            cv2.drawMarker(frame, (scx, scy), (0, 255, 255), cv2.MARKER_CROSS, 20, 2)
