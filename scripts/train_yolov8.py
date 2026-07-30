import os
import sys
import shutil
import argparse
import logging
from pathlib import Path
from ultralytics import YOLO

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("TrainYOLOv8")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_YAML = PROJECT_ROOT / "data" / "military_assets" / "data.yaml"
OUTPUT_MODELS_DIR = PROJECT_ROOT / "models"

def parse_args():
    parser = argparse.ArgumentParser(description="Entrenar modelo YOLOv8 localmente")
    parser.add_argument("--model", type=str, default="yolov8n.pt", help="Modelo base PyTorch (yolov8n.pt, yolov8s.pt, etc.)")
    parser.add_argument("--data", type=str, default=str(DEFAULT_DATA_YAML), help="Ruta al archivo data.yaml")
    parser.add_argument("--epochs", type=int, default=50, help="Número de épocas para entrenamiento")
    parser.add_argument("--batch", type=int, default=8, help="Tamaño de lote (batch size)")
    parser.add_argument("--imgsz", type=int, default=640, help="Resolución de las imágenes")
    parser.add_argument("--device", type=str, default="cpu", help="Dispositivo para entrenamiento: 'cpu' o '0' (GPU)")
    parser.add_argument("--project", type=str, default=str(PROJECT_ROOT / "runs" / "detect"), help="Directorio de salidas del experimento")
    parser.add_argument("--name", type=str, default="train_military_assets", help="Nombre del experimento")
    return parser.parse_args()

def main():
    args = parse_args()
    data_yaml_path = Path(args.data)

    if not data_yaml_path.exists():
        logger.error(f"El archivo data.yaml no fue encontrado en: {data_yaml_path.resolve()}")
        logger.error("Por favor ejecuta primero: python scripts/download_dataset.py")
        sys.exit(1)

    logger.info(f"Cargando modelo base: {args.model}...")
    model = YOLO(args.model)

    logger.info(f"Iniciando entrenamiento local YOLOv8:")
    logger.info(f"  - Dataset config: {data_yaml_path.resolve()}")
    logger.info(f"  - Épocas: {args.epochs}")
    logger.info(f"  - Batch Size: {args.batch}")
    logger.info(f"  - Resolución Image: {args.imgsz}")
    logger.info(f"  - Dispositivo: {args.device}")

    # Ejecutar entrenamiento
    results = model.train(
        data=str(data_yaml_path.resolve()),
        epochs=args.epochs,
        batch=args.batch,
        imgsz=args.imgsz,
        device=args.device,
        project=args.project,
        name=args.name,
        exist_ok=True,
        workers=2,
        save=True
    )

    logger.info("Entrenamiento completado exitosamente.")

    # Copiar los mejores pesos a la carpeta models/
    best_weights_path = Path(args.project) / args.name / "weights" / "best.pt"
    if best_weights_path.exists():
        OUTPUT_MODELS_DIR.mkdir(parents=True, exist_ok=True)
        dest_best_weights = OUTPUT_MODELS_DIR / "military_assets_yolov8n.pt"
        shutil.copy2(best_weights_path, dest_best_weights)
        logger.info(f"✅ Mejores pesos guardados en: {dest_best_weights.resolve()}")
    else:
        logger.warning(f"No se encontró el archivo de pesos 'best.pt' en {best_weights_path}")

if __name__ == "__main__":
    main()
