import streamlit as st
import pandas as pd
import json
import base64
from sqlalchemy.orm import Session
import os
import sys

# Add parent directory to path to import database
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from database import SessionLocal, LogEvent

st.set_page_config(page_title="Central Server - Dashboard", layout="wide")
st.title("Monitoreo Centralizado de Cámaras")
st.markdown("Visualiza y gestiona los reportes de múltiples nodos en tiempo real.")

col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 1])
with col_btn1:
    if st.button("Actualizar Historial", key="refresh"):
        st.rerun()
with col_btn2:
    if st.button("Wipe Database (Borrar Todo)", type="primary", key="wipe"):
        with SessionLocal() as db:
            try:
                db.query(LogEvent).delete()
                db.commit()
                st.success("Base de datos borrada con éxito.")
                st.rerun()
            except Exception as e:
                db.rollback()
                st.error(f"Error: {e}")
with col_btn3:
    auto_refresh = st.checkbox("Auto-actualizar (cada 3s)", value=True)

# Consultar siempre con una sesión nueva para evitar caché de datos viejos
with SessionLocal() as db:
    logs = db.query(LogEvent).order_by(LogEvent.timestamp.desc()).limit(100).all()

if not logs:
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
    df = pd.DataFrame(data)
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Eventos", len(logs))
    col2.metric("Persona (Biometría)", len(df[df["Tipo Evento"] == "Persona"]) if not df.empty else 0)
    col3.metric("Entrada Vehicular", len(df[df["Tipo Evento"] == "Vehículo"]) if not df.empty else 0)
    col4.metric("Nodos Activos", df["Cámara"].nunique() if not df.empty else 0)
    
    st.subheader("Registro Centralizado de Eventos (Edge Computing - Personas & Vehículos)")
    st.dataframe(df, use_container_width=True)

if auto_refresh:
    import time
    time.sleep(3)
    st.rerun()
