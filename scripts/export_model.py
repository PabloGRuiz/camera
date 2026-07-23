import os
import sys
import logging
from pathlib import Path
from ultralytics import YOLO

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ExportModel")

def export_yolo_to_openvino(model_name: str = "yolov8n", output_dir: str = "models"):
    """
    Descarga el modelo PyTorch YOLOv8 (.pt) y lo exporta a formato OpenVINO IR (.xml/.bin).
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    openvino_model_dir = output_path / f"{model_name}_openvino_model"
    
    if openvino_model_dir.exists() and any(openvino_model_dir.iterdir()):
        logger.info(f"El modelo OpenVINO ya existe en: {openvino_model_dir.resolve()}")
        return str(openvino_model_dir)

    logger.info(f"Cargando modelo PyTorch: {model_name}.pt...")
    model = YOLO(f"{model_name}.pt")

    logger.info(f"Exportando {model_name}.pt a formato OpenVINO IR...")
    # Exportar a OpenVINO
    export_path = model.export(format="openvino", dynamic=True)
    logger.info(f"Exportación exitosa. Ruta generada: {export_path}")

    # Si la ruta exportada no está en el directorio objetivo de modelos, la movemos o usamos
    export_dir_path = Path(export_path)
    if export_dir_path.resolve() != openvino_model_dir.resolve():
        if not openvino_model_dir.exists():
            import shutil
            shutil.move(str(export_dir_path), str(openvino_model_dir))
            logger.info(f"Modelo movido a: {openvino_model_dir.resolve()}")

    return str(openvino_model_dir)

if __name__ == "__main__":
    model_name_arg = os.getenv("MODEL_NAME", "yolov8n")
    try:
        export_yolo_to_openvino(model_name=model_name_arg)
    except Exception as e:
        logger.error(f"Error exportando el modelo a OpenVINO: {e}", exc_info=True)
        sys.exit(1)
