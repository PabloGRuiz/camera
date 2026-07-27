import os
import sys
import logging
from pathlib import Path
from ultralytics import YOLO

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ExportModel")

def export_yolo_to_openvino(model_name: str = "yolov8n", output_dir: str = "models", use_int8: bool = False):
    """
    Descarga el modelo PyTorch YOLOv8 (.pt) y lo exporta a formato OpenVINO IR (.xml/.bin).
    Soporta cuantización a INT8 usando NNCF para acelerar la inferencia en CPU.
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Nombre del directorio de salida basado en si usamos INT8
    suffix = "_int8" if use_int8 else ""
    openvino_model_dir = output_path / f"{model_name}_openvino{suffix}_model"
    
    if openvino_model_dir.exists() and any(openvino_model_dir.iterdir()):
        logger.info(f"El modelo OpenVINO ya existe en: {openvino_model_dir.resolve()}")
        return str(openvino_model_dir)

    logger.info(f"Cargando modelo PyTorch: {model_name}.pt...")
    model = YOLO(f"{model_name}.pt")

    logger.info(f"Exportando {model_name}.pt a formato OpenVINO IR (INT8={use_int8})...")
    # Exportar a OpenVINO
    if use_int8:
        logger.info("Iniciando cuantización NNCF INT8 (puede descargar dataset de calibración COCO128)...")
        export_path = model.export(format="openvino", dynamic=True, int8=True, data="coco128.yaml")
    else:
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
