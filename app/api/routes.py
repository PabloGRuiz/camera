import cv2
import time
import logging
import numpy as np
from typing import Optional, List
import base64
from datetime import datetime
from collections import deque
from fastapi import APIRouter, Query, HTTPException, File, UploadFile, Response, BackgroundTasks, Security, Depends
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel, Field
import httpx
import os
import asyncio

API_KEY = os.getenv("API_KEY", "super_secret_edge_key_2026")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def verify_api_key(api_key: str = Security(api_key_header)):
    if api_key != API_KEY:
        raise HTTPException(status_code=401, detail="No autorizado. Falta o es inválida la API Key.")
    return api_key

from app.core.config import settings
from app.core.detector import OpenVINODetector
from app.core.face_db import face_db
from app.core.face_recognizer import face_recognizer
from app.core.symbol_db import symbol_db
from app.core.symbol_recognizer import symbol_recognizer
from app.core.camera_manager import camera_manager

logger = logging.getLogger("APIRoutes")

face_recognition_cache = {}
symbol_recognition_cache = {}

event_logs = deque(maxlen=10)
logged_track_ids = set()
last_logged_times = {}

router = APIRouter()

detector = OpenVINODetector()

pipeline_stats = {
    "fps": 0.0,
    "inference_latency_ms": 0.0,
    "frame_count": 0,
    "last_telemetry": {}
}

CENTRAL_SERVER_URL = os.getenv("CENTRAL_SERVER_URL", "http://central_server:8082")

class SettingsUpdateModel(BaseModel):
    ema_alpha: Optional[float] = Field(None, ge=0.01, le=1.0)
    padding: Optional[float] = Field(None, ge=0.0, le=1.0)
    aspect_ratio: Optional[str] = Field(None)
    target_id: Optional[int] = Field(None)
    target_classes: Optional[List[int]] = Field(None)
    draw_overlays: Optional[bool] = Field(None)
    detection_paused: Optional[bool] = Field(None)
    active_model: Optional[str] = Field(None)
    max_fps: Optional[int] = Field(None)
    camera_id: Optional[str] = Field(None)

class CameraControlModel(BaseModel):
    action: str
    camera_id: str
    source: Optional[str] = None

@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "app_title": settings.APP_TITLE,
        "version": settings.APP_VERSION,
        "openvino_device": detector.device,
        "active_model_path": settings.MODEL_PATH,
        "active_cameras": camera_manager._camera_ids
    }

@router.post("/api/settings", dependencies=[Depends(verify_api_key)])
async def update_settings(payload: SettingsUpdateModel):
    target_engines = []
    if payload.camera_id and payload.camera_id in camera_manager.framing_engines:
        target_engines.append(camera_manager.get_framing_engine(payload.camera_id))
    else:
        target_engines = list(camera_manager.framing_engines.values())

    for framing_engine in target_engines:
        framing_engine.set_parameters(
            ema_alpha=payload.ema_alpha,
            padding=payload.padding,
            aspect_ratio=payload.aspect_ratio,
            target_id=payload.target_id
        )

    if payload.draw_overlays is not None:
        settings.DRAW_OVERLAYS = payload.draw_overlays
    if payload.target_classes is not None:
        if len(payload.target_classes) > 0 and payload.target_classes[0] == -1:
            settings.TARGET_CLASSES = None
        else:
            settings.TARGET_CLASSES = payload.target_classes
        detector.active_trackers.clear()
        settings.ENABLE_SYMBOL_RECOGNITION = False 
        symbol_recognition_cache.clear()
    if payload.detection_paused is not None:
        settings.DETECTION_PAUSED = payload.detection_paused
    if payload.active_model is not None:
        new_path = "models/military_assets_yolov8n_openvino_model" if payload.active_model.upper() == "MILITARY" else "models/yolov8n_openvino_model"
        if settings.MODEL_PATH != new_path:
            detector.reload_model(new_path)
            face_recognition_cache.clear()
    if payload.max_fps is not None:
        settings.MAX_FPS = payload.max_fps

    return {"status": "success"}

