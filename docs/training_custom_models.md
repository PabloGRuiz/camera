# Guía Completa: Cómo Entrenar Modelos Personalizados para Reconocimiento de Objetos en YOLOv8 + Intel OpenVINO

Esta guía explica en detalle cómo funciona la detección de objetos en nuestro sistema y cómo puedes entrenar un modelo personalizado (*Fine-Tuning*) para reconocer cualquier elemento específico (por ejemplo, **tijeras rojas**, herramientas, productos o piezas industriales).

---

## 💡 1. ¿Cómo Funciona la Detección de Objetos en este Sistema?

El sistema combina tres capas tecnológicas:

1. **Reconocimiento con YOLOv8 + Intel OpenVINO**:
   - El modelo base `yolov8n` fue entrenado con el dataset **COCO** (contiene **80 clases de objetos cotidianos** como personas, tijeras, celulares, tazas, autos, gatos, etc.).
   - La red neuronal recibe el fotograma y genera automáticamente las cajas delimitadoras (*Bounding Boxes*), la clase del objeto y el porcentaje de confianza.

2. **Seguimiento con ByteTrack**:
   - Asigna un **ID persistente e inmutable** a cada objeto detectado cuadro a cuadro (`ID #1`, `ID #2`, etc.).

---

## 🎓 2. Guía Paso a Paso para Entrenar un Modelo Personalizado (Custom YOLOv8 Model)

Si deseas que el sistema reconozca un elemento **muy específico** (por ejemplo, una herramienta industrial, un producto específico o una pieza exclusiva):

### Paso 1: Recopilación de Imágenes (Dataset)
1. Toma **entre 40 y 100 fotografías** del objeto con tu teléfono o webcam.
2. Asegúrate de incluir variedad:
   - Distintas orientaciones y ángulos (frente, perfil, diagonal).
   - Distintos fondos (mesa, mano, fondo claro, fondo oscuro).
   - Distintas iluminaciones (luz natural, luz artificial, sombras).

---

### Paso 2: Etiquetado de las Imágenes (Annotations)
Usa una herramienta gratuita y basada en web como **[Roboflow](https://roboflow.com/)** o la aplicación local **[LabelImg](https://github.com/HumanSignal/labelImg)**:

1. Crea un nuevo proyecto en Roboflow de tipo **Object Detection**.
2. Sube tus fotografías.
3. Dibuja un rectángulo alrededor del objeto y asígnale la etiqueta (ejemplo: `objeto_custom`).
4. Haz clic en **Export Dataset** en formato **YOLOv8 PyTorch**.

---

### Paso 3: Entrenamiento del Modelo con Python

Puedes realizar el entrenamiento de forma gratuita en **Google Colab** o en tu máquina local con Python:

```python
from ultralytics import YOLO

# 1. Cargar el modelo base pre-entrenado
model = YOLO('yolov8n.pt')

# 2. Entrenar el modelo con tu dataset etiquetado
results = model.train(
    data='path/to/data.yaml',  # Archivo generado por Roboflow
    epochs=50,                  # Número de iteraciones
    imgsz=640,                  # Resolución de entrada
    name='modelo_custom'
)

# 3. El resultado genera el archivo: runs/detect/modelo_custom/weights/best.pt
```

---

### Paso 4: Integración en nuestro Proyecto

1. Copia tu archivo de modelo entrenado `best.pt` a la carpeta `models/` de este proyecto con el nombre que desees:
   ```
   models/objeto_custom.pt
   ```

2. Configura el nombre del modelo en `docker-compose.yml`:
   ```yaml
   environment:
     - MODEL_NAME=objeto_custom
   ```

3. Al iniciar el contenedor (`docker-compose up`), nuestro script [`export_model.py`](file:///c:/Users/pablruiz/Proyectos/Object-Centered%20Tracking%20%26%20Auto-Framing/scripts/export_model.py) convertirá automáticamente tu modelo `.pt` al formato **Intel OpenVINO IR (`.xml` / `.bin`)** optimizado para tu procesador Intel.

---

## 🎯 3. Resumen de Opciones de Detección en la Interfaz Web

En el panel de control web ([http://localhost:8080](http://localhost:8080)) puedes seleccionar el objeto a detectar mediante el menú desplegable **"Objetos a Detectar"**:

- **👤 Personas (Seguimiento Humano)**: Rastrea exclusivamente cuerpos y rostros humanos.
- **📦 Objetos (Celulares, Tazas, Sillas, Laptops, etc.)**: Enfoca únicamente en objetos inanimados de las 80 clases COCO.
- **✨ Todos (Personas + Objetos)**: Detecta simultáneamente personas y objetos.
