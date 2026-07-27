FROM python:3.10-slim

# Evitar prompts interactivos durante la instalación
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Instalación de dependencias del sistema para OpenCV y OpenVINO
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    ffmpeg \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

# Copiar e instalar dependencias de Python
COPY requirements.txt .
RUN pip install --default-timeout=1000 --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements.txt

# Copiar la estructura del código del proyecto
COPY . /workspace

# Crear directorios para modelos y datos
RUN mkdir -p /workspace/models /workspace/data

EXPOSE 8000
EXPOSE 8501

# Comando por defecto: inicia el servidor FastAPI inmediatamente (el modelo se carga/exporta dinámicamente)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
