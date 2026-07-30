import cv2
import time
import logging
import numpy as np
from typing import Optional, List
import base64
from datetime import datetime
from collections import deque
from fastapi import APIRouter, Query, HTTPException, File, UploadFile, Response
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.video_stream import VideoStreamReader
from app.core.detector import OpenVINODetector
from app.core.auto_framing import AutoFramingEngine
from app.core.face_db import face_db
from app.core.face_recognizer import face_recognizer
from app.core.symbol_db import symbol_db
from app.core.symbol_recognizer import symbol_recognizer

logger = logging.getLogger("APIRoutes")

# Cache para evitar bloqueos repetitivos por reconocimiento facial y de símbolos
face_recognition_cache = {}
symbol_recognition_cache = {}

# Registro de Eventos (Capturas)
event_logs = deque(maxlen=10)
logged_track_ids = set()
last_logged_times = {}

router = APIRouter()

# Instancias singleton del pipeline
video_reader = VideoStreamReader(source=settings.VIDEO_SOURCE, target_fps=settings.MAX_FPS)
video_reader.start()

detector = OpenVINODetector()
framing_engine = AutoFramingEngine()

# Estado global de telemetría y FPS
pipeline_stats = {
    "fps": 0.0,
    "inference_latency_ms": 0.0,
    "frame_count": 0,
    "last_telemetry": {}
}

CATEGORY_MAP = {
    "ALL": None,                       # Todas las clases del modelo activo
    "PERSON": [0, 5, 6],               # Personas (COCO ID 0, Militar IDs 0, 5, 6)
    "OBJECTS": list(range(1, 80)),     # Todos los objetos inanimados
    "SYMBOLS": None                    # Modo dedicado a Insignias, Rangos y Logos
}

class SettingsUpdateModel(BaseModel):
    ema_alpha: Optional[float] = Field(None, ge=0.01, le=1.0, description="Factor de suavizado EMA")
    padding: Optional[float] = Field(None, ge=0.0, le=1.0, description="Porcentaje de padding alrededor del objeto")
    aspect_ratio: Optional[str] = Field(None, description="Relación de aspecto: '16:9', '9:16', '1:1', 'FREE'")
    target_id: Optional[int] = Field(None, description="ID del objeto a seguir (-1 para selección automática)")
    target_category: Optional[str] = Field(None, description="Categoría a buscar: ALL, SCISSORS, PERSON, etc.")
    draw_overlays: Optional[bool] = Field(None, description="Mostrar/Ocultar overlays en la vista previa")
    detection_paused: Optional[bool] = Field(None, description="Pausar la inferencia de IA para ahorrar CPU")
    active_model: Optional[str] = Field(None, description="Modelo de visión: 'STANDARD' o 'MILITARY'")

@router.get("/health")
async def health_check():
    """Endpoint de estado del servicio e inspección de aceleración OpenVINO."""
    return {
        "status": "healthy",
        "app_title": settings.APP_TITLE,
        "version": settings.APP_VERSION,
        "openvino_device": detector.device,
        "is_synthetic_mode": detector.is_synthetic_mode,
        "video_source": str(settings.VIDEO_SOURCE),
        "active_model_path": settings.MODEL_PATH
    }

