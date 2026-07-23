import pytest
import numpy as np
from app.core.auto_framing import AutoFramingEngine

def test_ema_smoothing_calculation():
    """Verifica que las ecuaciones del filtro EMA suavicen progresivamente las coordenadas del centro."""
    engine = AutoFramingEngine(ema_alpha=0.2, padding=0.2, aspect_ratio="16:9")
    
    # Simular secuencia de detecciones para un objeto moviéndose hacia la derecha
    frame_h, frame_w = 720, 1280
    frame = np.zeros((frame_h, frame_w, 3), dtype=np.uint8)

    # Frame 1: Objeto en cx=100
    obj1 = [{"track_id": 1, "class_name": "person", "bbox": [50, 200, 150, 400]}] # cx=100
    _, _, telemetry1 = engine.process_frame(frame, obj1, draw_overlay=False)
    
    assert engine.smooth_cx == 100.0
    assert engine.smooth_cy == 300.0

    # Frame 2: Objeto se mueve bruscamente a cx=200
    obj2 = [{"track_id": 1, "class_name": "person", "bbox": [150, 200, 250, 400]}] # cx=200
    _, _, telemetry2 = engine.process_frame(frame, obj2, draw_overlay=False)

    # Con alpha = 0.2: smooth_cx = 0.2 * 200 + 0.8 * 100 = 40 + 80 = 120.0
    assert pytest.approx(engine.smooth_cx, 0.1) == 120.0

def test_aspect_ratio_cropping_bounds():
    """Verifica que el Crop Box resultante respete los límites de la imagen original."""
    engine = AutoFramingEngine(ema_alpha=0.5, padding=0.1, aspect_ratio="16:9")
    frame_h, frame_w = 720, 1280
    frame = np.zeros((frame_h, frame_w, 3), dtype=np.uint8)

    # Objeto cerca de la esquina superior izquierda (x1=0, y1=0)
    obj = [{"track_id": 5, "class_name": "person", "bbox": [0, 0, 100, 200]}]
    _, _, telemetry = engine.process_frame(frame, obj, draw_overlay=False)
    
    crop_x1, crop_y1, crop_x2, crop_y2 = telemetry["crop_box"]

    assert crop_x1 >= 0
    assert crop_y1 >= 0
    assert crop_x2 <= frame_w
    assert crop_y2 <= frame_h
