# Matemáticas del Seguimiento Cinematográfico y Optimización

Este documento describe las mejoras algorítmicas implementadas en el sistema de Object-Centered Tracking y Auto-Framing para lograr un rendimiento superior ("Production-Ready") y movimientos de cámara similares a los de un operador PTZ profesional.

## 1. Cinematic Damping (Modelo de Resorte Amortiguado)

Anteriormente, el sistema utilizaba un filtro de Media Móvil Exponencial (EMA) simple para suavizar los movimientos del encuadre. Aunque efectivo, el EMA tiende a sentirse "robótico" y presenta un retraso (lag) lineal y constante.

Para lograr un movimiento "cinematográfico", se ha reemplazado el EMA por un **Modelo Físico de Resorte Amortiguado (Damped Spring System)** integrado mediante el método de Euler.

### Ecuaciones del Sistema

El objetivo actúa como un "ancla" y la cámara está unida a él mediante un resorte invisible. 
La aceleración $a$ de la cámara es proporcional a la distancia hacia el objetivo (Ley de Hooke):

$$ a_{cx} = (Target_{cx} - Camera_{cx}) \times k $$

Donde:
- $k$ es la constante de rigidez del resorte (Stiffness), mapeada a partir de la variable `ema_alpha` ($\approx 0.4 \times ema\_alpha$).

Para evitar oscilaciones infinitas alrededor del objetivo (efecto péndulo), se introduce una fricción o amortiguación (Damping $d = 0.85$):

$$ v_{cx} = (v_{cx} + a_{cx}) \times d $$
$$ Camera_{cx} = Camera_{cx} + v_{cx} $$

Este modelo produce curvas S (S-curves) muy suaves: la cámara acelera paulatinamente cuando el sujeto se mueve rápido y frena suavemente al acercarse a él, eliminando la vibración del bounding box y los movimientos bruscos.

## 2. Extrapolación de Velocidad Lineal (O(1) Frame-Skipping)

Para maximizar los FPS, el sistema implementa la técnica de `FRAME_SKIP` (iniciar inferencia de YOLO/ByteTrack solo 1 de cada N cuadros). Anteriormente, se utilizaban los rastreadores rápidos de OpenCV (como KCF) para los cuadros intermedios.

Sin embargo, inicializar `cv2.TrackerKCF_create()` por cada objeto en cada cuadro de inferencia agregaba un overhead considerable (aproximadamente 10-15 ms extra por ID detectado), colapsando la CPU cuando había múltiples personas.

### Solución: Extrapolación Cinemática Básica

Como los saltos de cuadro suelen ser muy pequeños (e.g. 1-3 frames), el movimiento del sujeto puede modelarse como rectilíneo uniforme entre inferencias.
Al detectar un objeto, se calcula su vector de velocidad espacial respecto a su detección previa:

$$ V_x = \frac{x_{actual} - x_{anterior}}{\Delta frames} $$

En los cuadros saltados, simplemente sumamos el vector de velocidad al bounding box. Esto tiene una complejidad computacional de $O(1)$ por rastreo y un costo nulo de inicialización, incrementando dramáticamente el rendimiento del bucle principal, especialmente en dispositivos Edge y CPUs.

## 3. Cacheo Asíncrono Biométrico

El módulo de reconocimiento facial (YuNet + SFace) ejecutaba la inferencia de manera síncrona por cada persona en el encuadre repetidamente, provocando caídas a 0 FPS o congelamientos del motor MJPEG. 

Se introdujo un sistema de **Caché Temporal de Identidad** (basado en el `track_id` persistente de ByteTrack). Una vez que la red SFace identifica exitosamente a un sujeto (`similarity > threshold`), se asocia la métrica a la ID en el hilo principal y se omite la costosa reevaluación biométrica en los fotogramas subsiguientes.
