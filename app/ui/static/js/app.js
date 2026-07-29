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
          webcamToggleBtn.textContent = 'Detener Webcam';
          
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

  // Transmisión de Pantalla / Pestaña del Navegador (Screen Sharing)
  let isScreenShareActive = false;
  let screenStream = null;
  const screenShareToggleBtn = document.getElementById('screenShareToggleBtn');

  if (screenShareToggleBtn) {
    screenShareToggleBtn.addEventListener('click', async () => {
      if (!isScreenShareActive) {
        try {
          if (isWebcamActive) stopWebcam();

          screenStream = await navigator.mediaDevices.getDisplayMedia({
            video: { cursor: "always" },
            audio: false
          });

          webcamVideo.srcObject = screenStream;
          await webcamVideo.play();
          await new Promise(r => setTimeout(r, 200));

          isScreenShareActive = true;
          isWebcamActive = true;

          if (videoFeed) videoFeed.style.display = 'block';
          if (outputCanvas) outputCanvas.style.display = 'none';

          screenShareToggleBtn.classList.add('active');
          screenShareToggleBtn.textContent = 'Detener Transmisión Pantalla';

          // Detectar cuando el usuario presiona "Dejar de compartir" en la barra nativa del navegador
          screenStream.getVideoTracks()[0].addEventListener('ended', () => {
            stopScreenShare();
          });

          updateStreamUrl();
          startWebcamLoop();
        } catch (err) {
          if (err.name !== 'NotAllowedError') {
            alert('No se pudo compartir la pantalla: ' + err.message);
          }
          stopScreenShare();
        }
      } else {
        stopScreenShare();
      }
    });
  }

  function stopScreenShare() {
    isScreenShareActive = false;
    isWebcamActive = false;
    webcamLoopActive = false;
    if (screenStream) {
      screenStream.getTracks().forEach(track => track.stop());
      screenStream = null;
    }
    if (screenShareToggleBtn) {
      screenShareToggleBtn.classList.remove('active');
      screenShareToggleBtn.textContent = 'Transmitir Pantalla / Pestaña';
    }
    if (outputCanvas) outputCanvas.style.display = 'none';
    if (videoFeed) videoFeed.style.display = 'block';
    updateStreamUrl();
  }

  function stopWebcam() {
    isWebcamActive = false;
    webcamLoopActive = false;
    if (screenStream) {
      stopScreenShare();
    }
    if (webcamStream) {
      webcamStream.getTracks().forEach(track => track.stop());
      webcamStream = null;
    }
    if (webcamToggleBtn) {
      webcamToggleBtn.classList.remove('active');
      webcamToggleBtn.textContent = 'Activar Webcam Navegador';
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

  // --- LÓGICA DE ENROLAMIENTO FACIAL Y GESTIÓN ---
  const btnEnrollFace = document.getElementById('btnEnrollFace');
  const enrollName = document.getElementById('enrollName');
  const enrollDni = document.getElementById('enrollDni');
  const enrollRole = document.getElementById('enrollRole');
  const enrolledFacesList = document.getElementById('enrolledFacesList');

  async function loadEnrolledFaces() {
    if (!enrolledFacesList) return;
    try {
      const res = await fetch('/api/faces/list');
      if (res.ok) {
        const data = await res.json();
        enrolledFacesList.innerHTML = '';
        if (!data.persons || data.persons.length === 0) {
          enrolledFacesList.innerHTML = '<span style="font-size:0.75rem; color:var(--text-muted);">Sin personas registradas aún</span>';
          return;
        }

        data.persons.forEach(p => {
          const item = document.createElement('div');
          item.style.cssText = 'display:flex; justify-content:space-between; align-items:center; background:rgba(255,255,255,0.05); padding:6px 10px; border-radius:6px; font-size:0.8rem;';
          item.innerHTML = `
            <div>
              <strong style="color:#00ffe0;">${p.name}</strong> 
              <span style="color:var(--text-muted); font-size:0.75rem;">(DNI: ${p.dni} - ${p.role})</span>
            </div>
            <button class="btn-delete-face" data-id="${p.id}" style="background:#e74c3c; border:none; color:white; border-radius:4px; padding:2px 6px; cursor:pointer; font-size:0.7rem;">🗑️</button>
          `;
          enrolledFacesList.appendChild(item);
        });

        document.querySelectorAll('.btn-delete-face').forEach(btn => {
          btn.addEventListener('click', async (e) => {
            const id = e.target.getAttribute('data-id');
            if (confirm(`¿Eliminar la persona registrada ID #${id}?`)) {
              await fetch(`/api/faces/${id}`, { method: 'DELETE' });
              loadEnrolledFaces();
            }
          });
        });
      } else {
        enrolledFacesList.innerHTML = '<span style="font-size:0.75rem; color:var(--text-muted);">Sin personas registradas aún</span>';
      }
    } catch (err) {
      console.warn('Error cargando lista de rostros enrolados:', err);
      enrolledFacesList.innerHTML = '<span style="font-size:0.75rem; color:var(--text-muted);">Sin personas registradas aún</span>';
    }
  }

  if (btnEnrollFace) {
    btnEnrollFace.addEventListener('click', async () => {
      const name = enrollName.value.trim();
      const dni = enrollDni.value.trim();
      const role = enrollRole.value;

      if (!name || !dni) {
        alert('Por favor ingresa el Nombre completo y el DNI para enrolar a la persona.');
        return;
      }

      btnEnrollFace.disabled = true;
      btnEnrollFace.textContent = '⏳ Extrayendo Rostro...';

      // Capturar fotograma actual de la webcam o canvas
      let canvasToUse = webcamCanvas;
      if (!isWebcamActive || !webcamCanvas.width) {
        // Si la webcam del navegador no está activa, intentar crear canvas desde el videoFeed de la demo
        canvasToUse = document.createElement('canvas');
        canvasToUse.width = videoFeed.naturalWidth || 1280;
        canvasToUse.height = videoFeed.naturalHeight || 720;
        const cCtx = canvasToUse.getContext('2d');
        cCtx.drawImage(videoFeed, 0, 0, canvasToUse.width, canvasToUse.height);
      }

      canvasToUse.toBlob(async (blob) => {
        if (!blob) {
          alert('Error capturando la imagen para enrolamiento.');
          btnEnrollFace.disabled = false;
          btnEnrollFace.textContent = '📸 Enrolar Rostro desde Cámara';
          return;
        }

        const formData = new FormData();
        formData.append('file', blob, 'enroll.jpg');

        try {
          const res = await fetch(`/api/faces/enroll?name=${encodeURIComponent(name)}&dni=${encodeURIComponent(dni)}&role=${encodeURIComponent(role)}`, {
            method: 'POST',
            body: formData
          });

          const data = await res.json();
          if (res.ok) {
            alert(`✅ ${data.message}`);
            enrollName.value = '';
            enrollDni.value = '';
            loadEnrolledFaces();
          } else {
            alert(`⚠️ No se pudo enrolar: ${data.detail || 'Verifica que tu cara sea visible frente a la cámara.'}`);
          }
        } catch (err) {
          alert('Error de conexión enviando foto de enrolamiento: ' + err.message);
        } finally {
          btnEnrollFace.disabled = false;
          btnEnrollFace.textContent = '📸 Enrolar Rostro desde Cámara';
        }
      }, 'image/jpeg', 0.95);
    });
  }

  // Enrolamiento mediante Subida de Foto de Archivo (JPG/PNG)
  const btnEnrollFile = document.getElementById('btnEnrollFile');
  const enrollPhotoInput = document.getElementById('enrollPhotoInput');

  if (btnEnrollFile && enrollPhotoInput) {
    btnEnrollFile.addEventListener('click', () => {
      const name = enrollName.value.trim();
      const dni = enrollDni.value.trim();
      if (!name || !dni) {
        alert('Por favor ingresa el Nombre completo y el DNI antes de elegir la foto.');
        return;
      }
      enrollPhotoInput.click();
    });

    enrollPhotoInput.addEventListener('change', async (e) => {
      const file = e.target.files[0];
      if (!file) return;

      const name = enrollName.value.trim();
      const dni = enrollDni.value.trim();
      const role = enrollRole.value;

      btnEnrollFile.disabled = true;
      btnEnrollFile.textContent = '⏳ Procesando Foto...';

      const formData = new FormData();
      formData.append('file', file);

      try {
        const res = await fetch(`/api/faces/enroll?name=${encodeURIComponent(name)}&dni=${encodeURIComponent(dni)}&role=${encodeURIComponent(role)}`, {
          method: 'POST',
          body: formData
        });

        const data = await res.json();
        if (res.ok) {
          alert(`${data.message}`);
          enrollName.value = '';
          enrollDni.value = '';
          enrollPhotoInput.value = '';
          loadEnrolledFaces();
        } else {
          alert(`No se pudo enrolar la foto: ${data.detail || 'Asegúrate de que la foto contenga un rostro claro y visible.'}`);
        }
      } catch (err) {
        alert('Error enviando la foto de enrolamiento: ' + err.message);
      } finally {
        btnEnrollFile.disabled = false;
        btnEnrollFile.textContent = 'Subir Foto de Archivo (JPG/PNG)';
      }
    });
  }

  loadEnrolledFaces();

  // Enrolamiento de Símbolos e Insignias
  const btnEnrollSymbolFile = document.getElementById('btnEnrollSymbolFile');
  const symbolPhotoInput = document.getElementById('symbolPhotoInput');
  const symbolName = document.getElementById('symbolName');
  const symbolCategory = document.getElementById('symbolCategory');
  const enrolledSymbolsList = document.getElementById('enrolledSymbolsList');

  async function loadEnrolledSymbols() {
    if (!enrolledSymbolsList) return;
    try {
      const res = await fetch('/api/symbols/list');
      if (res.ok) {
        const data = await res.json();
        const symbols = data.symbols || [];
        enrolledSymbolsList.innerHTML = '';

        if (symbols.length === 0) {
          enrolledSymbolsList.innerHTML = '<span style="font-size: 0.75rem; color: var(--text-muted);">Sin símbolos registrados aún</span>';
          return;
        }

        symbols.forEach(s => {
          const item = document.createElement('div');
          item.style.display = 'flex';
          item.style.justifyContent = 'space-between';
          item.style.alignItems = 'center';
          item.style.background = 'rgba(0, 0, 0, 0.3)';
          item.style.padding = '4px 8px';
          item.style.borderRadius = '4px';
          item.style.fontSize = '0.75rem';

          item.innerHTML = `
            <span><strong>${s.name}</strong> (${s.category})</span>
            <button class="delete-symbol-btn" data-id="${s.id}" style="background: #e74c3c; color: #fff; border: none; padding: 2px 6px; border-radius: 3px; cursor: pointer; font-size: 0.65rem;">Eliminar</button>
          `;

          item.querySelector('.delete-symbol-btn').addEventListener('click', async () => {
            if (confirm(`¿Eliminar símbolo '${s.name}'?`)) {
              await fetch(`/api/symbols/${s.id}`, { method: 'DELETE' });
              loadEnrolledSymbols();
            }
          });

          enrolledSymbolsList.appendChild(item);
        });
      }
    } catch (e) {
      console.error('Error cargando símbolos enrolados:', e);
    }
  }

  if (btnEnrollSymbolFile && symbolPhotoInput) {
    btnEnrollSymbolFile.addEventListener('click', () => {
      if (!symbolName.value.trim()) {
        alert('Por favor escribe el nombre del símbolo o insignia antes de continuar.');
        symbolName.focus();
        return;
      }
      symbolPhotoInput.click();
    });

    symbolPhotoInput.addEventListener('change', async (e) => {
      const file = e.target.files[0];
      if (!file) return;

      const name = symbolName.value.trim();
      const cat = symbolCategory.value;

      btnEnrollSymbolFile.disabled = true;
      btnEnrollSymbolFile.textContent = 'Procesando Símbolo...';

      const formData = new FormData();
      formData.append('file', file);

      try {
        const res = await fetch(`/api/symbols/enroll?name=${encodeURIComponent(name)}&category=${encodeURIComponent(cat)}`, {
          method: 'POST',
          body: formData
        });

        const data = await res.json();
        if (res.ok) {
          alert(`${data.message}`);
          symbolName.value = '';
          symbolPhotoInput.value = '';
          loadEnrolledSymbols();
        } else {
          alert(`No se pudo enrolar el símbolo: ${data.detail || 'Error extrayendo huella visual.'}`);
        }
      } catch (err) {
        alert('Error enrolando símbolo: ' + err.message);
      } finally {
        btnEnrollSymbolFile.disabled = false;
        btnEnrollSymbolFile.textContent = 'Subir Foto de Símbolo (JPG/PNG)';
      }
    });
  }

  loadEnrolledSymbols();

  // Event Logs (Capturas)
  const eventLogsContainer = document.getElementById('eventLogsContainer');
  let lastLogsHash = '';

  async function fetchLogs() {
    if (!eventLogsContainer) return;
    try {
      const res = await fetch('/api/logs');
      if (res.ok) {
        const logs = await res.json();
        
        const currentHash = JSON.stringify(logs.map(l => `${l.track_id}-${l.timestamp}-${l.name}`));
        if (currentHash !== lastLogsHash) {
          lastLogsHash = currentHash;
          eventLogsContainer.innerHTML = '';
          
          if (logs.length === 0) {
            eventLogsContainer.innerHTML = '<span style="font-size: 0.85rem; color: var(--text-muted); padding: 10px;">Esperando eventos de cámara...</span>';
            return;
          }
          
          logs.forEach(log => {
            const card = document.createElement('div');
            
            // Determinar color por estado
            let badgeColor = '#3498db'; // Default
            if (log.status === 'No Registrado') badgeColor = '#e74c3c';
            else if (log.status === 'VIP' || log.status === 'VIP / Autorizado') badgeColor = '#f1c40f';
            else if (log.status === 'Empleado') badgeColor = '#2ecc71';
            
            card.className = 'compact-log-card';
            card.onclick = () => window.openModal(log.image, log.name, log.status, log.timestamp, badgeColor);

            card.innerHTML = `
              <img src="${log.image}" alt="Captura">
              <div class="compact-log-badge" style="background: ${badgeColor};" title="${log.name} - ${log.status}"></div>
            `;
            eventLogsContainer.appendChild(card);
          });
        }
      }
    } catch (e) {
      // Silenciar errores de conexión
    }
  }

  if (eventLogsContainer) {
    setInterval(fetchLogs, 2000);
    fetchLogs();
  }

  const aboutBtn = document.getElementById('aboutBtn');
  if (aboutBtn) {
    aboutBtn.addEventListener('click', () => {
      document.getElementById('aboutModal').style.display = 'flex';
    });
  }

  // Enrolamiento rápido desde la captura del Modal
  const btnModalEnroll = document.getElementById('btnModalEnroll');
  if (btnModalEnroll) {
    btnModalEnroll.addEventListener('click', async () => {
      const nameInput = document.getElementById('modalEnrollName');
      const dniInput = document.getElementById('modalEnrollDni');
      const roleInput = document.getElementById('modalEnrollRole');

      const name = nameInput ? nameInput.value.trim() : '';
      const dni = dniInput ? dniInput.value.trim() : '';
      const role = roleInput ? roleInput.value : 'Usuario';

      if (!name || !dni) {
        alert('Por favor ingresa Nombre y DNI/Legajo para enrolar a esta persona.');
        return;
      }

      btnModalEnroll.disabled = true;
      btnModalEnroll.textContent = 'Enrolando...';

      try {
        const res = await fetch('/api/faces/enroll_b64', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name: name,
            dni: dni,
            role: role,
            image_b64: currentModalImageB64
          })
        });

        const data = await res.json();
        if (res.ok) {
          alert(`${data.message}`);
          if (nameInput) nameInput.value = '';
          if (dniInput) dniInput.value = '';
          window.closeModal();
          loadEnrolledFaces();
          fetchLogs();
        } else {
          alert(`No se pudo enrolar desde la captura: ${data.detail || 'Asegúrate de que la captura muestre un rostro nítido.'}`);
        }
      } catch (err) {
        alert('Error en la solicitud de enrolamiento: ' + err.message);
      } finally {
        btnModalEnroll.disabled = false;
        btnModalEnroll.textContent = 'Registrar e Identificar';
      }
    });
  }

});

