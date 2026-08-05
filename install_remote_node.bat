@echo off
title INSTALADOR Y CONFIGURADOR DE NODO REMOTO (EDGE COMPUTE)
color 0A

echo ======================================================================
echo    INSTALADOR DE NODO REMOTO - SISTEMA DE SEGUIMIENTO E IA
echo ======================================================================
echo.
echo Este asistente guiado configurara la conexion entre esta maquina (Nodo)
echo y el Servidor Central de Monitoreo.
echo.

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python no esta instalado o no se encuentra en el PATH.
    echo Por favor instala Python 3.10+ o ejecuta la version portable Docker.
    pause
    exit /b 1
)

echo Ejecutando diagnostico y prueba de conectividad con el Servidor Central...
echo.
python scripts\check_connectivity.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] La verificacion de red no paso la prueba. Revise los mensajes arriba.
    pause
    exit /b 1
)

echo.
echo ======================================================================
echo    ¡CONFIGURACION DE NODO COMPLETADA EXITOSAMENTE!
echo ======================================================================
echo.
echo Iniciando aplicacion local en 3 segundos...
timeout /t 3 /nobreak >nul

python -m uvicorn app.api.routes:router --host 0.0.0.0 --port 8081
pause