@router.post("/api/settings")
async def update_settings(payload: SettingsUpdateModel):
    """Actualiza la configuración de suavizado, padding y selección de objeto en tiempo real."""
    framing_engine.set_parameters(
        ema_alpha=payload.ema_alpha,
        padding=payload.padding,
        aspect_ratio=payload.aspect_ratio,
        target_id=payload.target_id
    )
    if payload.draw_overlays is not None:
        settings.DRAW_OVERLAYS = payload.draw_overlays
    if payload.target_category is not None:
        cat_upper = payload.target_category.upper()
        settings.TARGET_CLASSES = CATEGORY_MAP.get(cat_upper, None)
        settings.ENABLE_SYMBOL_RECOGNITION = (cat_upper == "SYMBOLS")
        symbol_recognition_cache.clear()
    if payload.detection_paused is not None:
        settings.DETECTION_PAUSED = payload.detection_paused
    if payload.active_model is not None:
        new_path = "models/military_openvino_model" if payload.active_model.upper() == "MILITARY" else "models/yolov8n_openvino_model"
        if settings.MODEL_PATH != new_path:
            detector.reload_model(new_path)
            face_recognition_cache.clear()

    return {
        "status": "success",
        "message": "Parámetros del motor de auto-framing actualizados en caliente",
        "current_parameters": {
            "ema_alpha": framing_engine.ema_alpha,
            "padding": framing_engine.padding,
            "aspect_ratio": framing_engine.aspect_ratio,
            "target_id": framing_engine.target_id,
            "draw_overlays": settings.DRAW_OVERLAYS,
            "detection_paused": settings.DETECTION_PAUSED
        }
    }

@router.get("/api/status")
async def get_status():
    """Obtiene la telemetría en tiempo real del pipeline de visión por computadora."""
    return {
        "fps": round(pipeline_stats["fps"], 1),
        "inference_latency_ms": round(pipeline_stats["inference_latency_ms"], 1),
        "frame_count": pipeline_stats["frame_count"],
        "openvino_device": detector.device,
        "detection_paused": settings.DETECTION_PAUSED,
        "engine_parameters": {
            "ema_alpha": framing_engine.ema_alpha,
            "padding": framing_engine.padding,
            "aspect_ratio": framing_engine.aspect_ratio,
            "target_id": framing_engine.target_id
        },
        "telemetry": pipeline_stats["last_telemetry"]
    }

@router.get("/api/logs")
async def get_logs():
    """Devuelve los últimos 10 eventos/capturas registrados en Base64."""
    return list(event_logs)

@router.delete("/api/logs/{log_index}")
async def delete_log(log_index: int):
    """Elimina una captura específica del registro de eventos en memoria (Modo Pruebas)."""
    if 0 <= log_index < len(event_logs):
        del event_logs[log_index]
        return {"status": "success", "message": f"Captura #{log_index} eliminada."}
    raise HTTPException(status_code=404, detail="Índice de captura no encontrado")

@router.delete("/api/logs")
async def clear_all_logs():
    """Vacía todo el historial del registro de capturas en memoria (Modo Pruebas)."""
    event_logs.clear()
    logged_track_ids.clear()
    last_logged_times.clear()
    return {"status": "success", "message": "Historial de capturas vaciado."}

