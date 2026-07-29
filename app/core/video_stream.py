import cv2
import time
import math
import numpy as np
import threading
import logging
from typing import Tuple, Union

logger = logging.getLogger("VideoStream")

class SyntheticVideoGenerator:
    """
    Generador de video sintético en tiempo real con sujetos en movimiento.
    Permite probar todo el pipeline de auto-framing sin depender de cámaras o archivos externos.
    """
    def __init__(self, width: int = 1280, height: int = 720, fps: int = 30):
        self.width = width
        self.height = height
        self.fps = fps
        self.frame_count = 0

    def generate_frame(self) -> np.ndarray:
        self.frame_count += 1
        t = self.frame_count / float(self.fps)

        # Fondo con gradiente dinámico elegante
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        
        # Grid decorativa de fondo
        grid_size = 40
        for y in range(0, self.height, grid_size):
            cv2.line(frame, (0, y), (self.width, y), (25, 30, 35), 1)
        for x in range(0, self.width, grid_size):
            cv2.line(frame, (x, 0), (x, self.height), (25, 30, 35), 1)

        # Sujeto 1: Persona simulación (Movimiento Lissajous suave)
        cx1 = int(self.width / 2 + math.sin(t * 0.8) * (self.width * 0.3))
        cy1 = int(self.height / 2 + math.cos(t * 1.2) * (self.height * 0.2))
        w1, h1 = 120, 240
        
        # Sujeto 2: Objeto secundario (Movimiento circular opuesto)
        cx2 = int(self.width / 2 + math.cos(t * 0.5) * (self.width * 0.35))
        cy2 = int(self.height / 2 + math.sin(t * 0.7) * (self.height * 0.25))
        w2, h2 = 140, 140

        # Dibujar Sujeto 1 (Avatar estilizado representando una persona)
        cv2.rectangle(frame, (cx1 - w1//2, cy1 - h1//2), (cx1 + w1//2, cy1 + h1//2), (40, 160, 220), -1)
        cv2.circle(frame, (cx1, cy1 - h1//3), 35, (230, 230, 240), -1)  # Cabeza
        cv2.putText(frame, "Subject 1 (Person)", (cx1 - w1//2, cy1 - h1//2 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        # Dibujar Sujeto 2 (Caja/Vehículo sintético)
        cv2.rectangle(frame, (cx2 - w2//2, cy2 - h2//2), (cx2 + w2//2, cy2 + h2//2), (200, 100, 40), -1)
        cv2.putText(frame, "Subject 2 (Object)", (cx2 - w2//2, cy2 - h2//2 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        # Información de overlay en el video fuente
        cv2.putText(frame, f"SYNTHETIC VIDEO STREAM | Frame: {self.frame_count}", (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 180), 2)

        return frame


class VideoStreamReader:
    """
    Lector de flujo de video multihilo (Threaded Video Capture).
    Garantiza una lectura continua sin bloqueo del pipeline principal.
    """
    def __init__(self, source: Union[str, int] = "SYNTHETIC", target_fps: int = 30):
        self.source = source
        self.target_fps = target_fps
        self.stopped = False
        self.lock = threading.Lock()
        self.current_frame = None
        self.is_synthetic = False
        self.cap = None
        self.synthetic_gen = None

        self._init_source()

    def _init_source(self):
        source_str = str(self.source).strip()
        
        # Evaluar si la fuente es sintética, número de webcam o archivo/stream
        if source_str.upper() in ["SYNTHETIC", "DEMO", "MOCK"]:
            logger.info("Iniciando VideoStreamReader en modo SYNTHETIC GENERATOR.")
            self.is_synthetic = True
            self.synthetic_gen = SyntheticVideoGenerator(fps=self.target_fps)
            self.current_frame = self.synthetic_gen.generate_frame()
        else:
            try:
                # Si es un número (ej. "0"), convertir a int para la cámara web
                src_val = int(source_str) if source_str.isdigit() else source_str
                if isinstance(src_val, int):
                    self.cap = cv2.VideoCapture(src_val, cv2.CAP_DSHOW)
                    if not self.cap.isOpened():
                        self.cap = cv2.VideoCapture(src_val)
                else:
                    self.cap = cv2.VideoCapture(src_val)

                if not self.cap.isOpened():
                    logger.warning(f"No se pudo abrir la fuente: {src_val}. Recurriendo a modo SYNTHETIC.")
                    self.is_synthetic = True
                    self.synthetic_gen = SyntheticVideoGenerator(fps=self.target_fps)
                    self.current_frame = self.synthetic_gen.generate_frame()
                else:
                    ret, frame = self.cap.read()
                    if ret:
                        self.current_frame = frame
                    else:
                        logger.warning("No se pudo leer el primer frame. Recurriendo a SYNTHETIC.")
                        self.is_synthetic = True
                        self.synthetic_gen = SyntheticVideoGenerator(fps=self.target_fps)
                        self.current_frame = self.synthetic_gen.generate_frame()
            except Exception as e:
                logger.error(f"Error abriendo la fuente de video {self.source}: {e}. Usando modo SYNTHETIC.")
                self.is_synthetic = True
                self.synthetic_gen = SyntheticVideoGenerator(fps=self.target_fps)
                self.current_frame = self.synthetic_gen.generate_frame()

    def start(self):
        """Inicia el hilo de captura en segundo plano."""
        self.stopped = False
        self.thread = threading.Thread(target=self._update_loop, daemon=True)
        self.thread.start()
        return self

    def _update_loop(self):
        frame_interval = 1.0 / float(self.target_fps)
        while not self.stopped:
            start_time = time.time()
            # Si se han enviado fotogramas de webcam en los últimos 2 segundos, priorizar la webcam
            is_client_webcam_active = hasattr(self, "last_pushed_time") and (time.time() - self.last_pushed_time < 2.0)
            
            if self.is_synthetic and not is_client_webcam_active:
                frame = self.synthetic_gen.generate_frame()
                with self.lock:
                    self.current_frame = frame
            else:
                if self.cap and self.cap.isOpened():
                    ret, frame = self.cap.read()
                    if not ret:
                        # Si es un archivo de video y llegó al final, rebobinar
                        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        ret, frame = self.cap.read()
                    
                    if ret:
                        with self.lock:
                            self.current_frame = frame

            elapsed = time.time() - start_time
            sleep_time = max(0.001, frame_interval - elapsed)
            time.sleep(sleep_time)

    def read(self) -> Tuple[bool, np.ndarray]:
        """Obtiene el último fotograma capturado de forma thread-safe."""
        with self.lock:
            if self.current_frame is None:
                return False, np.zeros((720, 1280, 3), dtype=np.uint8)
            return True, self.current_frame.copy()

    def push_frame(self, frame: np.ndarray):
        """Recibe un fotograma en vivo desde el cliente y lo inyecta en el búfer de video del servidor."""
        with self.lock:
            self.current_frame = frame
            self.last_pushed_time = time.time()

    def stop(self):
        """Detiene el hilo de lectura y libera los recursos."""
        self.stopped = True
        if self.cap:
            self.cap.release()
        logger.info("VideoStreamReader detenido correctamente.")