@router.post("/api/camera/control", dependencies=[Depends(verify_api_key)])
async def control_camera(payload: CameraControlModel):
    if payload.action == "add":
        if payload.source:
            camera_manager.add_camera(payload.camera_id, payload.source)
    elif payload.action == "remove":
        camera_manager.remove_camera(payload.camera_id)
    elif payload.action == "fix":
        camera_manager.fixed_camera_id = payload.camera_id if payload.camera_id in camera_manager.cameras else None
    return {"status": "success", "fixed_camera": camera_manager.fixed_camera_id, "cameras": camera_manager._camera_ids}

@router.get("/api/camera/list")
async def list_cameras():
    return {
        "cameras": camera_manager._camera_ids,
        "fixed_camera": camera_manager.fixed_camera_id,
        "active_inference_camera": camera_manager.get_active_inference_camera()
    }

@router.get("/api/status")
async def get_status():
    return {
        "fps": round(pipeline_stats["fps"], 1),
        "inference_latency_ms": round(pipeline_stats["inference_latency_ms"], 1),
        "frame_count": pipeline_stats["frame_count"],
        "openvino_device": detector.device,
        "detection_paused": settings.DETECTION_PAUSED,
        "telemetry": pipeline_stats["last_telemetry"],
        "active_cameras": camera_manager._camera_ids,
        "fixed_camera": camera_manager.fixed_camera_id,
        "active_inference": camera_manager.get_active_inference_camera()
    }

@router.get("/api/models")
async def get_models():
    return {
        "models": [
            {
                "id": "STANDARD",
                "name": "Standard COCO (80 Classes)",
                "classes": {
                    0: "person", 1: "bicycle", 2: "car", 3: "motorcycle", 4: "airplane", 
                    5: "bus", 6: "train", 7: "truck", 8: "boat", 9: "traffic light", 
                    10: "fire hydrant", 11: "stop sign", 12: "parking meter", 13: "bench", 14: "bird", 
                    15: "cat", 16: "dog", 17: "horse", 18: "sheep", 19: "cow", 
                    20: "elephant", 21: "bear", 22: "zebra", 23: "giraffe", 24: "backpack", 
                    25: "umbrella", 26: "handbag", 27: "tie", 28: "suitcase", 29: "frisbee", 
                    30: "skis", 31: "snowboard", 32: "sports ball", 33: "kite", 34: "baseball bat", 
                    35: "baseball glove", 36: "skateboard", 37: "surfboard", 38: "tennis racket", 39: "bottle", 
                    40: "wine glass", 41: "cup", 42: "fork", 43: "knife", 44: "spoon", 
                    45: "bowl", 46: "banana", 47: "apple", 48: "sandwich", 49: "orange", 
                    50: "broccoli", 51: "carrot", 52: "hot dog", 53: "pizza", 54: "donut", 
                    55: "cake", 56: "chair", 57: "couch", 58: "potted plant", 59: "bed", 
                    60: "dining table", 61: "toilet", 62: "tv", 63: "laptop", 64: "mouse", 
                    65: "remote", 66: "keyboard", 67: "cell phone", 68: "microwave", 69: "oven", 
                    70: "toaster", 71: "sink", 72: "refrigerator", 73: "book", 74: "clock", 
                    75: "vase", 76: "scissors", 77: "teddy bear", 78: "hair drier", 79: "toothbrush"
                }
            },
            {
                "id": "MILITARY",
                "name": "Military Arsenal & Troops (12 Classes)",
                "classes": {
                    0: "camouflage_soldier", 1: "weapon", 2: "military_tank", 3: "military_truck", 
                    4: "military_vehicle", 5: "civilian", 6: "soldier", 7: "civilian_vehicle", 
                    8: "military_artillery", 9: "trench", 10: "military_aircraft", 11: "military_warship"
                }
            }
        ]
    }

@router.get("/api/logs")
async def get_logs():
    return list(event_logs)

@router.delete("/api/logs/{log_index}")
async def delete_log(log_index: int):
    if 0 <= log_index < len(event_logs):
        del event_logs[log_index]
        return {"status": "success"}
    raise HTTPException(status_code=404)

@router.delete("/api/logs")
async def clear_all_logs():
    event_logs.clear()
    logged_track_ids.clear()
    last_logged_times.clear()
    return {"status": "success"}

import threading

def send_to_central_server_async(payload: dict):
    def _worker():
        try:
            url = f"{CENTRAL_SERVER_URL}/api/report_log"
            res = httpx.post(url, json=payload, timeout=5.0)
            logger.info(f"Reporte enviado al servidor central: {res.status_code}")
        except Exception as e:
            logger.error(f"Error enviando log al servidor central: {e}")

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()

