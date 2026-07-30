document.addEventListener('DOMContentLoaded', () => {
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
      
      // Auto-seleccionar MILITARY por defecto si existe, si no, el primero
      const hasMilitary = availableModels.find(m => m.id === 'MILITARY');
      if(hasMilitary) {
        activeModelSelect.value = 'MILITARY';
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
    // Por defecto, activar todas las clases
    activeClassIds = new Set(Object.keys(currentModelClasses).map(Number));
    
    renderFilters();
    postSettings(); // Notificar al backend el cambio de modelo y filtros
  }

  function renderFilters() {
    dynamicFiltersContainer.innerHTML = '';
    
    Object.entries(currentModelClasses).forEach(([idStr, name]) => {
      const id = parseInt(idStr);
      const isActive = activeClassIds.has(id);
      
      const toggle = document.createElement('div');
      toggle.className = `filter-toggle ${isActive ? 'active' : ''}`;
      
      // Nombre traducido/formateado
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

  loadModels(); // Iniciar carga


  // Actualizar URL del video stream (Servidor MJPEG)
  function updateStreamUrl() {
    if (videoFeed) videoFeed.style.display = 'block';
    videoFeed.src = `/video_feed?mode=${currentMode}&t=${Date.now()}`;
  }

  // Webcam Setup
  if (webcamToggleBtn) {
    webcamToggleBtn.addEventListener('click', async () => {
      if (!isWebcamActive || screenStream) { // Permitir activar cámara si está compartiendo pantalla
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
          
          isWebcamActive = true; // Compartir pantalla también usa el pipeline de webcam
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
    // Si están todos seleccionados, enviamos [-1] o None para decirle al backend "Rastrea Todo"
    // Si no hay ninguno, enviamos [] (lista vacía)
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
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
    } catch (err) {
      console.error('Error al actualizar ajustes:', err);
    }
  }

  // Listeners Ajustes Expertos
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

  // Modal Acerca De
  const aboutBtn = document.getElementById('aboutBtn');
  const aboutModal = document.getElementById('aboutModal');
  const closeAboutModalBtn = document.getElementById('closeAboutModalBtn');
  if (aboutBtn && aboutModal) {
    aboutBtn.addEventListener('click', () => aboutModal.style.display = 'flex');
  }
  if (closeAboutModalBtn && aboutModal) {
    closeAboutModalBtn.addEventListener('click', () => aboutModal.style.display = 'none');
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
