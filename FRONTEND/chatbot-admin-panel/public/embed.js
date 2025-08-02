// Archivo: public/embed.js
(function() {
  if (window.atiqtecChatbotInitialized) return;
  window.atiqtecChatbotInitialized = true;

  const scriptTag = document.currentScript;
  const apiKey = scriptTag.getAttribute('data-api-key');
  const appId = scriptTag.getAttribute('data-app-id');

  if (!apiKey || !appId) {
    console.error("AtiqTec Chatbot: 'data-api-key' y 'data-app-id' son requeridos.");
    return;
  }

  const iframeSrc = new URL(scriptTag.src.replace('embed.js', 'chatbot.html'));
  iframeSrc.searchParams.set('apiKey', apiKey);
  iframeSrc.searchParams.set('appId', appId);
  
  // Crea el iframe, PERO AÚN NO LE DA UN TAMAÑO GRANDE
  const iframe = document.createElement('iframe');
  iframe.src = iframeSrc.toString();
  iframe.id = 'atiqtec-chatbot-iframe';
  iframe.setAttribute('title', 'Asistente Virtual AtiqTec');
  
  // --- ESTILOS INICIALES (Para el estado CERRADO) ---
  iframe.style.position = 'fixed';
  iframe.style.bottom = '20px';
  iframe.style.right = '20px';
  iframe.style.width = '120px'; // Suficiente para el botón y un pequeño mensaje
  iframe.style.height = '120px';
  iframe.style.border = '0';
  iframe.style.backgroundColor = 'transparent';
  iframe.style.zIndex = '2147483647';
  iframe.style.transition = 'width 0.3s ease, height 0.3s ease'; // Para animar el cambio de tamaño

  document.body.appendChild(iframe);

  // --- ESCUCHA DE MENSAJES (LA MAGIA) ---
  window.addEventListener('message', function(event) {
    // Seguridad: Asegúrate de que el mensaje viene de nuestro iframe
    if (event.source !== iframe.contentWindow) {
      return;
    }

    const message = event.data;

    if (message.type === 'ATIQTEC_CHAT_STATE_CHANGE') {
      if (message.payload.isOpen) {
        // El chat se ha abierto: EXPANDIMOS EL IFRAME
        iframe.style.width = '400px';
        iframe.style.height = '600px';
        iframe.style.maxWidth = '90vw';
        iframe.style.maxHeight = '80vh';
        iframe.style.boxShadow = '0 10px 15px -3px rgba(0,0,0,0.1), 0 4px 6px -2px rgba(0,0,0,0.05)';
        iframe.style.borderRadius = '12px';
      } else {
        // El chat se ha cerrado: ENCOGEMOS EL IFRAME
        iframe.style.width = '120px';
        iframe.style.height = '120px';
        iframe.style.maxWidth = 'initial';
        iframe.style.maxHeight = 'initial';
        iframe.style.boxShadow = 'none';
        iframe.style.borderRadius = '0';
      }
    }
  });
})();