def _log_person_capture(camera_id: str, t_id: int, frame: np.ndarray, bbox: List[float], match_info: dict):
    now = time.time()
    name = match_info.get("name", "Desconocido")
    status_role = match_info.get("role", "No Registrado")
    
    cooldown = 10.0 if name != "Desconocido" else 5.0
    cache_key = f"{camera_id}_{name}_{t_id}"
    if (now - last_logged_times.get(cache_key, 0.0)) < cooldown:
        return

    last_logged_times[cache_key] = now
    try:
        full_snapshot = frame.copy()
        x1, y1, x2, y2 = [int(c) for c in bbox]
        
        color = (0, 255, 120) if status_role != "No Registrado" else (0, 0, 255)
        cv2.rectangle(full_snapshot, (x1, y1), (x2, y2), color, 2)
        label = f"{name} ({status_role})"
        cv2.putText(full_snapshot, label, (x1, max(25, y1 - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2, cv2.LINE_AA)

        h, w = full_snapshot.shape[:2]
        target_w = 640
        target_h = int(target_w * (h / float(w)))
        full_resized = cv2.resize(full_snapshot, (target_w, target_h), interpolation=cv2.INTER_AREA)

        _, buffer = cv2.imencode(".jpg", full_resized, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
        b64_img = base64.b64encode(buffer).decode("utf-8")
        
        # Local log entry (retains local preview image)
        log_entry = {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "camera_id": camera_id,
            "track_id": t_id,
            "name": name,
            "status": status_role,
            "image": f"data:image/jpeg;base64,{b64_img}"
        }
        event_logs.appendleft(log_entry)
        
        # Send lightweight text log to central server via daemon thread
        send_to_central_server_async({
            "camera_id": camera_id,
            "person_name": name,
            "role": status_role,
            "event_type": "Persona"
        })
    except Exception as e:
        logger.error(f"Error generando captura: {e}")

def _log_vehicle_capture(camera_id: str, t_id: int, frame: np.ndarray, bbox: List[float], vehicle_type: str):
    now = time.time()
    vehicle_type_clean = vehicle_type.replace("_", " ").title()
    
    cooldown = 10.0
    cache_key = f"veh_{camera_id}_{vehicle_type_clean}_{t_id}"
    if (now - last_logged_times.get(cache_key, 0.0)) < cooldown:
        return

    last_logged_times[cache_key] = now
    try:
        full_snapshot = frame.copy()
        x1, y1, x2, y2 = [int(c) for c in bbox]
        
        color = (255, 180, 0)
        cv2.rectangle(full_snapshot, (x1, y1), (x2, y2), color, 2)
        label = f"Vehículo: {vehicle_type_clean}"
        cv2.putText(full_snapshot, label, (x1, max(25, y1 - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2, cv2.LINE_AA)

        h, w = full_snapshot.shape[:2]
        target_w = 640
        target_h = int(target_w * (h / float(w)))
        full_resized = cv2.resize(full_snapshot, (target_w, target_h), interpolation=cv2.INTER_AREA)

        _, buffer = cv2.imencode(".jpg", full_resized, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
        b64_img = base64.b64encode(buffer).decode("utf-8")
        
        log_entry = {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "camera_id": camera_id,
            "track_id": t_id,
            "name": f"Vehículo ({vehicle_type_clean})",
            "status": "Entrada Vehicular",
            "image": f"data:image/jpeg;base64,{b64_img}"
        }
        event_logs.appendleft(log_entry)
        
        # Send lightweight text log to central server via daemon thread
        send_to_central_server_async({
            "camera_id": camera_id,
            "person_name": f"Vehículo: {vehicle_type_clean}",
            "role": "Entrada Vehicular",
            "event_type": "Vehículo"
        })
    except Exception as e:
        logger.error(f"Error generando captura de vehículo: {e}")

def generate_mjpeg_stream(camera_id: str, mode: str, background_tasks: BackgroundTasks):
    last_frame_time = time.time()
    
    reader = camera_manager.get_reader(camera_id)
    framing_engine = camera_manager.get_framing_engine(camera_id)
    
    if not reader or not framing_engine:
        logger.error(f"Stream requested for unknown camera: {camera_id}")
        return

    while True:
        try:
            if settings.MAX_FPS > 0:
                now = time.time()
                elapsed = now - last_frame_time
                target_interval = 1.0 / settings.MAX_FPS
                if elapsed < target_interval:
                    time.sleep(target_interval - elapsed)

            ret, frame = reader.read()
            if not ret or frame is None:
                time.sleep(0.01)
                continue
                
            active_infer_cam = camera_manager.get_active_inference_camera()
            perform_inference = not settings.DETECTION_PAUSED and (active_infer_cam == camera_id)

            if not perform_inference:
                tracked_objects = []
                infer_latency = 0.0
            else:
                start_infer = time.time()
                tracked_objects = detector.detect_and_track(frame, conf=settings.CONFIDENCE_THRESHOLD)
                infer_latency = (time.time() - start_infer) * 1000.0

                for obj in tracked_objects:
                    c_id = obj.get("class_id")
                    c_name = str(obj.get("class_name", "")).lower()
                    t_id = obj.get("track_id")
                    
                    # Persona / Soldado
                    if c_id in [0, 5, 6] or any(p in c_name for p in ["person", "soldier", "soldado", "civil"]):
                        if t_id is not None:
                            cache_key = f"{camera_id}_{t_id}"
                            if face_recognition_cache.get(cache_key) is None:
                                match_info = face_recognizer.recognize_face_in_bbox(frame, obj["bbox"])
                                if match_info:
                                    face_recognition_cache[cache_key] = match_info
                            
                            match_info = face_recognition_cache.get(cache_key) or {"name": "Desconocido", "role": "No Registrado"}
                            obj["face_identity"] = match_info
                            _log_person_capture(camera_id, t_id, frame, obj["bbox"], match_info)

                    # Vehículos (Autos, Camiones, Tanques, Motos, etc.)
                    vehicle_keywords = ["car", "auto", "vehiculo", "vehicle", "truck", "camion", "bus", "colectivo", "motorcycle", "moto", "tank", "tanque", "object"]
                    if c_id in [1, 2, 3, 4, 5, 7, 8, 10] or any(v in c_name for v in vehicle_keywords):
                        if t_id is not None and not any(p in c_name for p in ["person", "soldier", "soldado", "civil"]):
                            _log_vehicle_capture(camera_id, t_id, frame, obj["bbox"], c_name)
                    
                    if settings.ENABLE_SYMBOL_RECOGNITION:
                        t_id = obj.get("track_id")
                        if t_id is not None:
                            cache_key = f"{camera_id}_{t_id}"
                            if symbol_recognition_cache.get(cache_key) is None:
                                sym_match = symbol_recognizer.recognize_symbol_in_bbox(frame, obj["bbox"])
                                if sym_match:
                                    symbol_recognition_cache[cache_key] = sym_match
                            if symbol_recognition_cache.get(cache_key):
                                obj["symbol_identity"] = symbol_recognition_cache[cache_key]

            auto_framed_output, annotated_frame, telemetry = framing_engine.process_frame(
                frame, tracked_objects, draw_overlay=settings.DRAW_OVERLAYS
            )

            now = time.time()
            dt = now - last_frame_time
            last_frame_time = now
            fps = 1.0 / dt if dt > 0 else 0.0

            if perform_inference:
                pipeline_stats["fps"] = fps
                pipeline_stats["inference_latency_ms"] = infer_latency
                pipeline_stats["frame_count"] += 1
                pipeline_stats["last_telemetry"] = telemetry

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
                continue

            frame_bytes = jpeg_buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        except Exception as e:
            logger.error(f"Error procesando frame en el stream MJPEG: {e}", exc_info=True)
            time.sleep(0.1)

@router.get("/video_feed")
async def video_feed(background_tasks: BackgroundTasks, 
                     camera_id: Optional[str] = Query(None, description="ID de la cámara a transmitir"),
                     mode: str = Query("framed", description="Modo: 'framed', 'annotated', o 'dual'"),
                     padding: Optional[float] = None,
                     ema_alpha: Optional[float] = None,
                     target_id: Optional[int] = None,
                     aspect_ratio: Optional[str] = None):
    
    if not camera_id:
        if camera_manager._camera_ids:
            camera_id = camera_manager._camera_ids[0]
        else:
            raise HTTPException(status_code=404, detail="No hay cámaras conectadas")

    if padding is not None or ema_alpha is not None or target_id is not None or aspect_ratio is not None:
        engine = camera_manager.get_framing_engine(camera_id)
        if engine:
            engine.set_parameters(ema_alpha=ema_alpha, padding=padding, aspect_ratio=aspect_ratio, target_id=target_id)
            
    if not camera_manager.get_reader(camera_id):
        raise HTTPException(status_code=404, detail=f"Cámara {camera_id} no encontrada")

    return StreamingResponse(
        generate_mjpeg_stream(camera_id=camera_id, mode=mode, background_tasks=background_tasks),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

@router.post("/api/webcam_frame")
async def receive_webcam_frame(file: UploadFile = File(...)):
    """
    Recibe un fotograma de la webcam del navegador y lo inyecta en el motor de video de la primera cámara.
    """
    if file.size and file.size > 2 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Frame muy grande")
        
    contents = await file.read()
    nparr = np.frombuffer(contents, np.uint8)
    if nparr.size > 0:
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if frame is not None:
            if camera_manager._camera_ids:
                cam_id = camera_manager._camera_ids[0]
                reader = camera_manager.get_reader(cam_id)
                if reader:
                    reader.push_frame(frame)
    return {"status": "ok"}

class EnrollB64Model(BaseModel):
    name: str = Field(..., max_length=50)
    dni: str = Field(..., max_length=20)
    role: Optional[str] = Field("Usuario", max_length=50)
    image_b64: str = Field(..., max_length=5000000)

@router.post("/api/faces/enroll_b64", dependencies=[Depends(verify_api_key)])
async def enroll_face_b64(payload: EnrollB64Model):
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
            raise HTTPException(status_code=422, detail="No se detectó rostro nítido.")

        success = face_db.register_person(name=payload.name, dni=payload.dni, role=payload.role, embedding=embedding)
        if not success:
            raise HTTPException(status_code=500, detail="Error de BD (DNI duplicado?).")

        face_recognition_cache.clear()

        for log_entry in event_logs:
            if log_entry.get("status") == "No Registrado" or log_entry.get("name") == "Desconocido":
                log_entry["name"] = payload.name
                log_entry["status"] = payload.role

        return {"status": "success", "message": f"Persona enrolada exitosamente."}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error enrolando: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/faces/enroll", dependencies=[Depends(verify_api_key)])
async def enroll_face(name: str = Query(..., max_length=50), dni: str = Query(..., max_length=20), role: Optional[str] = Query("Usuario", max_length=50), file: UploadFile = File(...)):
    if file.size and file.size > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="El archivo supera el límite de 5MB")
    
    contents = await file.read()
    nparr = np.frombuffer(contents, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if frame is None:
        raise HTTPException(status_code=400, detail="Imagen no válida")

    embedding = face_recognizer.extract_embedding(frame)
    if embedding is None:
        raise HTTPException(status_code=422, detail="No se detectó rostro.")

    success = face_db.register_person(name=name, dni=dni, role=role, embedding=embedding)
    if not success:
        raise HTTPException(status_code=500, detail="Error de BD.")

    face_recognition_cache.clear()
    last_logged_times.clear()

    return {"status": "success", "message": f"Persona enrolada exitosamente."}

@router.get("/api/faces/list")
async def list_faces():
    return {"persons": face_db.get_all_persons()}

@router.delete("/api/faces/{person_id}", dependencies=[Depends(verify_api_key)])
async def delete_face(person_id: int):
    success = face_db.delete_person(person_id)
    if not success:
        raise HTTPException(status_code=404, detail="Error")
    face_recognition_cache.clear()
    last_logged_times.clear()
    return {"status": "success"}

@router.post("/api/symbols/enroll")
async def enroll_symbol(name: str = Query(...), category: Optional[str] = Query("Insignia"), description: Optional[str] = Query(""), file: UploadFile = File(...)):
    contents = await file.read()
    nparr = np.frombuffer(contents, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    embedding = symbol_recognizer.extract_embedding(frame)
    success = symbol_db.register_symbol(name=name, category=category, description=description, embedding=embedding)
    return {"status": "success"}

@router.get("/api/symbols/list")
async def list_symbols():
    return {"symbols": symbol_db.get_all_symbols()}

@router.delete("/api/symbols/{symbol_id}")
async def delete_symbol(symbol_id: int):
    success = symbol_db.delete_symbol(symbol_id)
    return {"status": "success"}
