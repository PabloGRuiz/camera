import streamlit as st
import pandas as pd
import json
import base64
from sqlalchemy.orm import Session
import os
import sys

# Add parent directory to path to import database
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from database import SessionLocal, LogEvent, RegisteredNode
from datetime import datetime

st.set_page_config(page_title="Central Server - Dashboard", layout="wide")
st.title("Monitoreo Centralizado de Cámaras & Nodos Remotos")
st.markdown("Visualiza y gestiona los reportes de múltiples nodos en tiempo real con monitoreo continuo de red (Heartbeat).")

col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 1])
with col_btn1:
    if st.button("Actualizar Historial", key="refresh"):
        st.rerun()
with col_btn2:
    if st.button("Wipe Database (Borrar Todo)", type="primary", key="wipe"):
        with SessionLocal() as db:
            try:
                db.query(LogEvent).delete()
                db.query(RegisteredNode).delete()
                db.commit()
                st.success("Base de datos borrada con éxito.")
                st.rerun()
            except Exception as e:
                db.rollback()
                st.error(f"Error: {e}")
with col_btn3:
    auto_refresh = st.checkbox("Auto-actualizar (cada 3s)", value=True)

# Tabs Principales
tab_nodes, tab_logs = st.tabs(["🟢 Salud de Nodos Remotos & Red (Heartbeat)", "📋 Historial Centralizado de Eventos"])

with SessionLocal() as db:
    # 1. Datos de Nodos
    registered_nodes = db.query(RegisteredNode).all()
    now_dt = datetime.now()
    nodes_data = []
    online_count = 0
    offline_count = 0
    syncing_count = 0

    for n in registered_nodes:
        diff_sec = (now_dt - n.last_seen).total_seconds()
        calc_status = "🟢 ONLINE" if diff_sec <= 30 else "🔴 OFFLINE"
        if calc_status == "🟢 ONLINE" and (n.pending_logs_count or 0) > 0:
            calc_status = "🟡 SYNCING"
        
        if "ONLINE" in calc_status: online_count += 1
        elif "SYNCING" in calc_status: syncing_count += 1
        else: offline_count += 1

        nodes_data.append({
            "Nodo ID": n.node_id,
            "Nombre / Ubicación": n.node_name,
            "Estado": calc_status,
            "Última Respuesta": n.last_seen.strftime("%Y-%m-%d %H:%M:%S"),
            "Seg. Transcurridos": int(diff_sec),
            "FPS Inferencia": round(n.current_fps or 0.0, 1),
            "Latencia (ms)": round(n.inference_latency_ms or 0.0, 1),
            "Eventos en Cola": n.pending_logs_count or 0,
            "IP Nodo": n.ip_address or "Local"
        })

    # 2. Datos de Logs
    total_count = db.query(LogEvent).count()
    persona_count = db.query(LogEvent).filter((LogEvent.event_type == 'Persona') | (LogEvent.event_type.is_(None))).count()
    vehiculo_count = db.query(LogEvent).filter(LogEvent.event_type == 'Vehículo').count()
    
    limit_val = st.sidebar.selectbox("Límite de Registros a Mostrar", [100, 200, 500, 1000, 5000], index=2)
    logs = db.query(LogEvent).order_by(LogEvent.timestamp.desc()).limit(limit_val).all()

with tab_nodes:
    st.subheader("Estado e Integridad de Nodos Conectados")
    col1_n, col2_n, col3_n, col4_n = st.columns(4)
    col1_n.metric("Total Nodos Registrados", len(registered_nodes))
    col2_n.metric("🟢 En Línea (Online)", online_count)
    col3_n.metric("🟡 Sincronizando Cola", syncing_count)
    col4_n.metric("🔴 Caídos / Offline", offline_count)

    if not nodes_data:
        st.info("No hay nodos remotos registrados aún. Ejecuta `install_remote_node.bat` o arranca un cliente remoto.")
    else:
        df_nodes = pd.DataFrame(nodes_data)
        st.dataframe(df_nodes, use_container_width=True)

with tab_logs:
    if total_count == 0:
        st.info("No hay registros en la base de datos central.")
    else:
        data = []
        for log in logs:
            ev_type = getattr(log, "event_type", "Persona") or "Persona"
            data.append({
                "ID": log.id,
                "Fecha/Hora": log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "Tipo Evento": ev_type,
                "Cámara": log.camera_id,
                "Sujeto / Detalle": log.person_name,
                "Rol / Estado": log.role,
            })
        df_logs = pd.DataFrame(data)
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Eventos en BD", total_count)
        col2.metric("Persona (Biometría)", persona_count)
        col3.metric("Entrada Vehicular", vehiculo_count)
        col4.metric("Nodos Activos", len(set(d["Cámara"] for d in data)) if data else 0)
        
        st.subheader(f"Registro Centralizado de Eventos (Mostrando últimos {len(df_logs)} de {total_count})")
        st.dataframe(df_logs, use_container_width=True)

if auto_refresh:
    import time
    time.sleep(3)
    st.rerun()
