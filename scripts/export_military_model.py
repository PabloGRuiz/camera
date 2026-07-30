import os
import sys
import argparse
import logging
from pathlib import Path
from ultralytics import YOLO

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ExportMilitaryModel")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MODEL_PATH = PROJECT_ROOT / "models" / "military_assets_yolov8n.pt"

def export_to_openvino(weights_path: Path, use_int8: bool = False):
    if not weights_path.exists():
        logger.error(f"No se encontró el archivo de pesos: {weights_path.resolve()}")
        logger.error("Asegúrate de haber ejecutado el entrenamiento primero: python scripts/train_yolov8.py")
        sys.exit(1)

    logger.info(f"Cargando modelo PyTorch entrenado: {weights_path.name}...")
    model = YOLO(str(weights_path))

    suffix = "_int8" if use_int8 else ""
    output_dir_name = f"{weights_path.stem}_openvino{suffix}_model"
    output_dir = PROJECT_ROOT / "models" / output_dir_name

    logger.info(f"Exportando {weights_path.name} a formato OpenVINO IR (INT8={use_int8})...")
    
    if use_int8:
        dataset_yaml = PROJECT_ROOT / "data" / "military_assets" / "data.yaml"
        export_path = model.export(format="openvino", dynamic=True, int8=True, data=str(dataset_yaml))
    else:
        export_path = model.export(format="openvino", dynamic=True)

    logger.info(f"✅ Modelo exportado correctamente en: {export_path}")
    return export_path

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Exportar modelo militar entrenado a OpenVINO")
    parser.add_argument("--weights", type=str, default=str(DEFAULT_MODEL_PATH), help="Ruta al archivo .pt entrenado")
    parser.add_argument("--int8", action="store_true", help="Cuantizar a INT8 utilizando NNCF")
    args = parser.parse_args()

    export_to_openvino(weights_path=Path(args.weights), use_int8=args.int8)