def _log_person_capture(t_id: int, frame: np.ndarray, bbox: List[float], match_info: dict):
    now = time.time()
    name = match_info.get("name", "Desconocido")
    
    # Cooldown inteligente para evitar spamear capturas de la misma persona
    cooldown = 30.0 if name != "Desconocido" else 15.0
    if (now - last_logged_times.get(name, 0.0)) < cooldown:
        return

    if t_id not in logged_track_ids:
        logged_track_ids.add(t_id)
        last_logged_times[name] = now
        try:
            # Crear copia del fotograma a tamaño completo para el registro
            full_snapshot = frame.copy()
            x1, y1, x2, y2 = [int(c) for c in bbox]
            
            status_role = match_info.get("role", "No Registrado")
            color = (0, 255, 120) if status_role != "No Registrado" else (0, 0, 255)
            cv2.rectangle(full_snapshot, (x1, y1), (x2, y2), color, 2)
            label = f"{name} ({status_role})"
            cv2.putText(full_snapshot, label, (x1, max(25, y1 - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2, cv2.LINE_AA)

            # Redimensionar el fotograma completo a resolución óptima (640x360)
            h, w = full_snapshot.shape[:2]
            target_w = 640
            target_h = int(target_w * (h / float(w)))
            full_resized = cv2.resize(full_snapshot, (target_w, target_h), interpolation=cv2.INTER_AREA)

            _, buffer = cv2.imencode(".jpg", full_resized, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
            b64_img = base64.b64encode(buffer).decode("utf-8")
            event_logs.appendleft({
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "track_id": t_id,
                "name": name,
                "status": status_role,
                "image": f"data:image/jpeg;base64,{b64_img}"
            })
        except Exception as e:
            logger.error(f"Error generando captura a tamaño completo para log: {e}")

def generate_mjpeg_stream(mode: str = "framed"):
    """
    Generador asíncrono de fotogramas MJPEG para streaming HTTP.
    Modos soportados:
    - 'framed': Flujo recortado y suavizado centrado en el sujeto.
    - 'annotated': Flujo original completo con cajas de seguimiento y encuadre.
    - 'dual': Vista dividida (Lado a lado: Original vs Auto-Framed).
    """
    last_frame_time = time.time()

    while True:
        try:
            ret, frame = video_reader.read()
            if not ret or frame is None:
                time.sleep(0.01)
                continue

            if settings.DETECTION_PAUSED:
                tracked_objects = []
                infer_latency = 0.0
            else:
                start_infer = time.time()
                # 1. Detección y Tracking ByteTrack en OpenVINO
                tracked_objects = detector.detect_and_track(frame, conf=settings.CONFIDENCE_THRESHOLD)
                infer_latency = (time.time() - start_infer) * 1000.0

                # 1.5 Reconocimiento Facial Biométrico en Sujetos (Personas / Soldados / Civiles)
                for obj in tracked_objects:
                    c_id = obj.get("class_id")
                    c_name = str(obj.get("class_name", "")).lower()
                    if c_id in [0, 5, 6] or any(p in c_name for p in ["person", "soldier", "soldado", "civil"]):
                        t_id = obj.get("track_id")
                        if t_id is not None:
                            # Intentar reconocer la cara mientras no esté identificada
                            if face_recognition_cache.get(t_id) is None:
                                match_info = face_recognizer.recognize_face_in_bbox(frame, obj["bbox"])
                                if match_info:
                                    face_recognition_cache[t_id] = match_info
                            
                            if face_recognition_cache.get(t_id):
                                match_info = face_recognition_cache[t_id]
                                obj["face_identity"] = match_info
                                _log_person_capture(t_id, frame, obj["bbox"], match_info)
                    
                    # Reconocimiento de Símbolos, Insignias y Logos (Solo si la categoría es SYMBOLS)
                    if settings.ENABLE_SYMBOL_RECOGNITION:
                        t_id = obj.get("track_id")
                        if t_id is not None:
                            if symbol_recognition_cache.get(t_id) is None:
                                sym_match = symbol_recognizer.recognize_symbol_in_bbox(frame, obj["bbox"])
                                if sym_match:
                                    symbol_recognition_cache[t_id] = sym_match
                            if symbol_recognition_cache.get(t_id):
                                obj["symbol_identity"] = symbol_recognition_cache[t_id]

            # 2. Motor de Auto-Framing y Suavizado EMA
            auto_framed_output, annotated_frame, telemetry = framing_engine.process_frame(
                frame, tracked_objects, draw_overlay=settings.DRAW_OVERLAYS
            )

            # Actualizar telemetría global
            now = time.time()
            dt = now - last_frame_time
            last_frame_time = now
            fps = 1.0 / dt if dt > 0 else 0.0

            pipeline_stats["fps"] = fps
            pipeline_stats["inference_latency_ms"] = infer_latency
            pipeline_stats["frame_count"] += 1
            pipeline_stats["last_telemetry"] = telemetry

            # 3. Selección de fotograma a transmitir
            if mode == "annotated":
                output_image = annotated_frame
            elif mode == "dual":
                # Redimensionar ambas imágenes para concatenación horizontal
                h1, w1 = annotated_frame.shape[:2]
                h2, w2 = auto_framed_output.shape[:2]
                target_h = 540
                w1_res = int(w1 * (target_h / float(h1)))
                w2_res = int(w2 * (target_h / float(h2)))
                
                img1 = cv2.resize(annotated_frame, (w1_res, target_h))
                img2 = cv2.resize(auto_framed_output, (w2_res, target_h))
                output_image = cv2.hconcat([img1, img2])
            else: # 'framed'
                output_image = auto_framed_output

            # 4. Codificar a JPEG
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 85]
            success, jpeg_buffer = cv2.imencode(".jpg", output_image, encode_param)
            if not success:
                continue

            frame_bytes = jpeg_buffer.tobytes()

            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        except Exception as e:
            logger.error(f"Error procesando frame en el stream MJPEG: {e}", exc_info=True)
            time.sleep(0.1)

@router.post("/api/webcam_frame")
async def receive_webcam_frame(file: UploadFile = File(...)):
    """
    Recibe un fotograma de la webcam del navegador y lo inyecta en el motor de video en tiempo real.
    """
    contents = await file.read()
    nparr = np.frombuffer(contents, np.uint8)
    if nparr.size > 0:
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if frame is not None:
            video_reader.push_frame(frame)
    return {"status": "ok"}

@router.post("/api/process_frame")
async def process_frame(
    file: UploadFile = File(...),
    mode: str = Query("framed"),
    padding: Optional[float] = None,
    ema_alpha: Optional[float] = None,
    target_id: Optional[int] = None,
    target_category: Optional[str] = Query("ALL"),
    aspect_ratio: Optional[str] = None
):
    """
    Recibe un fotograma capturado directamente de la webcam del navegador web,
    ejecuta inferencia OpenVINO + ByteTrack + Auto-Framing y retorna la imagen procesada en tiempo real.
    """
    if padding is not None or ema_alpha is not None or target_id is not None or aspect_ratio is not None:
        framing_engine.set_parameters(
            ema_alpha=ema_alpha,
            padding=padding,
            aspect_ratio=aspect_ratio,
            target_id=target_id
        )

    contents = await file.read()
    nparr = np.frombuffer(contents, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR) if nparr.size > 0 else None

    if frame is None:
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        cv2.putText(frame, "Procesando camara de navegacion...", (100, 360), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 180), 2)

    start_infer = time.time()
    target_classes = CATEGORY_MAP.get((target_category or "ALL").upper(), None)
    tracked_objects = detector.detect_and_track(frame, conf=settings.CONFIDENCE_THRESHOLD, classes=target_classes)
    infer_latency = (time.time() - start_infer) * 1000.0

    # 1.5 Reconocimiento Facial Biométrico en Sujetos (Personas / Soldados / Civiles)
    for obj in tracked_objects:
        c_id = obj.get("class_id")
        c_name = str(obj.get("class_name", "")).lower()
        if c_id in [0, 5, 6] or any(p in c_name for p in ["person", "soldier", "soldado", "civil"]):
            t_id = obj.get("track_id")
            if t_id is not None:
                if face_recognition_cache.get(t_id) is None:
                    match_info = face_recognizer.recognize_face_in_bbox(frame, obj["bbox"])
                    if match_info:
                        face_recognition_cache[t_id] = match_info
                
                if face_recognition_cache.get(t_id):
                    match_info = face_recognition_cache[t_id]
                    obj["face_identity"] = match_info
                    _log_person_capture(t_id, frame, obj["bbox"], match_info)

        # Reconocimiento de Símbolos en process_frame (Solo si la categoría es SYMBOLS)
        if settings.ENABLE_SYMBOL_RECOGNITION:
            t_id = obj.get("track_id")
            if t_id is not None:
                if symbol_recognition_cache.get(t_id) is None:
                    sym_match = symbol_recognizer.recognize_symbol_in_bbox(frame, obj["bbox"])
                    if sym_match:
                        symbol_recognition_cache[t_id] = sym_match
                if symbol_recognition_cache.get(t_id):
                    obj["symbol_identity"] = symbol_recognition_cache[t_id]

    auto_framed_output, annotated_frame, telemetry = framing_engine.process_frame(
        frame, tracked_objects, draw_overlay=settings.DRAW_OVERLAYS
    )

    if mode == "annotated":
        output_image = annotated_frame
    elif mode == "dual":
        h1, w1 = annotated_frame.shape[:2]
        h2, w2 = auto_framed_output.shape[:2]
        target_h = 540
        w1_res = int(w1 * (target_h / float(h1)))
        w2_res = int(w2 * (target_h / float(h2)))
        img1 = cv2.resize(annotated_frame, (w1_res, target_h))
        img2 = cv2.resize(auto_framed_output, (w2_res, target_h))
        output_image = cv2.hconcat([img1, img2])
    else:
        output_image = auto_framed_output

    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 85]
    success, jpeg_buffer = cv2.imencode(".jpg", output_image, encode_param)
    if not success:
        raise HTTPException(status_code=500, detail="Error codificando imagen JPEG")

    pipeline_stats["inference_latency_ms"] = infer_latency
    pipeline_stats["frame_count"] += 1
    pipeline_stats["last_telemetry"] = telemetry

    return Response(content=jpeg_buffer.tobytes(), media_type="image/jpeg")

