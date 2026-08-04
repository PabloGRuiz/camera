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
            selected_view_cams = st.sidebar.multiselect("Cámaras para Visualizar", cameras, default=cameras[:1])
            
            fixed_selection = st.sidebar.selectbox("Fijar Inferencia en Cámara (Opcional)", ["Ninguna"] + cameras, index=0 if not fixed_camera else cameras.index(fixed_camera) + 1)
            
            if st.sidebar.button("Aplicar Fijación de Cámara"):
                fix_cam = None if fixed_selection == "Ninguna" else fixed_selection
                requests.post(f"{FASTAPI_URL}/api/camera/control", json={"action": "fix", "camera_id": fix_cam}, headers=HEADERS, timeout=2)
                st.sidebar.success("Configuración aplicada")
                st.rerun()
        else:
            selected_view_cams = []
            st.sidebar.warning("No hay cámaras conectadas.")

        st.sidebar.markdown("---")
        with st.sidebar.expander("➕ Añadir / Nombrar Cámara", expanded=False):
            new_cam_id = st.text_input("Nombre / Alias de Cámara", value="Camara_Extra")
            source_type = st.selectbox("Origen de Video", ["Cámara Web Local", "URL RTSP / IP", "Archivo MP4 Local"])
            
            if source_type == "Cámara Web Local":
                cam_index = st.number_input("Índice de Cámara (0=Frontal, 1=Webcam, etc.)", min_value=0, max_value=10, value=0, step=1)
                default_src = str(cam_index)
            elif source_type == "URL RTSP / IP":
                default_src = "rtsp://admin:123456@192.168.1.100:554/stream1"
            else:
                default_src = "videos/sample.mp4"

            new_cam_source = st.text_input("Ruta / URL del Origen", value=default_src)

            if st.button("Conectar Nueva Cámara"):
                if new_cam_id and new_cam_source:
                    try:
                        payload = {"action": "add", "camera_id": new_cam_id, "source": new_cam_source}
                        r = requests.post(f"{FASTAPI_URL}/api/camera/control", json=payload, headers=HEADERS, timeout=3)
                        if r.status_code == 200:
                            st.sidebar.success(f"Cámara '{new_cam_id}' añadida con éxito.")
                            st.rerun()
                        else:
                            st.sidebar.error("Error al añadir cámara.")
                    except Exception as ex:
                        st.sidebar.error(f"Error: {ex}")

        if cameras:
            with st.sidebar.expander("🗑️ Eliminar Cámara", expanded=False):
                cam_to_del = st.selectbox("Seleccionar para eliminar", cameras, key="sel_del_cam")
                if st.button("Eliminar Cámara Seleccionada"):
                    try:
                        r = requests.post(f"{FASTAPI_URL}/api/camera/control", json={"action": "remove", "camera_id": cam_to_del}, headers=HEADERS, timeout=3)
                        if r.status_code == 200:
                            st.sidebar.success(f"Cámara '{cam_to_del}' eliminada.")
                            st.rerun()
                    except Exception as ex:
                        st.sidebar.error(f"Error: {ex}")
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

# Filtro de Clases (Integrado en Streamlit)
st.sidebar.markdown("---")
st.sidebar.subheader("Filtro de Detección (Clases)")
class_options = {
    "Persona": 0, "Vehículo/Auto": 2, "Moto": 3, "Camión": 7,
    "TV": 62, "Laptop": 63, "Teléfono": 67, "Silla": 56
}
selected_classes_names = st.sidebar.multiselect(
    "Filtrar por Clase (Vacío = Detectar Todo)", 
    list(class_options.keys()), 
    default=["Persona"]
)
target_classes_ids = [class_options[name] for name in selected_classes_names] if selected_classes_names else [-1]

st.sidebar.markdown("---")
draw_overlays = st.sidebar.checkbox("Mostrar Overlays en Vista Previa", value=True)
mode = st.sidebar.radio("Modo de Transmisión", ["framed", "annotated", "dual"], index=0)

