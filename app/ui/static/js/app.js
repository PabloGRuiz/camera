document.addEventListener('DOMContentLoaded', () => {
  const videoFeed = document.getElementById('videoFeed');
  const modeBtns = document.querySelectorAll('.mode-btn');

  // Sliders e Inputs
  const emaSlider = document.getElementById('emaSlider');
  const emaValue = document.getElementById('emaValue');
  const paddingSlider = document.getElementById('paddingSlider');
  const paddingValue = document.getElementById('paddingValue');
  const targetIdInput = document.getElementById('targetIdInput');
  const aspectRatioSelect = document.getElementById('aspectRatioSelect');
  const overlayCheckbox = document.getElementById('overlayCheckbox');
  const targetCategorySelect = document.getElementById('targetCategorySelect');

  // Elementos de telemetría
  const fpsStat = document.getElementById('fpsStat');
  const latencyStat = document.getElementById('latencyStat');
  const targetIdStat = document.getElementById('targetIdStat');
  const deviceStat = document.getElementById('deviceStat');

  // Elementos de Webcam Navegador y PiP
  const webcamToggleBtn = document.getElementById('webcamToggleBtn');
  const scanToggleBtn = document.getElementById('scanToggleBtn');
  const pipToggleBtn = document.getElementById('pipToggleBtn');
  const webcamVideo = document.getElementById('webcamVideo');
  const webcamCanvas = document.getElementById('webcamCanvas');
  const pipVideo = document.getElementById('pipVideo');
  const pipCanvas = document.getElementById('pipCanvas');
  const pipCtx = pipCanvas ? pipCanvas.getContext('2d') : null;
  
  let isWebcamActive = false;
  let webcamStream = null;
  let webcamLoopActive = false;
  let isProcessingFrame = false;
  let isDetectionPaused = false;
  let currentMode = 'framed';

  // Renderizador continuo para canal de Picture-in-Picture
  function renderPiPFrame() {
    if (pipCanvas && pipCtx) {
      const sourceImg = (outputCanvas && outputCanvas.style.display !== 'none') ? outputCanvas : videoFeed;
      if (sourceImg && (sourceImg.naturalWidth || sourceImg.width || sourceImg.videoWidth)) {
        const w = sourceImg.naturalWidth || sourceImg.width || 1280;
        const h = sourceImg.naturalHeight || sourceImg.height || 720;
        if (w > 0 && h > 0) {
          if (pipCanvas.width !== w || pipCanvas.height !== h) {
            pipCanvas.width = w;
            pipCanvas.height = h;
          }
          try {
            pipCtx.drawImage(sourceImg, 0, 0, w, h);
          } catch (e) {}
        }
      }
    }
    requestAnimationFrame(renderPiPFrame);
  }
  requestAnimationFrame(renderPiPFrame);

  const outputCanvas = document.getElementById('outputCanvas');

  // Actualizar URL del video stream (Servidor MJPEG)
  function updateStreamUrl() {
    if (outputCanvas) outputCanvas.style.display = 'none';
    if (videoFeed) videoFeed.style.display = 'block';
    videoFeed.src = `/video_feed?mode=${currentMode}&t=${Date.now()}`;
  }

  // Iniciar / Detener Webcam del Navegador
  if (webcamToggleBtn) {
    webcamToggleBtn.addEventListener('click', async () => {
      if (!isWebcamActive) {
        try {
          webcamStream = await navigator.mediaDevices.getUserMedia({
            video: { width: { ideal: 1280 }, height: { ideal: 720 } }
          });
          webcamVideo.srcObject = webcamStream;
          await webcamVideo.play();
          await new Promise(r => setTimeout(r, 200));

          isWebcamActive = true;
          if (videoFeed) videoFeed.style.display = 'block';
          if (outputCanvas) outputCanvas.style.display = 'none';

          webcamToggleBtn.classList.add('active');
          webcamToggleBtn.textContent = '⏹️ Detener Webcam';
          
          updateStreamUrl();
          startWebcamLoop();
        } catch (err) {
          alert('No se pudo acceder a la webcam del navegador: ' + err.message);
          console.error('Error accediendo a getUserMedia:', err);
        }
      } else {
        stopWebcam();
      }
    });
  }

  function stopWebcam() {
    isWebcamActive = false;
    webcamLoopActive = false;
    if (webcamStream) {
      webcamStream.getTracks().forEach(track => track.stop());
      webcamStream = null;
    }
    if (webcamToggleBtn) {
      webcamToggleBtn.classList.remove('active');
      webcamToggleBtn.textContent = '📷 Activar Webcam Navegador';
    }
    if (outputCanvas) outputCanvas.style.display = 'none';
    if (videoFeed) videoFeed.style.display = 'block';
    updateStreamUrl();
  }

  async function startWebcamLoop() {
    webcamLoopActive = true;
    const ctx = webcamCanvas.getContext('2d');

    while (webcamLoopActive && isWebcamActive) {
      const vw = webcamVideo.videoWidth || 1280;
      const vh = webcamVideo.videoHeight || 720;

      if (!isProcessingFrame && (webcamVideo.readyState >= 2 || vw > 0)) {
        isProcessingFrame = true;
        
        webcamCanvas.width = vw;
        webcamCanvas.height = vh;
        ctx.drawImage(webcamVideo, 0, 0, vw, vh);

        webcamCanvas.toBlob(async (blob) => {
          if (!blob || !isWebcamActive) {
            isProcessingFrame = false;
            return;
          }

          const formData = new FormData();
          formData.append('file', blob, 'frame.jpg');

          try {
            const res = await fetch('/api/webcam_frame', {
              method: 'POST',
              body: formData
            });
          } catch (err) {
            console.warn('Error enviando fotograma a webcam_frame:', err);
          } finally {
            isProcessingFrame = false;
          }
        }, 'image/jpeg', 0.85);
      }
      await new Promise(r => setTimeout(r, 40)); // Loop ~25 FPS en segundo plano
    }
  }

  // Cambio de modo de visualización (Framed, Annotated, Dual)
  modeBtns.forEach(btn => {
    btn.addEventListener('click', (e) => {
      modeBtns.forEach(b => b.classList.remove('active'));
      e.target.classList.add('active');
      currentMode = e.target.getAttribute('data-mode');
      isProcessingFrame = false; // Permitir procesamiento inmediato con el nuevo modo
      updateStreamUrl();
    });
  });

  if (targetCategorySelect) {
    targetCategorySelect.addEventListener('change', () => {
      isProcessingFrame = false;
      postSettings();
    });
  }

  if (scanToggleBtn) {
    scanToggleBtn.addEventListener('click', () => {
      isDetectionPaused = !isDetectionPaused;
      if (isDetectionPaused) {
        scanToggleBtn.textContent = '⏸️ Escáner IA: Pausado';
        scanToggleBtn.style.background = '#e74c3c';
      } else {
        scanToggleBtn.textContent = '⚡ Escáner IA: Activo';
        scanToggleBtn.style.background = '#2ecc71';
      }
      postSettings();
    });
  }

  // Modo Picture-in-Picture (Ventana Flotante / Ventana Aparte)
  if (pipToggleBtn && pipVideo && pipCanvas) {
    pipToggleBtn.addEventListener('click', async () => {
      try {
        if (document.pictureInPictureElement) {
          await document.exitPictureInPicture();
        } else {
          if (!pipVideo.srcObject) {
            const stream = pipCanvas.captureStream(30);
            pipVideo.srcObject = stream;
          }
          await pipVideo.play();
          await pipVideo.requestPictureInPicture();
        }
      } catch (err) {
        console.error('Error al activar Modo Picture-in-Picture:', err);
        alert('Modo Ventana Flotante (PiP) no soportado o bloqueado por el navegador.');
      }
    });

    pipVideo.addEventListener('enterpictureinpicture', () => {
      pipToggleBtn.textContent = '🗗 Salir de Flotante (PiP)';
      pipToggleBtn.style.background = '#8e44ad';
    });

    pipVideo.addEventListener('leavepictureinpicture', () => {
      pipToggleBtn.textContent = '🖼️ Flotante (PiP)';
      pipToggleBtn.style.background = '#9b59b6';
    });
  }

  // Apertura de Ventanas Flotantes Popout Independientes para cada vista
  const openDetectorPopoutBtn = document.getElementById('openDetectorPopoutBtn');
  const openFramedPopoutBtn = document.getElementById('openFramedPopoutBtn');

  if (openDetectorPopoutBtn) {
    openDetectorPopoutBtn.addEventListener('click', () => {
      window.open('/video_feed?mode=annotated', 'VistaDetectorPopout', 'width=850,height=500,resizable=yes,scrollbars=no');
    });
  }

  if (openFramedPopoutBtn) {
    openFramedPopoutBtn.addEventListener('click', () => {
      window.open('/video_feed?mode=framed', 'VistaEncuadrePopout', 'width=850,height=500,resizable=yes,scrollbars=no');
    });
  }

  // Enviar actualización de parámetros al servidor
  async function postSettings() {
    const payload = {
      ema_alpha: parseFloat(emaSlider.value),
      padding: parseFloat(paddingSlider.value) / 100.0,
      target_id: parseInt(targetIdInput.value) || -1,
      aspect_ratio: aspectRatioSelect.value,
      draw_overlays: overlayCheckbox.checked,
      target_category: targetCategorySelect ? targetCategorySelect.value : 'ALL',
      detection_paused: isDetectionPaused
    };

    try {
      const response = await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (!response.ok) {
        console.warn('Error al actualizar ajustes en el servidor');
      }
    } catch (err) {
      console.error('Error de red al actualizar ajustes:', err);
    }
  }

  // Event Listeners para sliders e inputs
  emaSlider.addEventListener('input', (e) => {
    emaValue.textContent = parseFloat(e.target.value).toFixed(2);
    postSettings();
  });

  paddingSlider.addEventListener('input', (e) => {
    paddingValue.textContent = `${e.target.value}%`;
    postSettings();
  });

  targetIdInput.addEventListener('change', () => {
    postSettings();
  });

  aspectRatioSelect.addEventListener('change', () => {
    postSettings();
  });

  overlayCheckbox.addEventListener('change', () => {
    postSettings();
  });

  // Polling de Telemetría cada 1 segundo
  async function fetchStatus() {
    try {
      const res = await fetch('/api/status');
      if (res.ok) {
        const data = await res.json();
        fpsStat.textContent = `${data.fps} FPS`;
        latencyStat.textContent = `${data.inference_latency_ms} ms`;
        deviceStat.textContent = data.openvino_device || 'CPU';
        
        const activeTarget = data.telemetry?.active_target_id;
        targetIdStat.textContent = activeTarget ? `ID #${activeTarget}` : 'Auto';
      }
    } catch (err) {
      console.warn('Error obteniendo estado:', err);
    }
  }

  setInterval(fetchStatus, 1000);
  fetchStatus();
});
