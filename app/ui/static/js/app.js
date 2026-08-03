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

  loadModels();

  function updateStreamUrl() {
    if (videoFeed) videoFeed.style.display = 'block';
    videoFeed.src = `/video_feed?mode=${currentMode}&t=${Date.now()}`;
  }

  // Webcam Setup
  if (webcamToggleBtn) {
    webcamToggleBtn.addEventListener('click', async () => {
      if (!isWebcamActive || screenStream) {
        try {
          if (screenStream) stopScreenShare();
          webcamStream = await navigator.mediaDevices.getUserMedia({
            video: { width: { ideal: 1280 }, height: { ideal: 720 } }
          });
          webcamVideo.srcObject = webcamStream;
          await webcamVideo.play();
          
          isWebcamActive = true;
          webcamToggleBtn.classList.add('active');
          webcamToggleBtn.textContent = 'Detener Cámara';
          
          updateStreamUrl();
          startWebcamLoop();
        } catch (err) {
          alert('No se pudo acceder a la webcam: ' + err.message);
        }
      } else {
        stopWebcam();
      }
    });
  }

  // Compartir Pantalla
  const screenShareToggleBtn = document.getElementById('screenShareToggleBtn');
  let screenStream = null;

  if (screenShareToggleBtn) {
    screenShareToggleBtn.addEventListener('click', async () => {
      if (!screenStream) {
        try {
          if (isWebcamActive) stopWebcam();
          screenStream = await navigator.mediaDevices.getDisplayMedia({
            video: { cursor: "always" },
            audio: false
          });
          webcamVideo.srcObject = screenStream;
          await webcamVideo.play();
          
          isWebcamActive = true;
          screenShareToggleBtn.classList.add('active');
          screenShareToggleBtn.textContent = 'Detener Pantalla';
          
          screenStream.getVideoTracks()[0].addEventListener('ended', stopScreenShare);
          updateStreamUrl();
          startWebcamLoop();
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
    isWebcamActive = false;
    webcamLoopActive = false;
    if (screenStream) {
      screenStream.getTracks().forEach(track => track.stop());
      screenStream = null;
    }
    if (screenShareToggleBtn) {
      screenShareToggleBtn.classList.remove('active');
      screenShareToggleBtn.textContent = 'Transmitir Pantalla';
    }
    updateStreamUrl();
  }

  function stopWebcam() {
    isWebcamActive = false;
    webcamLoopActive = false;
    if (webcamStream) {
      webcamStream.getTracks().forEach(track => track.stop());
      webcamStream = null;
    }
    webcamToggleBtn.classList.remove('active');
    webcamToggleBtn.textContent = 'Activar Cámara';
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
          if (!blob) return (isProcessingFrame = false);
          const formData = new FormData();
          formData.append('file', blob, 'frame.jpg');

          try {
            await fetch('/api/webcam_frame', { method: 'POST', body: formData });
          } catch (err) {} finally {
            isProcessingFrame = false;
          }
        }, 'image/jpeg', 0.85);
      }
      await new Promise(r => setTimeout(r, 40));
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
      ema_alpha: parseFloat(emaSlider.value),
      padding: parseFloat(paddingSlider.value) / 100.0,
      target_id: parseInt(targetIdInput.value) || -1,
      draw_overlays: overlayCheckbox.checked,
      active_model: activeModelSelect.value,
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
        fpsStat.textContent = `${data.fps} FPS`;
        latencyStat.textContent = `${data.inference_latency_ms} ms`;
        deviceStat.textContent = data.openvino_device || 'CPU';
        
        const activeTarget = data.telemetry?.active_target_id;
        targetIdStat.textContent = activeTarget ? `ID #${activeTarget}` : 'Auto';
      }
    } catch (err) {}
  }
  setInterval(fetchStatus, 1000);
  fetchStatus();
});
