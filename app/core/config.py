from typing import List, Union
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    """
    Configuración global del sistema Object-Centered Tracking & Auto-Framing.
    Permite anulación mediante variables de entorno o archivo .env.
    """
    APP_TITLE: str = "Object-Centered Tracking & Auto-Framing System"
    APP_VERSION: str = "1.0.0"
    
    # Inferencia & Modelo
    MODEL_NAME: str = "yolov8n"
    MODEL_PATH: str = "models/yolov8n_openvino_model"
    OPENVINO_DEVICE: str = Field(default="CPU", description="Dispositivo OpenVINO: CPU, GPU, MYRIAD, etc.")
    CONFIDENCE_THRESHOLD: float = 0.35
    DETECTION_PAUSED: bool = False
    TARGET_CLASSES: Union[List[int], None] = None  # None = Detectar todas las clases del modelo activo por defecto
    ENABLE_SYMBOL_RECOGNITION: bool = False        # Desactivado por defecto para evitar falsos positivos con objetos
    
    # Optimizaciones de Rendimiento
    FRAME_SKIP: int = 3                 # Ejecuta IA cada N frames (1=Siempre, 3=IA en frame 0, tracker clásico en 1,2)
    USE_INT8_QUANTIZATION: bool = True  # Exportar modelo a OpenVINO INT8 (vía NNCF)
    
    # Auto-Framing & Suavizado
    DEFAULT_PADDING: float = 0.20       # 20% de padding alrededor del objeto
    DEFAULT_EMA_ALPHA: float = 0.15     # Alpha de suavizado exponencial (0.01 a 1.0)
    DEFAULT_ASPECT_RATIO: str = "16:9"  # '16:9', '9:16', '1:1', 'FREE'
    TARGET_OBJECT_ID: Union[int, None] = None  # None = Seleccionar el más dominante/cercano al centro
    
    # Fuente de Video & Stream
    VIDEO_SOURCE: str = "SYNTHETIC"     # "SYNTHETIC", "0" (webcam), o ruta a un archivo MP4/stream RTSP
    MAX_FPS: int = 10
    DRAW_OVERLAYS: bool = True          # Dibujar cajas y vectores en la vista previa
    # Servidor Central & Identificación del Nodo
    CENTRAL_SERVER_URL: str = "http://localhost:8082"
    NODE_ID: str = "NODE-LOCAL-01"
    NODE_NAME: str = "Estacion de Control Local"
    HEARTBEAT_INTERVAL: int = 10
    NODE_AUTH_TOKEN: str = "super_secret_edge_key_2026"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
