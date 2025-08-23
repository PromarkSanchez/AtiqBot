// Archivo: public/embed.js (Basado en TU versión funcional + MEJORAS FINALES)
(function() {
  if (window.atiqtecChatbotInitialized) return;
  window.atiqtecChatbotInitialized = true;

  const scriptTag = document.currentScript;
  const clientId = scriptTag.getAttribute('data-client-id');
  const appId = scriptTag.getAttribute('data-app-id');
  
  if (!clientId || !appId) {
    console.error("AtiqTec Chatbot: Faltan los atributos 'data-client-id' y 'data-app-id'.");
    return;
  }

  const iframeSrc = new URL(scriptTag.src.replace('embed.js', 'chatbot.html'));
  iframeSrc.searchParams.set('clientId', clientId);
  iframeSrc.searchParams.set('appId', appId);

  const container = document.createElement('div');
  container.id = 'atiqtec-chatbot-container';
  
  const iframe = document.createElement('iframe');
  iframe.id = 'atiqtec-chatbot-iframe';
  iframe.src = iframeSrc.toString();
  iframe.setAttribute('title', 'Asistente Virtual AtiqTec');

  const overlay = document.createElement('div');
  overlay.id = 'atiqtec-chatbot-overlay';

  // --- 2. APLICACIÓN DE ESTILOS ---
  Object.assign(container.style, {
    position: 'fixed', bottom: '20px', right: '20px',
    width: '100px', height: '100px',
    zIndex: '2147483646',
    // ---> MEJORA #1: Añadimos 'left' y 'top' a la transición para una animación suave.
    transition: 'width 0.3s ease, height 0.3s ease, border-radius 0.3s ease, box-shadow 0.3s ease, left 0.3s ease, top 0.3s ease'
  });

  Object.assign(iframe.style, {
    width: '100%', height: '100%', border: 'none', backgroundColor: 'transparent',
    pointerEvents: 'none'
  });
  
  Object.assign(overlay.style, {
    position: 'absolute', top: '0', left: '0',
    width: '100%', height: '100%',
    zIndex: '2147483647',
    cursor: 'pointer'
  });
  
  container.appendChild(iframe);
  container.appendChild(overlay);
  document.body.appendChild(container);
  
  // --- 3. LÓGICA DE ESTADO Y COMUNICACIÓN ---
  let isChatOpen = false;
  // ---> NUEVO: Variable para recordar la posición
  let lastKnownPosition = { x: null, y: null };

  window.addEventListener('message', (event) => {
    if (event.source !== iframe.contentWindow) return;
    if (event.data.type === 'ATIQTEC_CHAT_STATE_CHANGE') {
      isChatOpen = event.data.payload.isOpen;
      updateContainerStyles(isChatOpen);
    }
  });

  function updateContainerStyles(isOpen) {
    const rect = container.getBoundingClientRect();
    const padding = 20;

    if (isOpen) {
      // Al abrir, guardamos la posición actual de la burbuja.
      lastKnownPosition.x = rect.left;
      lastKnownPosition.y = rect.top;

      const targetWidth = 400;
      const targetHeight = 600;
      let finalX = rect.left;
      let finalY = rect.top;

      if (finalX + targetWidth > window.innerWidth - padding) finalX = window.innerWidth - targetWidth - padding;
      if (finalY + targetHeight > window.innerHeight - padding) finalY = window.innerHeight - targetHeight - padding;
      if (finalX < padding) finalX = padding;
      if (finalY < padding) finalY = padding;

      container.style.left = `${finalX}px`;
      container.style.top = `${finalY}px`;
      container.style.right = 'auto';
      container.style.bottom = 'auto';
      container.style.width = `${targetWidth}px`;
      container.style.height = `${targetHeight}px`;
      container.style.maxWidth = '90vw';
      container.style.maxHeight = '80vh';
      container.style.boxShadow = '0 10px 15px -3px rgba(0,0,0,0.1)';
      container.style.borderRadius = '12px';
      overlay.style.display = 'none';
      iframe.style.pointerEvents = 'auto';

    } else {
      // ---> MEJORA #2: Al cerrar, usa la última posición conocida de la burbuja.
      if (lastKnownPosition.x !== null) {
          container.style.left = `${lastKnownPosition.x}px`;
          container.style.top = `${lastKnownPosition.y}px`;
          container.style.right = 'auto';
          container.style.bottom = 'auto';
      }

      container.style.width = '100px';
      container.style.height = '100px';
      container.style.maxWidth = 'initial';
      container.style.maxHeight = 'initial';
      container.style.boxShadow = 'none';
      container.style.borderRadius = '0';
      overlay.style.display = 'block';
      iframe.style.pointerEvents = 'none';
    }
  }

  // --- 4. LÓGICA DE ARRASTRE SOBRE EL OVERLAY (Tu código funcional, intacto) ---
  let isDragging = false, hasMoved = false, startX, startY, initialLeft, initialTop;
  const getEventCoords = (e) => e.touches ? e.touches[0] : e;
  
  const startDrag = (e) => {
    if (isChatOpen) return;
    e.preventDefault();
    isDragging = true;
    hasMoved = false;
    const coords = getEventCoords(e);
    startX = coords.clientX;
    startY = coords.clientY;
    const rect = container.getBoundingClientRect();
    initialLeft = rect.left;
    initialTop = rect.top;
    
    document.addEventListener('mousemove', moveDrag);
    document.addEventListener('touchmove', moveDrag);
    document.addEventListener('mouseup', endDrag);
    document.addEventListener('touchend', endDrag);
  };
  
  const moveDrag = (e) => {
    if (!isDragging) return;
    e.preventDefault();
    const coords = getEventCoords(e);
    const deltaX = coords.clientX - startX;
    const deltaY = coords.clientY - startY;

    if (!hasMoved && (Math.abs(deltaX) > 5 || Math.abs(deltaY) > 5)) {
      hasMoved = true;
      overlay.style.cursor = 'grabbing';
    }

    if (hasMoved) {
      container.style.left = `${initialLeft + deltaX}px`;
      container.style.top = `${initialTop + deltaY}px`;
      container.style.right = 'auto';
      container.style.bottom = 'auto';
    }
  };

  const endDrag = () => {
    if (!isDragging) return;
    isDragging = false;
    overlay.style.cursor = 'pointer';

    if (!hasMoved) {
      iframe.contentWindow.postMessage({ type: 'ATIQTEC_COMMAND', command: 'openChat' }, '*');
    }
    
    document.removeEventListener('mousemove', moveDrag);
    document.removeEventListener('touchmove', moveDrag);
    document.removeEventListener('mouseup', endDrag);
    document.removeEventListener('touchend', endDrag);
  };
  
  overlay.addEventListener('mousedown', startDrag);
  overlay.addEventListener('touchstart', startDrag);
})();