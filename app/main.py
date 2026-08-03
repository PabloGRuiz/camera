import os
import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.routes import router as api_router
from scripts.export_model import export_yolo_to_openvino

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("MainApp")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Evento de inicio y cierre de la aplicación FastAPI."""
    logger.info(f"Iniciando {settings.APP_TITLE} v{settings.APP_VERSION}")
    
    # Verificar y exportar el modelo YOLOv8 a OpenVINO IR si no existe
    model_dir = Path(settings.MODEL_PATH)
    if not model_dir.exists() or not any(model_dir.iterdir()):
        logger.info("Comprobando disponibilidad del modelo OpenVINO en el inicio de la app...")
        try:
            export_yolo_to_openvino(model_name=settings.MODEL_NAME, output_dir="models")
        except Exception as e:
            logger.warning(f"No se pudo completar la exportación automática de OpenVINO en startup: {e}")

    yield
    logger.info("Deteniendo la aplicación...")

app = FastAPI(
    title=settings.APP_TITLE,
    version=settings.APP_VERSION,
    lifespan=lifespan
)

# Configuración de CORS Segura
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,  # Mitigación de riesgo: Evita robo de sesión
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Configuración de rutas estáticas y plantillas HTML
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "ui" / "static"
TEMPLATES_DIR = BASE_DIR / "ui" / "templates"

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Incluir rutas de API
app.include_router(api_router)

from fastapi.responses import FileResponse, HTMLResponse

@app.get("/")
async def render_index():
    """Renderiza el Panel de Control Web principal."""
    try:
        index_file = TEMPLATES_DIR / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
        return HTMLResponse(f"<h3>Plantilla index.html no encontrada en {index_file}</h3>", status_code=404)
    except Exception as e:
        logger.error(f"Error sirviendo la página principal: {e}", exc_info=True)
        return HTMLResponse(f"<h3>Internal Error: {e}</h3>", status_code=500)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