// Global state for modal capture image
let currentModalImageB64 = '';

// Modal Logic
window.openModal = function(imgSrc, name, status, time, badgeColor) {
  currentModalImageB64 = imgSrc;
  document.getElementById('modalImage').src = imgSrc;
  document.getElementById('modalCaption').innerHTML = `
    <strong style="color:#fff; font-size:1.2rem;">${name}</strong> 
    <span style="background: ${badgeColor}; padding: 3px 8px; border-radius: 4px; font-size: 0.8rem; margin-left:10px; color:#fff;">${status}</span> 
    <br><span style="font-size: 0.85rem; color: #ccc;">${time}</span>
  `;

  const modalEnrollSection = document.getElementById('modalEnrollSection');
  if (modalEnrollSection) {
    modalEnrollSection.style.display = 'block';
  }

  document.getElementById('imageModal').style.display = 'flex';
};

window.closeModal = function() {
  document.getElementById('imageModal').style.display = 'none';
};

window.closeAboutModal = function() {
  document.getElementById('aboutModal').style.display = 'none';
};

window.onclick = function(event) {
  const modal = document.getElementById('imageModal');
  const aboutModal = document.getElementById('aboutModal');
  if (event.target === modal) {
    window.closeModal();
  }
  if (event.target === aboutModal) {
    window.closeAboutModal();
  }
};