if st.sidebar.button("Aplicar Cambios en Vivo") and selected_view_cams:
    try:
        payload = {
            "ema_alpha": float(ema_alpha),
            "padding": float(padding) / 100.0,
            "aspect_ratio": aspect_ratio,
            "target_id": int(target_id),
            "draw_overlays": draw_overlays,
            "target_classes": target_classes_ids,
            "camera_id": selected_view_cams[0] if len(selected_view_cams) == 1 else None
        }
        res = requests.post(f"{FASTAPI_URL}/api/settings", json=payload, headers=HEADERS, timeout=2)
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
        if selected_view_cams:
            if len(selected_view_cams) == 1:
                stream_url = f"{PUBLIC_FASTAPI_URL}/video_feed?camera_id={selected_view_cams[0]}&mode={mode}"
                st.markdown(f'<img src="{stream_url}" width="100%" style="border-radius: 8px; border: 1px solid #444;" />', unsafe_allow_html=True)
            else:
                grid_cols = st.columns(2)
                for i, cam_id in enumerate(selected_view_cams):
                    with grid_cols[i % 2]:
                        st.markdown(f"**{cam_id}**")
                        stream_url = f"{PUBLIC_FASTAPI_URL}/video_feed?camera_id={cam_id}&mode={mode}"
                        st.markdown(f'<img src="{stream_url}" width="100%" style="border-radius: 8px; border: 1px solid #444;" />', unsafe_allow_html=True)
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
        capture_method = st.radio("Método de captura", ["Cámara Web (Rápido)", "Subir Foto local", "Face ID 3D (Multirrostro)"], horizontal=True, key="radio_enroll_method")
        
        with st.form("enroll_form", clear_on_submit=True):
            e_name = st.text_input("Nombre Completo *")
            e_dni = st.text_input("DNI o Identificador *")
            e_role = st.selectbox("Rol", ["Usuario", "Empleado", "VIP", "Seguridad", "Militar"])
            
            e_file = None
            e_camera = None
            if capture_method == "Subir Foto local":
                e_file = st.file_uploader("Selecciona una foto clara del rostro", type=["jpg", "jpeg", "png"])
                submitted = st.form_submit_button("Registrar Persona")
            elif capture_method == "Cámara Web (Rápido)":
                e_camera = st.camera_input("Tómate una foto de frente")
                submitted = st.form_submit_button("Registrar Persona")
            else:
                st.info("💡 **El Enrolamiento Face ID 3D (Multirrostro)** requiere acceso continuo a tu cámara para capturar 3 ángulos (Frente, Izquierda, Derecha).")
                st.markdown(f"👉 **[ABRIR PANEL WEB PRINCIPAL]({PUBLIC_FASTAPI_URL})** para utilizar el anillo biométrico avanzado.")
                submitted = st.form_submit_button("Registrar Persona", disabled=True)

        if submitted:
            if not e_name or not e_dni:
                st.error("El nombre y DNI son obligatorios.")
            elif capture_method == "Cámara Web (Rápido)" and e_camera is None:
                st.error("Por favor, tómate una foto con la cámara.")
            elif capture_method == "Subir Foto local" and e_file is None:
                st.error("Por favor, selecciona un archivo de imagen.")
            else:
                try:
                    if capture_method == "Cámara Web (Rápido)" and e_camera is not None:
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
        st.subheader("Historial de Capturas del Día (Almacenamiento Persistente SQLite)")
        st.markdown("Registro local continuo con imágenes almacenado en disco (`data/local_logs.db`).")
    with col_reg2:
        if st.button("Vaciar Historial Local"):
            try:
                res = requests.delete(f"{FASTAPI_URL}/api/logs", timeout=2)
                if res.status_code == 200:
                    st.success("Historial local vaciado.")
                    st.rerun()
            except Exception:
                st.error("Error al vaciar historial.")

    if st.button("Actualizar Capturas", key="btn_refresh_logs"):
        st.rerun()

    try:
        res = requests.get(f"{FASTAPI_URL}/api/logs?limit=200", timeout=3)
        if res.status_code == 200:
            logs = res.json()
            if not logs:
                st.info("Aún no hay capturas registradas en la base local.")
            else:
                st.metric("Total Capturas del Día (Persistente)", len(logs))
                cols = st.columns(3)
                for i, log in enumerate(logs):
                    with cols[i % 3]:
                        cam_id = log.get('camera_id', 'N/A')
                        ts = log.get('timestamp') or log.get('time', '')
                        dt = log.get('date', '')
                        st.markdown(f"**{dt} {ts}** | `{cam_id}`")
                        status = log.get('status', 'Desconocido')
                        name = log.get('name', 'Desconocido')
                        if status in ["No Registrado", "Desconocido"]:
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
