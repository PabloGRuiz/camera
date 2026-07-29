# Object-Centered Tracking & Auto-Framing System

Un sistema de alto rendimiento de visión por computadora para **seguimiento de objetos centrado en el sujeto** y **encuadre automático dinámico (Auto-Framing)** con aceleración de inferencia **Intel OpenVINO**, extrapoblación de velocidad lineal $O(1)$ y filtrado **Cinematic Damping (Spring Model)**.

---

## 🛠️ Stack Tecnológico

- **Backend**: Python 3.10+, FastAPI (Streaming MJPEG asíncrono y REST API limitando a 10 FPS de forma eficiente).
- **Motor de Visión**: YOLOv8 (Ultralytics) + ByteTrack para seguimiento persistente por ID + Extrapolación de Velocidad Lineal para frame skipping sin latencia.
- **Aceleración Inferencia**: Intel OpenVINO Toolkit (Optimizado para procesadores Intel i7 e iGPU UHD 630 / CPU vectorizado).
- **Procesamiento de Imagen**: OpenCV (`opencv-python-headless`) con caché asíncrono para biometría facial.
- **Panel de Control**: Interfaz Web HTML5/JS responsiva en modo oscuro + Dashboard en Streamlit.
- **Contenerización**: Docker & Docker Compose.

---

## 🚀 Inicio Rápido con Docker Compose

La forma más sencilla de ejecutar el prototipo completo es mediante Docker Compose:

```bash
docker-compose up --build
```

Una vez iniciados los contenedores:
- 🌐 **Panel Web Principal (FastAPI + Web UI)**: [http://localhost:8000](http://localhost:8000)
- 📊 **Dashboard en Streamlit**: [http://localhost:8501](http://localhost:8501)
- 🩺 **Healthcheck & Dispositivo OpenVINO**: [http://localhost:8000/health](http://localhost:8000/health)

---

## 💻 Ejecución Local (Sin Docker)

1. **Crear entorno virtual e instalar dependencias**:
   ```bash
   python -m venv venv
   # En Windows:
   venv\Scripts\activate
   # En Linux/macOS:
   source venv/bin/activate

   pip install -r requirements.txt
   ```

2. **Exportar modelo a OpenVINO IR**:
   ```bash
   python scripts/export_model.py
   ```

3. **Iniciar el servidor FastAPI**:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

---

## 📡 API Endpoints

- `GET /`: Panel de Control Web interactivo.
- `GET /video_feed?mode=framed`: Flujo MJPEG de video recortado y suavizado centrado en el objetivo.
- `GET /video_feed?mode=annotated`: Flujo MJPEG original con recuadros de tracking y retícula.
- `GET /video_feed?mode=dual`: Flujo en vista dividida (Original vs Auto-Framed side-by-side).
- `POST /api/settings`: Modificación en tiempo real de `ema_alpha`, `padding`, `target_id`, `aspect_ratio`, `draw_overlays`.
- `GET /api/status`: Telemetría en tiempo real (FPS, latencia OpenVINO, ID activo, coordenadas).

---

## 🧪 Pruebas Automatizadas

Para validar las matemáticas del filtro EMA y las restricciones de bordes del recuadro de encuadre:
```bash
pytest tests/
```
