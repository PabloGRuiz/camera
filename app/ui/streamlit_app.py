import os
import streamlit as st
import requests
import json
import base64

st.set_page_config(
    page_title="Sistema de Seguimiento y Detección de Objetivos",
    layout="wide"
)

st.title("Sistema de Seguimiento y Detección de Objetivos")
st.markdown("Control de parámetros en tiempo real con inferencia optimizada por **Intel OpenVINO** y soporte multi-cámara.")

FASTAPI_URL = os.getenv("FASTAPI_URL", "http://localhost:8081")

# Sidebar de Controles
st.sidebar.header("Gestión de Cámaras")

try:
    res = requests.get(f"{FASTAPI_URL}/api/camera/list", timeout=2)
    if res.status_code == 200:
        cam_data = res.json()
        cameras = cam_data.get("cameras", [])
        fixed_camera = cam_data.get("fixed_camera")
        active_inference = cam_data.get("active_inference_camera")
        
        st.sidebar.markdown(f"**Cámaras Activas:** {len(cameras)}")
        if cameras:
            selected_view_cam = st.sidebar.selectbox("Cámara para Visualizar", cameras, index=0)
            
            fixed_selection = st.sidebar.selectbox("Fijar Inferencia en Cámara (Opcional)", ["Ninguna"] + cameras, index=0 if not fixed_camera else cameras.index(fixed_camera) + 1)
            
            if st.sidebar.button("Aplicar Configuración de Cámara"):
                fix_cam = None if fixed_selection == "Ninguna" else fixed_selection
                requests.post(f"{FASTAPI_URL}/api/camera/control", json={"action": "fix", "camera_id": fix_cam}, timeout=2)
                st.sidebar.success("Configuración aplicada")
                st.rerun()
        else:
            selected_view_cam = None
            st.sidebar.warning("No hay cámaras conectadas.")
    else:
        selected_view_cam = None
        st.sidebar.error("Error obteniendo cámaras.")
except Exception as e:
    selected_view_cam = None
    st.sidebar.warning(f"No se pudo conectar a FastAPI: {e}")

st.sidebar.header("Parámetros de Auto-Framing")
ema_alpha = st.sidebar.slider("Factor de Suavizado EMA (α)", min_value=0.01, max_value=1.0, value=0.15, step=0.01)
padding = st.sidebar.slider("Padding / Margen (%)", min_value=0, max_value=60, value=20, step=5)
aspect_ratio = st.sidebar.selectbox("Relación de Aspecto Target", ["16:9", "9:16", "1:1", "FREE"], index=0)
target_id = st.sidebar.number_input("ID de Objeto Objetivo (-1 = Auto)", value=-1, step=1)
draw_overlays = st.sidebar.checkbox("Mostrar Overlays en Vista Previa", value=True)
mode = st.sidebar.radio("Modo de Transmisión", ["framed", "annotated", "dual"], index=0)

if st.sidebar.button("Aplicar Cambios en Vivo") and selected_view_cam:
    try:
        payload = {
            "ema_alpha": float(ema_alpha),
            "padding": float(padding) / 100.0,
            "aspect_ratio": aspect_ratio,
            "target_id": int(target_id),
            "draw_overlays": draw_overlays,
            "camera_id": selected_view_cam
        }
        res = requests.post(f"{FASTAPI_URL}/api/settings", json=payload, timeout=2)
        if res.status_code == 200:
            st.sidebar.success("Parámetros actualizados")
        else:
            st.sidebar.error("Error al actualizar la configuración")
    except Exception as e:
        st.sidebar.warning(f"Error: {e}")

PUBLIC_FASTAPI_URL = os.getenv("PUBLIC_FASTAPI_URL", "http://localhost:8081")

# Tabs Principales
tab_dashboard, tab_enrolamiento, tab_registro = st.tabs([
    "Dashboard", 
    "Enrolamiento de Personal", 
    "Registro de Detecciones (Local)"
])

with tab_dashboard:
    col1, col2 = st.columns([3, 1])

    with col1:
        st.subheader("Transmisión en Vivo")
        if selected_view_cam:
            stream_url = f"{PUBLIC_FASTAPI_URL}/video_feed?camera_id={selected_view_cam}&mode={mode}"
            st.image(stream_url, use_container_width=True)
        else:
            st.info("Selecciona o conecta una cámara para ver el flujo.")

    with col2:
        st.subheader("Telemetría del Sistema")
        try:
            res = requests.get(f"{FASTAPI_URL}/api/status", timeout=2)
            if res.status_code == 200:
                status_data = res.json()
                st.metric("Rendimiento", f"{status_data.get('fps', 0)} FPS")
                st.metric("Latencia Inferencia", f"{status_data.get('inference_latency_ms', 0)} ms")
                st.metric("Dispositivo OpenVINO", status_data.get('openvino_device', 'CPU'))
                st.metric("Cámara Inferencia", status_data.get('active_inference', 'Ninguna'))
                
                telemetry = status_data.get('telemetry', {})
                st.write("**Detalles del Objetivo:**")
                st.json(telemetry)
        except Exception:
            st.info("Conectando con la API para obtener telemetría...")