@router.get("/video_feed")
async def video_feed(mode: str = Query("framed", description="Modo de transmisión: 'framed', 'annotated', o 'dual'"),
                     padding: Optional[float] = None,
                     ema_alpha: Optional[float] = None,
                     target_id: Optional[int] = None,
                     aspect_ratio: Optional[str] = None):
    """
    Endpoint de streaming MJPEG de alta velocidad para transmisión de video recortado en vivo.
    """
    if padding is not None or ema_alpha is not None or target_id is not None or aspect_ratio is not None:
        framing_engine.set_parameters(
            ema_alpha=ema_alpha,
            padding=padding,
            aspect_ratio=aspect_ratio,
            target_id=target_id
        )

    return StreamingResponse(
        generate_mjpeg_stream(mode=mode),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

class EnrollB64Model(BaseModel):
    name: str
    dni: str
    role: Optional[str] = "Usuario"
    image_b64: str

@router.post("/api/faces/enroll_b64")
async def enroll_face_b64(payload: EnrollB64Model):
    """
    Registra a una persona desde una captura en Base64 extrayendo su vector facial de 128-D.
    """
    try:
        b64_data = payload.image_b64
        if "," in b64_data:
            b64_data = b64_data.split(",")[1]
        
        img_bytes = base64.b64decode(b64_data)
        nparr = np.frombuffer(img_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if frame is None:
            raise HTTPException(status_code=400, detail="Imagen Base64 no válida")

        embedding = face_recognizer.extract_embedding(frame)
        if embedding is None:
            raise HTTPException(status_code=422, detail="No se detectó un rostro nítido en la captura para extraer la huella biométrica.")

        success = face_db.register_person(name=payload.name, dni=payload.dni, role=payload.role, embedding=embedding)
        if not success:
            raise HTTPException(status_code=500, detail="Error guardando en la base de datos (DNI posiblemente duplicado).")

        # Limpiar la caché para que el rastreador identifique a la persona inmediatamente
        face_recognition_cache.clear()

        # Actualizar logs en memoria con la nueva identidad
        for log_entry in event_logs:
            if log_entry.get("status") == "No Registrado" or log_entry.get("name") == "Desconocido":
                log_entry["name"] = payload.name
                log_entry["status"] = payload.role

        return {
            "status": "success",
            "message": f"Persona '{payload.name}' (DNI: {payload.dni}) enrolada exitosamente desde la captura.",
            "person": {"name": payload.name, "dni": payload.dni, "role": payload.role}
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error enrolando desde Base64: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/faces/enroll")
async def enroll_face(
    name: str = Query(..., description="Nombre completo de la persona"),
    dni: str = Query(..., description="DNI o Identificador único"),
    role: Optional[str] = Query("Usuario", description="Rol o categoría (ej. Empleado, VIP)"),
    file: UploadFile = File(...)
):
    """
    Registra a una persona en la Base de Datos Biométrica extrayendo su vector facial de 128-D.
    """
    contents = await file.read()
    nparr = np.frombuffer(contents, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if frame is None:
        raise HTTPException(status_code=400, detail="Imagen no válida")

    embedding = face_recognizer.extract_embedding(frame)
    if embedding is None:
        raise HTTPException(status_code=422, detail="No se detectó ningún rostro claro en la imagen enviada. Intenta de nuevo frente a la cámara.")

    success = face_db.register_person(name=name, dni=dni, role=role, embedding=embedding)
    if not success:
        raise HTTPException(status_code=500, detail="Error guardando persona en la base de datos (DNI duplicado o error de BD)")

    # Limpiar caché de reconocimiento facial y de cooldowns para identificación inmediata sin recargar
    face_recognition_cache.clear()
    last_logged_times.clear()

    return {
        "status": "success",
        "message": f"Persona '{name}' (DNI: {dni}) enrolada exitosamente.",
        "person": {"name": name, "dni": dni, "role": role}
    }

@router.get("/api/faces/list")
async def list_faces():
    """
    Retorna la lista de todas las personas enroladas en la Base de Datos Biométrica.
    """
    return {"persons": face_db.get_all_persons()}

@router.delete("/api/faces/{person_id}")
async def delete_face(person_id: int):
    """
    Elimina a una persona enrolada de la Base de Datos por su ID.
    """
    success = face_db.delete_person(person_id)
    if not success:
        raise HTTPException(status_code=404, detail="Persona no encontrada o error al eliminar")
    face_recognition_cache.clear()
    last_logged_times.clear()
    return {"status": "success", "message": f"Persona ID {person_id} eliminada."}

@router.post("/api/symbols/enroll")
async def enroll_symbol(
    name: str = Query(..., description="Nombre del símbolo, insignia o rango (ej. 'Capitán', 'Logo Ford')"),
    category: Optional[str] = Query("Insignia", description="Categoría (ej. Rango Militar, Marca, Escudo)"),
    description: Optional[str] = Query("", description="Descripción opcional"),
    file: UploadFile = File(...)
):
    """
    Registra un nuevo símbolo o insignia en la Base de Datos extrayendo su huella digital visual.
    """
    contents = await file.read()
    nparr = np.frombuffer(contents, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if frame is None:
        raise HTTPException(status_code=400, detail="Imagen de símbolo no válida")

    embedding = symbol_recognizer.extract_embedding(frame)
    if embedding is None:
        raise HTTPException(status_code=422, detail="No se pudo extraer la huella visual de la imagen enviada.")

    success = symbol_db.register_symbol(name=name, category=category, description=description, embedding=embedding)
    if not success:
        raise HTTPException(status_code=500, detail="Error guardando el símbolo en la base de datos.")

    return {
        "status": "success",
        "message": f"Símbolo '{name}' ({category}) registrado exitosamente.",
        "symbol": {"name": name, "category": category, "description": description}
    }

@router.get("/api/symbols/list")
async def list_symbols():
    """
    Retorna la lista de todos los símbolos e insignias enrolados en la Base de Datos.
    """
    return {"symbols": symbol_db.get_all_symbols()}

@router.delete("/api/symbols/{symbol_id}")
async def delete_symbol(symbol_id: int):
    """
    Elimina un símbolo enrolado de la Base de Datos por su ID.
    """
    success = symbol_db.delete_symbol(symbol_id)
    if not success:
        raise HTTPException(status_code=404, detail="Símbolo no encontrado o error al eliminar")
    return {"status": "success", "message": f"Símbolo ID {symbol_id} eliminado."}

