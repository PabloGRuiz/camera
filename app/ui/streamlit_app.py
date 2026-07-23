import os
import streamlit as st
import requests
import json

st.set_page_config(
    page_title="Object-Centered Auto-Framing Dashboard",
    page_icon="🎥",
    layout="wide"
)

st.title("🎥 Object-Centered Tracking & Auto-Framing Dashboard")
st.markdown("Control de parámetros en tiempo real con inferencia optimizada por **Intel OpenVINO**.")

FASTAPI_URL = os.getenv("FASTAPI_URL", "http://localhost:8080")

# Sidebar de Controles
st.sidebar.header("⚙️ Parámetros de Auto-Framing")

ema_alpha = st.sidebar.slider("Factor de Suavizado EMA (α)", min_value=0.01, max_value=1.0, value=0.15, step=0.01)
padding = st.sidebar.slider("Padding / Margen (%)", min_value=0, max_value=60, value=20, step=5)
aspect_ratio = st.sidebar.selectbox("Relación de Aspecto Target", ["16:9", "9:16", "1:1", "FREE"], index=0)
target_id = st.sidebar.number_input("ID de Objeto Objetivo (-1 = Auto)", value=-1, step=1)
draw_overlays = st.sidebar.checkbox("Mostrar Overlays en Vista Previa", value=True)

mode = st.sidebar.radio("Modo de Transmisión", ["framed", "annotated", "dual"], index=0)

# Botón para actualizar parámetros vía API
if st.sidebar.button("Aplicar Cambios en Vivo"):
    try:
        payload = {
            "ema_alpha": float(ema_alpha),
            "padding": float(padding) / 100.0,
            "aspect_ratio": aspect_ratio,
            "target_id": int(target_id),
            "draw_overlays": draw_overlays
        }
        res = requests.post(f"{FASTAPI_URL}/api/settings", json=payload, timeout=2)
        if res.status_code == 200:
            st.sidebar.success("✅ Parámetros actualizados")
        else:
            st.sidebar.error("Error al actualizar la configuración")
    except Exception as e:
        st.sidebar.warning(f"No se pudo conectar a la API FastAPI en {FASTAPI_URL}: {e}")

# Layout Principal: Video + Telemetría
col1, col2 = st.columns([3, 1])

with col1:
    st.subheader("📺 Flujo de Video en Tiempo Real")
    stream_url = f"{FASTAPI_URL}/video_feed?mode={mode}"
    st.image(stream_url, use_container_width=True)

with col2:
    st.subheader("📊 Telemetría del Sistema")
    try:
        res = requests.get(f"{FASTAPI_URL}/api/status", timeout=2)
        if res.status_code == 200:
            status_data = res.json()
            st.metric("Rendimiento", f"{status_data.get('fps', 0)} FPS")
            st.metric("Latencia Inferencia", f"{status_data.get('inference_latency_ms', 0)} ms")
            st.metric("Dispositivo OpenVINO", status_data.get('openvino_device', 'CPU'))
            
            telemetry = status_data.get('telemetry', {})
            st.write("**Detalles del Objetivo:**")
            st.json(telemetry)
    except Exception:
        st.info("Conectando con la API para obtener telemetría...")
