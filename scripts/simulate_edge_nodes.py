import time
import random
import argparse
import requests
import sys

# Lista de cámaras / puestos simulados
SIMULATED_NODES = [
    {"camera_id": "Puesto_01_Acceso_Principal", "type": "Persona"},
    {"camera_id": "Puesto_02_Estacionamiento_Sur", "type": "Vehículo"},
    {"camera_id": "Puesto_03_Recepcion_VIP", "type": "Persona"},
    {"camera_id": "Puesto_04_Control_Barrera", "type": "Vehículo"},
    {"camera_id": "Puesto_05_Perimetro_Norte", "type": "Persona"},
    {"camera_id": "Puesto_06_Carga_Descarga", "type": "Vehículo"},
]

NAMES_DB = [
    ("Juan Pérez", "Empleado"),
    ("María González", "Gerencia"),
    ("Carlos Rodríguez", "Seguridad"),
    ("Ana Martínez", "Visitante"),
    ("Luis Fernández", "Empleado"),
    ("Desconocido", "No Registrado")
]

VEHICLES_DB = [
    "Auto Sedán",
    "Camioneta SUV",
    "Motocicleta",
    "Camión de Carga",
    "Colectivo / Bus"
]

def run_simulation(server_url: str, num_nodes: int, interval_sec: float):
    print("=" * 65)
    print(f"🚀 INICIANDO SIMULADOR DE NODOS EDGE MULTICÁMARA")
    print(f"📡 Servidor Central: {server_url}")
    print(f"🎥 Nodos/Cámaras Activas: {num_nodes}")
    print(f"⏱️ Frecuencia de envío: 1 evento cada ~{interval_sec} segundos")
    print("=" * 65)
    print("Presiona Ctrl+C para detener la simulación en cualquier momento.\n")

    active_nodes = SIMULATED_NODES[:num_nodes]
    counter = 0

    try:
        while True:
            node = random.choice(active_nodes)
            
            if node["type"] == "Persona" or random.random() > 0.5:
                person_name, role = random.choice(NAMES_DB)
                payload = {
                    "camera_id": node["camera_id"],
                    "person_name": person_name,
                    "role": role,
                    "event_type": "Persona"
                }
            else:
                vehicle = random.choice(VEHICLES_DB)
                payload = {
                    "camera_id": node["camera_id"],
                    "person_name": f"Vehículo: {vehicle}",
                    "role": "Entrada Vehicular",
                    "event_type": "Vehículo"
                }

            try:
                res = requests.post(f"{server_url}/api/report_log", json=payload, timeout=3.0)
                if res.status_code == 200:
                    counter += 1
                    print(f"[{time.strftime('%H:%M:%S')}] ✅ Evento #{counter} | {node['camera_id']} ➔ {payload['person_name']} ({payload['role']})")
                else:
                    print(f"[{time.strftime('%H:%M:%S')}] ⚠️ Error Servidor HTTP {res.status_code}")
            except Exception as e:
                print(f"[{time.strftime('%H:%M:%S')}] ❌ Servidor Inaccesible: {e}")

            time.sleep(random.uniform(interval_sec * 0.7, interval_sec * 1.3))

    except KeyboardInterrupt:
        print("\n\n🛑 Simulación finalizada por el usuario.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Simulador de Nodos Edge Multicámara")
    parser.add_argument("--url", default="http://localhost:8082", help="URL del servidor central")
    parser.add_argument("--nodes", type=int, default=4, help="Número de cámaras/puestos a simular (max 6)")
    parser.add_argument("--interval", type=float, default=2.5, help="Intervalo promedio entre eventos (segundos)")
    
    args = parser.parse_args()
    run_simulation(args.url, min(6, max(1, args.nodes)), args.interval)
