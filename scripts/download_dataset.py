import os
import sys
import shutil
import logging
from pathlib import Path
import yaml
import kagglehub

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("DownloadDataset")

DATASET_HANDLE = "rawsi18/military-assets-dataset-12-classes-yolo8-format"
DEST_DIR = Path(__file__).resolve().parent.parent / "data" / "military_assets"

def setup_dataset():
    logger.info(f"Iniciando descarga automatizada del dataset desde Kaggle ({DATASET_HANDLE})...")
    
    try:
        download_path_str = kagglehub.dataset_download(DATASET_HANDLE)
        download_path = Path(download_path_str)
        logger.info(f"Dataset descargado por kagglehub en: {download_path}")
    except Exception as e:
        logger.error(f"Error descargando el dataset con kagglehub: {e}")
        sys.exit(1)

    DEST_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f"Copiando y organizando archivos en: {DEST_DIR.resolve()}...")

    # Si los datos están dentro de un subdirectorio (ej. military_object_dataset), desglosarlo a la raíz de DEST_DIR
    subdirs = [d for d in DEST_DIR.iterdir() if d.is_dir()]
    if len(subdirs) == 1 and (subdirs[0] / "train").exists():
        subfolder = subdirs[0]
        logger.info(f"Aplanando estructura desde {subfolder.name}...")
        for child in subfolder.iterdir():
            target = DEST_DIR / child.name
            if target.exists():
                if target.is_dir():
                    shutil.rmtree(target)
                else:
                    target.unlink()
            shutil.move(str(child), str(target))
        shutil.rmtree(subfolder)

    logger.info("Estructura ajustada correctamente. Verificando y creando data.yaml...")

    yaml_files = list(DEST_DIR.glob("*.yaml")) + list(DEST_DIR.glob("*.yml"))
    data_config = {}
    if yaml_files:
        for yf in yaml_files:
            try:
                with open(yf, "r", encoding="utf-8") as f:
                    cfg = yaml.safe_load(f)
                    if isinstance(cfg, dict) and "names" in cfg:
                        data_config = cfg
                        break
            except Exception:
                pass

    # Asegurar configuración para YOLOv8
    data_config["path"] = str(DEST_DIR.resolve())
    data_config["train"] = "train/images" if (DEST_DIR / "train" / "images").exists() else "train"
    data_config["val"] = "val/images" if (DEST_DIR / "val" / "images").exists() else "val"
    if (DEST_DIR / "test").exists():
        data_config["test"] = "test/images" if (DEST_DIR / "test" / "images").exists() else "test"

    if "names" not in data_config or not data_config["names"]:
        data_config["names"] = {
            0: "camouflage_soldier",
            1: "weapon",
            2: "military_tank",
            3: "military_truck",
            4: "military_vehicle",
            5: "civilian",
            6: "soldier",
            7: "civilian_vehicle",
            8: "military_artillery",
            9: "trench",
            10: "military_aircraft",
            11: "military_warship"
        }

    final_yaml_path = DEST_DIR / "data.yaml"
    with open(final_yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(data_config, f, default_flow_style=False, sort_keys=False)

    logger.info(f"✅ Configuración final guardada en: {final_yaml_path.resolve()}")
    logger.info("Contenido del archivo data.yaml:")
    with open(final_yaml_path, "r", encoding="utf-8") as f:
        print(f.read())

if __name__ == "__main__":
    setup_dataset()