with tab_enrolamiento:
    st.subheader("Alta de Nuevo Personal")
    st.markdown("Ingresa los datos y captura o sube una foto para enrolar a la persona en la base de datos biométrica.")
    col_form, col_list = st.columns([1, 1])

    with col_form:
        with st.form("enroll_form", clear_on_submit=True):
            e_name = st.text_input("Nombre Completo *")
            e_dni = st.text_input("DNI o Identificador *")
            e_role = st.selectbox("Rol", ["Usuario", "Empleado", "VIP", "Seguridad", "Militar"])
            capture_method = st.radio("Método de captura", ["Cámara Web", "Subir Foto local"], horizontal=True)
            
            e_file = None
            e_camera = None
            if capture_method == "Subir Foto local":
                e_file = st.file_uploader("Selecciona una foto clara del rostro", type=["jpg", "jpeg", "png"])
            else:
                e_camera = st.camera_input("Tómate una foto de frente")

            submitted = st.form_submit_button("Registrar Persona")

        if submitted:
            if not e_name or not e_dni:
                st.error("El nombre y DNI son obligatorios.")
            elif capture_method == "Cámara Web" and e_camera is None:
                st.error("Por favor, tómate una foto con la cámara.")
            elif capture_method == "Subir Foto local" and e_file is None:
                st.error("Por favor, selecciona un archivo de imagen.")
            else:
                try:
                    if capture_method == "Cámara Web" and e_camera is not None:
                        bytes_data = e_camera.getvalue()
                        b64_data = base64.b64encode(bytes_data).decode()
                        payload = {"name": e_name, "dni": e_dni, "role": e_role, "image_b64": b64_data}
                        res = requests.post(f"{FASTAPI_URL}/api/faces/enroll_b64", json=payload, headers=HEADERS, timeout=5)
                    else:
                        files = {"file": (e_file.name, e_file, e_file.type)}
                        data = {"name": e_name, "dni": e_dni, "role": e_role}
                        res = requests.post(f"{FASTAPI_URL}/api/faces/enroll", params=data, files=files, headers=HEADERS, timeout=5)

                    if res.status_code == 200:
                        st.success(f"Persona enrolada correctamente: {e_name}")
                    else:
                        st.error(f"Error al enrolar: {res.json().get('detail', 'Desconocido')}")
                except Exception as e:
                    st.error(f"Error de conexión con la API: {e}")

    with col_list:
        st.subheader("Personal Registrado")
        if st.button("Actualizar Lista"):
            st.rerun()
            
        try:
            res = requests.get(f"{FASTAPI_URL}/api/faces/list", timeout=2)
            if res.status_code == 200:
                persons = res.json().get("persons", [])
                if not persons:
                    st.info("No hay personal enrolado actualmente.")
                else:
                    for p in persons:
                        with st.expander(f"{p['name']} (DNI: {p['dni']}) - {p['role']}"):
                            st.write(f"**Registrado el:** {p.get('created_at', 'N/A')}")
                            if st.button(f"Eliminar a {p['name']}", key=f"del_{p.get('id', p['dni'])}"):
                                try:
                                    del_res = requests.delete(f"{FASTAPI_URL}/api/faces/{p.get('id', p['dni'])}", headers=HEADERS, timeout=2)
                                    if del_res.status_code == 200:
                                        st.success(f"{p['name']} eliminado exitosamente.")
                                        st.rerun()
                                    else:
                                        st.error("Error al eliminar el registro.")
                                except Exception as e:
                                    st.error(f"Error de red: {e}")
            else:
                st.warning("No se pudo obtener la lista de personal.")
        except Exception:
            st.warning("Esperando conexión con la API...")

with tab_registro:
    col_reg1, col_reg2 = st.columns([4, 1])
    with col_reg1:
        st.subheader("Historial de Detecciones e Identificaciones (Caché Local)")
        st.markdown("Historial temporal de eventos generados por este nodo.")
    with col_reg2:
        if st.button("Vaciar Historial Local"):
            try:
                res = requests.delete(f"{FASTAPI_URL}/api/logs", timeout=2)
                if res.status_code == 200:
                    st.success("Historial vaciado.")
                    st.rerun()
            except Exception:
                st.error("Error al vaciar historial.")

    if st.button("Actualizar Historial", key="btn_refresh_logs"):
        st.rerun()

    try:
        res = requests.get(f"{FASTAPI_URL}/api/logs", timeout=2)
        if res.status_code == 200:
            logs = res.json()
            if not logs:
                st.info("Aún no hay registros de detecciones.")
            else:
                cols = st.columns(3)
                for i, log in enumerate(logs):
                    with cols[i % 3]:
                        st.markdown(f"**Hora:** {log.get('timestamp')} - **Cámara:** {log.get('camera_id', 'N/A')}")
                        status = log.get('status', 'Desconocido')
                        name = log.get('name', 'Desconocido')
                        if status == "No Registrado":
                            st.error(f"{name} ({status})")
                        else:
                            st.success(f"{name} ({status})")
                        
                        img_b64 = log.get("image")
                        if img_b64:
                            st.image(img_b64, use_container_width=True)
                        st.markdown("---")
        else:
            st.warning("No se pudo obtener el historial de registros.")
    except Exception:
        st.warning("Esperando conexión con la API...")
