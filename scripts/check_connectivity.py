import sys
import os
import json
import time
import urllib.request
import urllib.parse
import socket

def main():
    print("=" * 65)
    print("  HERRAMIENTA DE DIAGNÓSTICO Y VERIFICACIÓN DE RED (EDGE NODE)")
    print("=" * 65)
    
    server_url = input("Ingresa la URL o IP del Servidor Central [ej. http://192.168.1.100:8082]: ").strip()
    if not server_url:
        server_url = "http://localhost:8082"
        
    if not server_url.startswith("http://") and not server_url.startswith("https://"):
        server_url = f"http://{server_url}"
        
    node_id = input("Ingresa el ID único para este Nodo [ej. NODE-SUCURSAL-ROSARIO-01]: ").strip() or "NODE-TEST-01"
    node_name = input("Ingresa el Nombre/Ubicación legible [ej. Sucursal Rosario]: ").strip() or "Nodo de Prueba"
    
    print("\n[1/3] Verificando resolución de host y puerto...")
    try:
        parsed = urllib.parse.urlparse(server_url)
        hostname = parsed.hostname or "localhost"
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(4.0)
        result = sock.connect_ex((hostname, port))
        sock.close()
        
        if result == 0:
            print(f"  --> [OK] Conexión de Socket exitosa hacia {hostname}:{port}")
        else:
            print(f"  --> [ERROR] No se pudo abrir conexión de socket con {hostname}:{port} (Código: {result})")
            print("      Verifica el Firewall de Windows o que el Servidor Central esté encendido.")
            input("\nPresiona ENTER para salir...")
            sys.exit(1)
    except Exception as e:
        print(f"  --> [ERROR] Fallo en verificación de socket: {e}")
        input("\nPresiona ENTER para salir...")
        sys.exit(1)

    print("\n[2/3] Probando Handshake API con el Servidor Central...")
    try:
        reg_url = f"{server_url}/api/nodes/register"
        payload = json.dumps({
            "node_id": node_id,
            "node_name": node_name,
            "active_cameras_count": 1
        }).encode("utf-8")
        
        req = urllib.request.Request(reg_url, data=payload, headers={"Content-Type": "application/json"})
        start_t = time.time()
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            latency = (time.time() - start_t) * 1000.0
            resp_data = json.loads(resp.read().decode())
            print(f"  --> [OK] Registro de Handshake exitoso ({int(latency)} ms latencia HTTP)")
            print(f"      Respuesta del servidor: {resp_data}")
    except Exception as e:
        print(f"  --> [ERROR] Falló la petición HTTP de registro: {e}")
        input("\nPresiona ENTER para salir...")
        sys.exit(1)

    print("\n[3/3] Probando envío de Heartbeat (Latido de Salud)...")
    try:
        hb_url = f"{server_url}/api/nodes/heartbeat"
        hb_payload = json.dumps({
            "node_id": node_id,
            "current_fps": 30.0,
            "inference_latency_ms": 12.5,
            "pending_logs_count": 0,
            "active_cameras_count": 1
        }).encode("utf-8")
        
        req_hb = urllib.request.Request(hb_url, data=hb_payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req_hb, timeout=5.0) as resp:
            hb_resp = json.loads(resp.read().decode())
            print(f"  --> [OK] Heartbeat enviado con éxito: {hb_resp}")
    except Exception as e:
        print(f"  --> [ADVERTENCIA] No se pudo enviar el latido de prueba: {e}")

    print("\n" + "=" * 65)
    print("  ¡DIAGNÓSTICO COMPLETADO CON ÉXITO!")
    print(f"  Este nodo ({node_id}) está listo para transmitir al Servidor Central.")
    print("=" * 65)
    
    # Escribir o actualizar node_config.json
    config_data = {
        "CENTRAL_SERVER_URL": server_url,
        "NODE_ID": node_id,
        "NODE_NAME": node_name,
        "HEARTBEAT_INTERVAL": 10
    }
    with open("node_config.json", "w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=4, ensure_ascii=False)
        
    print(f"\n[INFO] Archivo de configuración generado: 'node_config.json'")

if __name__ == "__main__":
    main()
