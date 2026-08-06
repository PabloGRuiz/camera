document.addEventListener('DOMContentLoaded', () => {
  const API_KEY = "super_secret_edge_key_2026";
  function escapeHTML(str) {
    if (!str) return '';
    return str.toString()
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  const videoFeed = document.getElementById('videoFeed');
  const modeBtns = document.querySelectorAll('.mode-btn');

  // Sliders e Inputs
  const emaSlider = document.getElementById('emaSlider');
  const emaValue = document.getElementById('emaValue');
  const paddingSlider = document.getElementById('paddingSlider');
  const paddingValue = document.getElementById('paddingValue');
  const targetIdInput = document.getElementById('targetIdInput');
  const overlayCheckbox = document.getElementById('overlayCheckbox');

  // Selectors y Filtros dinámicos
  const activeModelSelect = document.getElementById('activeModelSelect');
  const dynamicFiltersContainer = document.getElementById('dynamicFiltersContainer');
  const selectAllFiltersBtn = document.getElementById('selectAllFiltersBtn');
  const onlyPersonFilterBtn = document.getElementById('onlyPersonFilterBtn');
  const clearAllFiltersBtn = document.getElementById('clearAllFiltersBtn');
  const maxFpsSelect = document.getElementById('maxFpsSelect');

  // Elementos de telemetría
  const fpsStat = document.getElementById('fpsStat');
  const latencyStat = document.getElementById('latencyStat');
  const targetIdStat = document.getElementById('targetIdStat');
  const deviceStat = document.getElementById('deviceStat');

  // Webcam
  const webcamToggleBtn = document.getElementById('webcamToggleBtn');
  const webcamVideo = document.getElementById('webcamVideo');
  const webcamCanvas = document.getElementById('webcamCanvas');
  
  let isWebcamActive = false;
  let webcamStream = null;
  let webcamLoopActive = false;
  let isProcessingFrame = false;
  let currentMode = 'framed';
  let availableModels = [];
  let currentModelClasses = {};
  let activeClassIds = new Set(); // IDs numéricos seleccionados

  // Fetch y configuración inicial de Modelos
  async function loadModels() {
    try {
      const res = await fetch('/api/models');
      const data = await res.json();
      availableModels = data.models;
      
      activeModelSelect.innerHTML = '';
      availableModels.forEach(m => {
        const opt = document.createElement('option');
        opt.value = m.id;
        opt.textContent = m.name;
        activeModelSelect.appendChild(opt);
      });
      
      const hasStandard = availableModels.find(m => m.id === 'STANDARD');
      if (hasStandard) {
        activeModelSelect.value = 'STANDARD';
      }
      
      handleModelChange();
    } catch (e) {
      console.error('Error cargando modelos:', e);
      activeModelSelect.innerHTML = '<option value="">Error cargando</option>';
    }
  }

  function handleModelChange() {
    const selectedId = activeModelSelect.value;
    const modelData = availableModels.find(m => m.id === selectedId);
    if (!modelData) return;

    currentModelClasses = modelData.classes;
    // Por defecto activamos ÚNICAMENTE la clase Persona (0) para evitar falsos positivos con otros objetos
    activeClassIds = new Set([0]);
    
    renderFilters();
    postSettings();
  }

  function renderFilters() {
    dynamicFiltersContainer.innerHTML = '';
    
    Object.entries(currentModelClasses).forEach(([idStr, name]) => {
      const id = parseInt(idStr);
      const isActive = activeClassIds.has(id);
      
      const toggle = document.createElement('div');
      toggle.className = `filter-toggle ${isActive ? 'active' : ''}`;
      
      let displayName = name.replace(/_/g, ' ');
      
      toggle.innerHTML = `
        <span class="filter-name" title="${displayName}">${displayName}</span>
        <div class="switch-indicator"></div>
      `;
      
      toggle.addEventListener('click', () => {
        if (activeClassIds.has(id)) {
          activeClassIds.delete(id);
          toggle.classList.remove('active');
        } else {
          activeClassIds.add(id);
          toggle.classList.add('active');
        }
        postSettings();
      });
      
      dynamicFiltersContainer.appendChild(toggle);
    });
  }

  if (activeModelSelect) {
    activeModelSelect.addEventListener('change', handleModelChange);
  }

  if (onlyPersonFilterBtn) {
    onlyPersonFilterBtn.addEventListener('click', () => {
      activeClassIds = new Set([0]);
      renderFilters();
      postSettings();
    });
  }

  if (selectAllFiltersBtn) {
    selectAllFiltersBtn.addEventListener('click', () => {
      activeClassIds = new Set(Object.keys(currentModelClasses).map(Number));
      renderFilters();
      postSettings();
    });
  }

  if (clearAllFiltersBtn) {
    clearAllFiltersBtn.addEventListener('click', () => {
      activeClassIds.clear();
      renderFilters();
      postSettings();
    });
  }

  let availableCameras = [];

  const videoWallContainer = document.getElementById('videoWallContainer');
  const liveAlertsContainer = document.getElementById('liveAlertsContainer');
  let lastLogId = 0;

  const cameraTabsList = document.getElementById('cameraTabsList');
  const openAddCamModalBtn = document.getElementById('openAddCamModalBtn');
  const addCameraModal = document.getElementById('addCameraModal');
  const closeAddCamModalBtn = document.getElementById('closeAddCamModalBtn');
  const modalCamIdInput = document.getElementById('modalCamIdInput');
  const modalSourceTypeSelect = document.getElementById('modalSourceTypeSelect');
  const modalCustomSourceGroup = document.getElementById('modalCustomSourceGroup');
  const modalSourceLabel = document.getElementById('modalSourceLabel');
  const modalCamSourceInput = document.getElementById('modalCamSourceInput');
  const modalAddCamSubmitBtn = document.getElementById('modalAddCamSubmitBtn');
  const modalAddCamMsg = document.getElementById('modalAddCamMsg');

  async function loadCameras() {
    try {
      const res = await fetch('/api/camera/list');
      if (!res.ok) return;
      const data = await res.json();
      
      const newCameras = data.cameras || [];
      // Solo re-renderizar si la lista de cámaras ha cambiado
      if (JSON.stringify(availableCameras) !== JSON.stringify(newCameras)) {
        availableCameras = newCameras;
        if (cameraTabsList) {
          cameraTabsList.innerHTML = `<span style="color: var(--text-muted); font-size: 0.85rem;">${availableCameras.length} cámara(s) conectada(s)</span>`;
        }
        renderVideoWall();
      }
    } catch (e) {
      console.error('Error cargando lista de cámaras:', e);
    }
  }

  function renderVideoWall() {
    if (!videoWallContainer) return;
    
    // Maintain existing elements like webcamVideo if any, but clear old streams
    Array.from(videoWallContainer.children).forEach(child => {
      if (child.id !== 'webcamVideo' && child.id !== 'webcamCanvas') {
        videoWallContainer.removeChild(child);
      }
    });

    if (availableCameras.length === 0) {
      const msg = document.createElement('div');
      msg.style.color = 'var(--text-muted)';
      msg.style.textAlign = 'center';
      msg.style.padding = '40px';
      msg.style.gridColumn = '1 / -1';
      msg.textContent = 'No hay cámaras conectadas al Video Wall.';
      videoWallContainer.appendChild(msg);
      return;
    }

    availableCameras.forEach(camId => {
      const cell = document.createElement('div');
      cell.className = 'camera-cell';
      
      const title = document.createElement('div');
      title.className = 'camera-cell-title';
      title.textContent = camId;
      
      const img = document.createElement('img');
      img.alt = `Cámara ${camId}`;
      img.className = 'video-stream-img';
      // Append timestamp to force reload
      img.src = `/video_feed?mode=${currentMode}&camera_id=${encodeURIComponent(camId)}&t=${Date.now()}`;
      
      const delBtn = document.createElement('button');
      delBtn.className = 'btn-danger';
      delBtn.style.position = 'absolute';
      delBtn.style.bottom = '8px';
      delBtn.style.right = '8px';
      delBtn.style.padding = '4px 8px';
      delBtn.style.fontSize = '0.7rem';
      delBtn.textContent = 'Desconectar';
      delBtn.onclick = async () => {
        if (confirm(`¿Desconectar la cámara '${camId}'?`)) {
          await removeCamera(camId);
        }
      };

      cell.appendChild(img);
      cell.appendChild(title);
      cell.appendChild(delBtn);
      videoWallContainer.appendChild(cell);
    });
  }

  async function removeCamera(camId) {
    try {
      const res = await fetch('/api/camera/control', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-API-Key': API_KEY },
        body: JSON.stringify({ action: 'remove', camera_id: camId })
      });
      if (res.ok) {
        loadCameras();
      }
    } catch (e) {}
  }

  function updateStreamUrl() {
    // When mode changes, refresh video wall to update src parameters
    renderVideoWall();
  }

  // --- POLING PARA ALERTAS EN TIEMPO REAL ---
  async function pollLiveAlerts() {
    if (!liveAlertsContainer) return;
    try {
      const res = await fetch('/api/logs?limit=5');
      if (!res.ok) return;
      const data = await res.json();
      const logs = data.logs || [];
      
      if (logs.length === 0) return;
      
      // Get the latest log ID to only add new ones
      const newLogs = logs.filter(log => log.id > lastLogId);
      
      if (newLogs.length > 0) {
        if (lastLogId === 0) {
           liveAlertsContainer.innerHTML = ''; // Clear "Esperando..." message
        }
        
        // Reverse to append oldest first among the new ones
        newLogs.reverse().forEach(log => {
           const alertDiv = document.createElement('div');
           
           const isDanger = log.role === 'No Registrado' || log.event_type === 'Alerta';
           const isWarning = log.event_type === 'Vehículo';
           
           alertDiv.className = `live-alert-card ${isDanger ? 'danger' : (isWarning ? 'warning' : '')}`;
           
           const imgHtml = log.image_path ? `<img src="${log.image_path}" class="live-alert-img" alt="Captura">` : `<div class="live-alert-img" style="background:#333"></div>`;
           
           alertDiv.innerHTML = `
              ${imgHtml}
              <div class="live-alert-content">
                 <div class="live-alert-title">${log.person_name}</div>
                 <div class="live-alert-meta">📍 ${log.camera_id} • 🕒 ${log.timestamp.substring(11, 19)}</div>
              </div>
           `;
           
           liveAlertsContainer.prepend(alertDiv);
           
           // Keep only max 15 alerts in UI
           if (liveAlertsContainer.children.length > 15) {
              liveAlertsContainer.removeChild(liveAlertsContainer.lastChild);
           }
           
           lastLogId = Math.max(lastLogId, log.id);
        });
      }
    } catch (e) {
      console.error("Error polling alerts:", e);
    }
  }
  
  setInterval(pollLiveAlerts, 2000);

  // Modal Conectar Cámara Handlers
  if (openAddCamModalBtn && addCameraModal) {
    openAddCamModalBtn.addEventListener('click', () => {
      if (modalCamIdInput) modalCamIdInput.value = `Camara_${availableCameras.length + 1}`;
      if (modalSourceTypeSelect) modalSourceTypeSelect.value = 'webcam_0';
      handleSourceTypeChange();
      if (modalAddCamMsg) modalAddCamMsg.innerHTML = '';
      addCameraModal.style.display = 'flex';
    });
  }

  if (closeAddCamModalBtn && addCameraModal) {
    closeAddCamModalBtn.addEventListener('click', () => {
      addCameraModal.style.display = 'none';
    });
  }

  if (modalSourceTypeSelect) {
    modalSourceTypeSelect.addEventListener('change', handleSourceTypeChange);
  }

  function handleSourceTypeChange() {
    const val = modalSourceTypeSelect.value;
    if (val === 'webcam_0') {
      modalCustomSourceGroup.style.display = 'none';
      modalCamSourceInput.value = '0';
    } else if (val === 'webcam_1') {
      modalCustomSourceGroup.style.display = 'none';
      modalCamSourceInput.value = '1';
    } else if (val === 'webcam_custom') {
      modalCustomSourceGroup.style.display = 'block';
      if (modalSourceLabel) modalSourceLabel.textContent = 'Número / Índice de Webcam USB (ej. 2):';
      modalCamSourceInput.value = '2';
    } else if (val === 'rtsp') {
      modalCustomSourceGroup.style.display = 'block';
      if (modalSourceLabel) modalSourceLabel.textContent = 'URL del Stream RTSP IP:';
      modalCamSourceInput.value = 'rtsp://admin:123456@192.168.1.100:554/stream1';
    } else if (val === 'mp4') {
      modalCustomSourceGroup.style.display = 'block';
      if (modalSourceLabel) modalSourceLabel.textContent = 'Ruta del Archivo MP4:';
      modalCamSourceInput.value = 'videos/sample.mp4';
    }
  }

  if (modalAddCamSubmitBtn) {
    modalAddCamSubmitBtn.addEventListener('click', async () => {
      const camId = modalCamIdInput.value.trim();
      const source = modalCamSourceInput.value.trim();

      if (!camId) {
        if (modalAddCamMsg) {
          modalAddCamMsg.innerHTML = '❌ Por favor ingresa un nombre para la cámara.';
          modalAddCamMsg.style.color = '#f87171';
        }
        return;
      }

      if (modalAddCamMsg) {
        modalAddCamMsg.innerHTML = '⚡ Conectando cámara...';
        modalAddCamMsg.style.color = 'var(--accent-cyan)';
      }

      try {
        const res = await fetch('/api/camera/control', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-API-Key': API_KEY },
          body: JSON.stringify({ action: 'add', source: source || '0', camera_id: camId })
        });
        if (res.ok) {
          if (modalAddCamMsg) {
            modalAddCamMsg.innerHTML = '✅ Cámara conectada con éxito.';
            modalAddCamMsg.style.color = '#10b981';
          }
          activeCameraId = camId;
          setTimeout(() => {
            if (addCameraModal) addCameraModal.style.display = 'none';
            loadCameras();
          }, 600);
        } else {
          const errData = await res.json();
          if (modalAddCamMsg) {
            modalAddCamMsg.innerHTML = `❌ Error: ${errData.detail || 'No se pudo conectar la cámara'}`;
            modalAddCamMsg.style.color = '#f87171';
          }
        }
      } catch (e) {
        if (modalAddCamMsg) {
          modalAddCamMsg.innerHTML = `❌ Error de red: ${e.message}`;
          modalAddCamMsg.style.color = '#f87171';
        }
      }
    });
  }

  loadCameras();

  // Captura Independiente de Webcam y Pantalla
  const webcamVideoEl = document.createElement('video');
  webcamVideoEl.autoplay = true;
  webcamVideoEl.muted = true;
  
  const screenVideoEl = document.createElement('video');
  screenVideoEl.autoplay = true;
  screenVideoEl.muted = true;

  if (webcamToggleBtn) {
    webcamToggleBtn.addEventListener('click', async () => {
      if (!isWebcamActive) {
        try {
          webcamStream = await navigator.mediaDevices.getUserMedia({
            video: { width: { ideal: 1280 }, height: { ideal: 720 } }
          });
          webcamVideoEl.srcObject = webcamStream;
          await webcamVideoEl.play();
          
          isWebcamActive = true;
          webcamToggleBtn.classList.add('active');
          webcamToggleBtn.textContent = 'Detener Cámara';
          
          startCaptureLoop(webcamVideoEl, 'Webcam_Local', () => isWebcamActive);
        } catch (err) {
          alert('No se pudo acceder a la webcam: ' + err.message);
        }
      } else {
        stopWebcam();
      }
    });
  }

  const screenShareToggleBtn = document.getElementById('screenShareToggleBtn');
  let screenStream = null;
  let isScreenActive = false;

  if (screenShareToggleBtn) {
    screenShareToggleBtn.addEventListener('click', async () => {
      if (!isScreenActive) {
        try {
          screenStream = await navigator.mediaDevices.getDisplayMedia({
            video: { cursor: "always" },
            audio: false
          });
          screenVideoEl.srcObject = screenStream;
          await screenVideoEl.play();
          
          isScreenActive = true;
          screenShareToggleBtn.classList.add('active');
          screenShareToggleBtn.textContent = 'Detener Pantalla';
          
          screenStream.getVideoTracks()[0].addEventListener('ended', stopScreenShare);
          startCaptureLoop(screenVideoEl, 'Pantalla_Compartida', () => isScreenActive);
        } catch (err) {
          if (err.name !== 'NotAllowedError') alert('Error: ' + err.message);
          stopScreenShare();
        }
      } else {
        stopScreenShare();
      }
    });
  }

  function stopScreenShare() {
    isScreenActive = false;
    if (screenStream) {
      screenStream.getTracks().forEach(track => track.stop());
      screenStream = null;
    }
    if (screenShareToggleBtn) {
      screenShareToggleBtn.classList.remove('active');
      screenShareToggleBtn.textContent = 'Transmitir Pantalla';
    }
  }

  function stopWebcam() {
    isWebcamActive = false;
    if (webcamStream) {
      webcamStream.getTracks().forEach(track => track.stop());
      webcamStream = null;
    }
    if (webcamToggleBtn) {
      webcamToggleBtn.classList.remove('active');
      webcamToggleBtn.textContent = 'Activar Cámara';
    }
  }

  async function startCaptureLoop(videoEl, cameraId, conditionFn) {
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    let isProcessing = false;

    while (conditionFn()) {
      const vw = videoEl.videoWidth || 1280;
      const vh = videoEl.videoHeight || 720;

      if (!isProcessing && (videoEl.readyState >= 2 || vw > 0)) {
        isProcessing = true;
        canvas.width = vw;
        canvas.height = vh;
        ctx.drawImage(videoEl, 0, 0, vw, vh);

        canvas.toBlob(async (blob) => {
          if (!blob) return (isProcessing = false);
          const formData = new FormData();
          formData.append('file', blob, 'frame.jpg');
          formData.append('camera_id', cameraId);

          try {
            await fetch('/api/webcam_frame', { method: 'POST', body: formData });
          } catch (err) {} finally {
            isProcessing = false;
          }
        }, 'image/jpeg', 0.8);
      }
      await new Promise(r => setTimeout(r, Math.max(33, 1000 / parseInt(maxFpsSelect.value || 30))));
    }
  }

  // Modos de Vista
  modeBtns.forEach(btn => {
    btn.addEventListener('click', (e) => {
      modeBtns.forEach(b => b.classList.remove('active'));
      e.target.classList.add('active');
      currentMode = e.target.getAttribute('data-mode');
      isProcessingFrame = false; 
      updateStreamUrl();
    });
  });

  // Enviar actualización de parámetros al servidor
  async function postSettings() {
    let classesPayload = Array.from(activeClassIds);
    if (classesPayload.length === Object.keys(currentModelClasses).length) {
      classesPayload = [-1]; 
    }

    const payload = {
      ema_alpha: emaSlider ? parseFloat(emaSlider.value) : 0.15,
      padding: paddingSlider ? parseFloat(paddingSlider.value) / 100.0 : 0.20,
      target_id: targetIdInput ? (parseInt(targetIdInput.value) || -1) : -1,
      draw_overlays: overlayCheckbox ? overlayCheckbox.checked : true,
      active_model: activeModelSelect ? activeModelSelect.value : 'STANDARD',
      target_classes: classesPayload,
      max_fps: maxFpsSelect ? parseInt(maxFpsSelect.value) : 30
    };

    try {
      await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-API-Key': API_KEY },
        body: JSON.stringify(payload)
      });
    } catch (err) {
      console.error('Error al actualizar ajustes:', err);
    }
  }

  if(emaSlider) {
    emaSlider.addEventListener('input', (e) => {
      emaValue.textContent = parseFloat(e.target.value).toFixed(2);
      postSettings();
    });
  }

  if(paddingSlider) {
    paddingSlider.addEventListener('input', (e) => {
      paddingValue.textContent = `${e.target.value}%`;
      postSettings();
    });
  }

  if(targetIdInput) targetIdInput.addEventListener('change', postSettings);
  if(overlayCheckbox) overlayCheckbox.addEventListener('change', postSettings);
  if(maxFpsSelect) maxFpsSelect.addEventListener('change', postSettings);

  // Pantalla Completa
  const fullscreenBtn = document.getElementById('fullscreenBtn');
  const videoViewContainer = document.querySelector('.video-view-container');
  if (fullscreenBtn) {
    fullscreenBtn.addEventListener('click', () => {
      if (!document.fullscreenElement) {
        if (videoViewContainer.requestFullscreen) {
          videoViewContainer.requestFullscreen();
        } else if (videoViewContainer.webkitRequestFullscreen) {
          videoViewContainer.webkitRequestFullscreen();
        } else if (videoViewContainer.msRequestFullscreen) {
          videoViewContainer.msRequestFullscreen();
        }
      } else {
        if (document.exitFullscreen) {
          document.exitFullscreen();
        }
      }
    });
  }

  // Modales: Acerca De
  const aboutBtn = document.getElementById('aboutBtn');
  const aboutModal = document.getElementById('aboutModal');
  const closeAboutModalBtn = document.getElementById('closeAboutModalBtn');
  if (aboutBtn && aboutModal) {
    aboutBtn.addEventListener('click', () => aboutModal.style.display = 'flex');
  }
  if (closeAboutModalBtn && aboutModal) {
    closeAboutModalBtn.addEventListener('click', () => aboutModal.style.display = 'none');
  }

  // Modales: Enrolamiento y Registro
  const enrollModalBtn = document.getElementById('enrollModalBtn');
  const enrollModal = document.getElementById('enrollModal');
  const closeEnrollModalBtn = document.getElementById('closeEnrollModalBtn');

  const logsModalBtn = document.getElementById('logsModalBtn');
  const logsModal = document.getElementById('logsModal');
  const closeLogsModalBtn = document.getElementById('closeLogsModalBtn');

  if (enrollModalBtn && enrollModal) {
    enrollModalBtn.addEventListener('click', () => {
      enrollModal.style.display = 'flex';
      loadEnrolledPersons();
      startEnrollWebcam();
    });
  }
  if (closeEnrollModalBtn && enrollModal) {
    closeEnrollModalBtn.addEventListener('click', () => {
      enrollModal.style.display = 'none';
      stopEnrollWebcam();
    });
  }

  if (logsModalBtn && logsModal) {
    logsModalBtn.addEventListener('click', () => {
      logsModal.style.display = 'flex';
      loadLogs();
    });
  }
  if (closeLogsModalBtn && logsModal) {
    closeLogsModalBtn.addEventListener('click', () => {
      logsModal.style.display = 'none';
    });
  }

  // Formulario y Lógica de Enrolamiento
  const enrollForm = document.getElementById('enrollForm');
  const enrollName = document.getElementById('enrollName');
  const enrollDni = document.getElementById('enrollDni');
  const enrollRole = document.getElementById('enrollRole');
  const captureMethodRadios = document.getElementsByName('captureMethod');
  const cameraSourceBox = document.getElementById('cameraSourceBox');
  const fileSourceBox = document.getElementById('fileSourceBox');
  const enrollFileInput = document.getElementById('enrollFileInput');
  
  const enrollWebcamVideo = document.getElementById('enrollWebcamVideo');
  const enrollCanvas = document.getElementById('enrollCanvas');
  const enrollSnapshotPreview = document.getElementById('enrollSnapshotPreview');
  const takeEnrollSnapshotBtn = document.getElementById('takeEnrollSnapshotBtn');
  const retakeEnrollSnapshotBtn = document.getElementById('retakeEnrollSnapshotBtn');
  const enrollMessage = document.getElementById('enrollMessage');
  const enrolledPersonsList = document.getElementById('enrolledPersonsList');
  const refreshPersonsBtn = document.getElementById('refreshPersonsBtn');

  let enrollWebcamStream = null;
  let enrollCapturedB64 = null;

  captureMethodRadios.forEach(radio => {
    radio.addEventListener('change', (e) => {
      if (e.target.value === 'camera') {
        cameraSourceBox.style.display = 'block';
        fileSourceBox.style.display = 'none';
        startEnrollWebcam();
      } else {
        cameraSourceBox.style.display = 'none';
        fileSourceBox.style.display = 'block';
        stopEnrollWebcam();
      }
    });
  });

  async function startEnrollWebcam() {
    if (enrollWebcamStream) return;
    try {
      enrollWebcamStream = await navigator.mediaDevices.getUserMedia({
        video: { width: 640, height: 480 }
      });
      enrollWebcamVideo.srcObject = enrollWebcamStream;
      await enrollWebcamVideo.play();
      enrollWebcamVideo.style.display = 'block';
      enrollSnapshotPreview.style.display = 'none';
      takeEnrollSnapshotBtn.style.display = 'block';
      retakeEnrollSnapshotBtn.style.display = 'none';
      enrollCapturedB64 = null;
    } catch (e) {
      console.error('Error accediendo a webcam de enrolamiento:', e);
    }
  }

  function stopEnrollWebcam() {
    if (enrollWebcamStream) {
      enrollWebcamStream.getTracks().forEach(track => track.stop());
      enrollWebcamStream = null;
    }
  }

  if (takeEnrollSnapshotBtn) {
    takeEnrollSnapshotBtn.addEventListener('click', () => {
      if (!enrollWebcamVideo) return;
      const vw = enrollWebcamVideo.videoWidth || 640;
      const vh = enrollWebcamVideo.videoHeight || 480;
      enrollCanvas.width = vw;
      enrollCanvas.height = vh;
      const ctx = enrollCanvas.getContext('2d');
      ctx.drawImage(enrollWebcamVideo, 0, 0, vw, vh);

      enrollCapturedB64 = enrollCanvas.toDataURL('image/jpeg', 0.9);
      enrollSnapshotPreview.src = enrollCapturedB64;
      enrollSnapshotPreview.style.display = 'block';
      enrollWebcamVideo.style.display = 'none';
      takeEnrollSnapshotBtn.style.display = 'none';
      retakeEnrollSnapshotBtn.style.display = 'block';
    });
  }

  if (retakeEnrollSnapshotBtn) {
    retakeEnrollSnapshotBtn.addEventListener('click', () => {
      enrollCapturedB64 = null;
      enrollSnapshotPreview.style.display = 'none';
      enrollWebcamVideo.style.display = 'block';
      takeEnrollSnapshotBtn.style.display = 'block';
      retakeEnrollSnapshotBtn.style.display = 'none';
    });
  }

  // Lógica de Escaneo Biométrico Face ID (Multirrostro 3D)
  const startFaceIdScanBtn = document.getElementById('startFaceIdScanBtn');
  const faceIdRingOverlay = document.getElementById('faceIdRingOverlay');
  const faceIdPrompt = document.getElementById('faceIdPrompt');
  const faceIdProgressBox = document.getElementById('faceIdProgressBox');
  const faceIdStepLabel = document.getElementById('faceIdStepLabel');
  const faceIdPercent = document.getElementById('faceIdPercent');
  const faceIdProgressBar = document.getElementById('faceIdProgressBar');

  if (startFaceIdScanBtn) {
    startFaceIdScanBtn.addEventListener('click', async () => {
      if (!enrollWebcamVideo || !enrollWebcamStream) {
        alert('Activa primero la cámara web para iniciar el escaneo 3D.');
        return;
      }
      
      const name = enrollName.value.trim();
      const dni = enrollDni.value.trim();
      if (!name || !dni) {
        alert('Por favor ingresa el Nombre Completo y DNI antes de iniciar el escaneo Face ID.');
        return;
      }

      startFaceIdScanBtn.disabled = true;
      if (faceIdProgressBox) faceIdProgressBox.style.display = 'block';
      let scannedImages = [];

      const steps = [
        { label: 'Paso 1/3: Mira de Frente 🎯', prompt: 'MIRA DE FRENTE', percent: '33%', ringColor: '#10b981' },
        { label: 'Paso 2/3: Gira levemente a la Izquierda ⬅️', prompt: 'GIRA A LA IZQUIERDA', percent: '66%', ringColor: '#3b82f6' },
        { label: 'Paso 3/3: Gira levemente a la Derecha ➡️', prompt: 'GIRA A LA DERECHA', percent: '100%', ringColor: '#8b5cf6' }
      ];

      function captureFrame() {
        const vw = enrollWebcamVideo.videoWidth || 640;
        const vh = enrollWebcamVideo.videoHeight || 480;
        enrollCanvas.width = vw;
        enrollCanvas.height = vh;
        const ctx = enrollCanvas.getContext('2d');
        ctx.drawImage(enrollWebcamVideo, 0, 0, vw, vh);
        return enrollCanvas.toDataURL('image/jpeg', 0.9);
      }

      try {
        for (let i = 0; i < steps.length; i++) {
          const step = steps[i];
          if (faceIdStepLabel) faceIdStepLabel.textContent = step.label;
          if (faceIdPrompt) faceIdPrompt.textContent = step.prompt;
          if (faceIdPercent) faceIdPercent.textContent = step.percent;
          if (faceIdProgressBar) faceIdProgressBar.style.width = step.percent;
          if (faceIdRingOverlay) {
            faceIdRingOverlay.style.borderColor = step.ringColor;
            faceIdRingOverlay.style.transform = 'scale(1.08)';
            setTimeout(() => { if (faceIdRingOverlay) faceIdRingOverlay.style.transform = 'scale(1.0)'; }, 250);
          }

          await new Promise(r => setTimeout(r, 1200));
          const frameB64 = captureFrame();
          scannedImages.push(frameB64);
        }

        if (enrollMessage) {
          enrollMessage.innerHTML = '⚡ Procesando fusión biométrica 3D Face ID...';
          enrollMessage.style.color = 'var(--accent-cyan)';
        }

        const payload = {
          name: name,
          dni: dni,
          role: enrollRole.value,
          images_b64: scannedImages
        };

        const res = await fetch('/api/faces/enroll_multi', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-API-Key': API_KEY },
          body: JSON.stringify(payload)
        });

        const data = await res.json();
        if (res.ok) {
          if (enrollMessage) {
            enrollMessage.innerHTML = `✅ ${data.message}`;
            enrollMessage.style.color = '#10b981';
          }
          loadEnrolledPersons();
        } else {
          if (enrollMessage) {
            enrollMessage.innerHTML = `❌ ${data.detail || 'Error en escaneo'}`;
            enrollMessage.style.color = '#f87171';
          }
        }
      } catch (err) {
        if (enrollMessage) {
          enrollMessage.innerHTML = `❌ Error de red: ${err.message}`;
          enrollMessage.style.color = '#f87171';
        }
      } finally {
        startFaceIdScanBtn.disabled = false;
        setTimeout(() => {
          if (faceIdProgressBox) faceIdProgressBox.style.display = 'none';
          if (faceIdPrompt) faceIdPrompt.textContent = 'Centra tu Rostro';
          if (faceIdRingOverlay) faceIdRingOverlay.style.borderColor = '#10b981';
        }, 3000);
      }
    });
  }

  if (enrollForm) {
    enrollForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      enrollMessage.innerHTML = 'Procesando biometría...';
      enrollMessage.style.color = 'var(--accent-cyan)';

      const name = enrollName.value.trim();
      const dni = enrollDni.value.trim();
      const role = enrollRole.value;
      const selectedMethod = document.querySelector('input[name="captureMethod"]:checked').value;

      try {
        let res;
        if (selectedMethod === 'camera') {
          if (!enrollCapturedB64) {
            enrollMessage.innerHTML = 'Primero debes tomar una foto con la cámara.';
            enrollMessage.style.color = '#f87171';
            return;
          }
          const payload = { name, dni, role, image_b64: enrollCapturedB64 };
          res = await fetch('/api/faces/enroll_b64', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-API-Key': API_KEY },
            body: JSON.stringify(payload)
          });
        } else {
          const file = enrollFileInput.files[0];
          if (!file) {
            enrollMessage.innerHTML = 'Primero selecciona un archivo de imagen.';
            enrollMessage.style.color = '#f87171';
            return;
          }
          const formData = new FormData();
          formData.append('file', file);
          res = await fetch(`/api/faces/enroll?name=${encodeURIComponent(name)}&dni=${encodeURIComponent(dni)}&role=${encodeURIComponent(role)}`, {
            method: 'POST',
            headers: { 'X-API-Key': API_KEY },
            body: formData
          });
        }

        const data = await res.json();
        if (res.ok) {
          enrollMessage.innerHTML = data.message || 'Persona enrolada correctamente.';
          enrollMessage.style.color = 'var(--accent-teal)';
          enrollName.value = '';
          enrollDni.value = '';
          if (selectedMethod === 'camera' && retakeEnrollSnapshotBtn) {
            retakeEnrollSnapshotBtn.click();
          }
          loadEnrolledPersons();
        } else {
          enrollMessage.innerHTML = `Error: ${data.detail || 'No se pudo enrolar'}`;
          enrollMessage.style.color = '#f87171';
        }
      } catch (err) {
        enrollMessage.innerHTML = `Error de red: ${err.message}`;
        enrollMessage.style.color = '#f87171';
      }
    });
  }

  async function loadEnrolledPersons() {
    if (!enrolledPersonsList) return;
    try {
      const res = await fetch('/api/faces/list');
      const data = await res.json();
      const persons = data.persons || [];

      if (persons.length === 0) {
        enrolledPersonsList.innerHTML = '<p style="color: var(--text-muted); font-size: 0.85rem;">No hay personas enroladas aún.</p>';
        return;
      }

      enrolledPersonsList.innerHTML = persons.map(p => `
        <div style="background: rgba(255,255,255,0.05); border: 1px solid var(--bg-card-border); padding: 10px; border-radius: 6px; display: flex; justify-content: space-between; align-items: center;">
          <div>
            <div style="font-weight: 600; font-size: 0.9rem; color: #fff;">${escapeHTML(p.name)}</div>
            <div style="font-size: 0.75rem; color: var(--text-muted);">DNI: ${escapeHTML(p.dni)} | Rol: ${escapeHTML(p.role)}</div>
          </div>
          <button onclick="deletePerson(${p.id})" class="filter-action-btn danger" style="padding: 4px 8px;">Eliminar</button>
        </div>
      `).join('');
    } catch (e) {
      console.error('Error cargando lista de personal:', e);
    }
  }

  window.deletePerson = async function(id) {
    if (!confirm('¿Seguro que deseas eliminar a esta persona?')) return;
    try {
      const res = await fetch(`/api/faces/${id}`, { method: 'DELETE', headers: { 'X-API-Key': API_KEY } });
      if (res.ok) {
        loadEnrolledPersons();
      }
    } catch (e) {}
  };

  if (refreshPersonsBtn) refreshPersonsBtn.addEventListener('click', loadEnrolledPersons);

  // Historial de Logs
  const logsGrid = document.getElementById('logsGrid');
  const refreshLogsBtn = document.getElementById('refreshLogsBtn');
  const clearLogsBtn = document.getElementById('clearLogsBtn');

  async function loadLogs() {
    if (!logsGrid) return;
    try {
      const res = await fetch('/api/logs');
      const logs = await res.json();

      if (!logs || logs.length === 0) {
        logsGrid.innerHTML = '<p style="color: var(--text-muted); font-size: 0.9rem; grid-column: 1 / -1;">No hay capturas registradas aún. El sistema tomará una captura cuando detecte a una persona.</p>';
        return;
      }

      logsGrid.innerHTML = logs.map(log => {
        const isRegistered = log.status !== 'No Registrado' && log.name !== 'Desconocido';
        const borderColor = isRegistered ? 'var(--accent-teal)' : '#f87171';
        const badgeBg = isRegistered ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)';
        return `
          <div style="background: rgba(0,0,0,0.4); border: 1px solid ${borderColor}; border-radius: 8px; overflow: hidden; display: flex; flex-direction: column;">
            <div style="padding: 8px 12px; background: rgba(0,0,0,0.6); display: flex; justify-content: space-between; align-items: center;">
              <span style="font-size: 0.8rem; font-weight: 600; color: var(--accent-cyan);">Hora: ${log.timestamp}</span>
              <span style="font-size: 0.75rem; padding: 2px 6px; border-radius: 4px; background: ${badgeBg}; color: ${borderColor}; font-weight: 600;">${log.status}</span>
            </div>
            <div style="width: 100%; aspect-ratio: 16/9; background: #000; overflow: hidden;">
              <img src="${log.image}" style="width: 100%; height: 100%; object-fit: cover;" alt="${log.name}">
            </div>
            <div style="padding: 8px 12px; font-weight: 600; font-size: 0.9rem; color: #fff;">
              ${log.name}
            </div>
          </div>
        `;
      }).join('');
    } catch (e) {
      console.error('Error cargando logs:', e);
    }
  }

  if (refreshLogsBtn) refreshLogsBtn.addEventListener('click', loadLogs);
  if (clearLogsBtn) {
    clearLogsBtn.addEventListener('click', async () => {
      if (!confirm('¿Deseas vaciar todo el historial de capturas?')) return;
      try {
        await fetch('/api/logs', { method: 'DELETE' });
        loadLogs();
      } catch (e) {}
    });
  }

  // Polling de Telemetría cada 1 segundo
  async function fetchStatus() {
    try {
      const res = await fetch('/api/status');
      if (res.ok) {
        const data = await res.json();
        if (fpsStat) fpsStat.textContent = `${data.fps} FPS`;
        if (latencyStat) latencyStat.textContent = `${data.inference_latency_ms} ms`;
        if (deviceStat) deviceStat.textContent = data.openvino_device || 'CPU';
        
        const activeTarget = data.telemetry?.active_target_id;
        if (targetIdStat) targetIdStat.textContent = activeTarget ? `ID #${activeTarget}` : 'Auto';
      }
    } catch (err) {}
  }
  setInterval(fetchStatus, 1000);
  fetchStatus();

  // Polling de Alertas en Tiempo Real
  let lastAlertIndex = -1;

  async function pollLiveAlerts() {
    if (!liveAlertsContainer) return;
    try {
      const res = await fetch('/api/logs?limit=20');
      const logs = await res.json();
      
      if (!logs || logs.length === 0) return;
      
      const newAlerts = [];
      // Buscar alertas nuevas
      for (let i = 0; i < logs.length; i++) {
        if (logs[i].id > lastAlertIndex || lastAlertIndex === -1) {
          newAlerts.push(logs[i]);
          if (logs[i].id > lastAlertIndex) lastAlertIndex = logs[i].id;
        }
      }
      
      // Si lastAlertIndex era -1, inicializamos con los ultimos 5 para no llenar
      if (lastAlertIndex === -1 && newAlerts.length > 5) {
        newAlerts.splice(5); 
      }
      
      if (newAlerts.length > 0) {
        if (liveAlertsContainer.innerHTML.includes('Esperando eventos')) {
          liveAlertsContainer.innerHTML = '';
        }
        
        newAlerts.reverse().forEach(alert => {
          const isDanger = alert.status === 'No Registrado' || alert.name === 'Desconocido';
          const borderColor = isDanger ? '#ef4444' : '#10b981';
          
          const alertEl = document.createElement('div');
          alertEl.style = `background: rgba(0,0,0,0.4); border-left: 4px solid ${borderColor}; padding: 10px; border-radius: 6px; margin-bottom: 8px; font-size: 0.85rem; color: #fff; animation: fade-in 0.3s ease;`;
          alertEl.innerHTML = `
            <div style="display:flex; justify-content:space-between; margin-bottom:4px; color:var(--text-muted); font-size:0.75rem;">
              <span>${alert.timestamp} | ${alert.camera_id}</span>
              <span style="color:${borderColor}; font-weight:700;">${alert.status}</span>
            </div>
            <div style="display:flex; gap: 10px; align-items:center;">
              <img src="${alert.image}" style="width: 50px; height: 50px; border-radius: 4px; object-fit: cover;">
              <div style="font-weight: 600;">${alert.name}</div>
            </div>
          `;
          liveAlertsContainer.prepend(alertEl);
        });
        
        // Mantener maximo 15 alertas en la vista
        while (liveAlertsContainer.children.length > 15) {
          liveAlertsContainer.removeChild(liveAlertsContainer.lastChild);
        }
      }
    } catch (err) {}
  }
  
  if (liveAlertsContainer) {
    setInterval(pollLiveAlerts, 2000);
  }

  // Inicialización de Modelos y Cámaras
  loadModels();
  loadCameras();
});
