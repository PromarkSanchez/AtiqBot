// Archivo: public/embed.js
(function() {
  if (window.atiqtecChatbotInitialized) return;
  window.atiqtecChatbotInitialized = true;
  const scriptTag = document.currentScript;
  
  // --- ¡CORRECCIÓN AQUÍ! ---
  // Leemos el atributo correcto: 'data-client-id'
  const clientId = scriptTag.getAttribute('data-client-id'); 
  const appId = scriptTag.getAttribute('data-app-id');
  
  if (!clientId || !appId) {
    console.error("AtiqTec Chatbot: Los atributos 'data-client-id' y 'data-app-id' son requeridos.");
    return;
  }

  const iframeSrc = new URL(scriptTag.src.replace('embed.js', 'chatbot.html'));
  
  // --- ¡Y CORRECCIÓN AQUÍ! ---
  // Pasamos el parámetro con el nombre correcto al iframe
  iframeSrc.searchParams.set('clientId', clientId);
  iframeSrc.searchParams.set('appId', appId);
  
  const iframe = document.createElement('iframe');
  iframe.src = iframeSrc.toString();
  iframe.id = 'atiqtec-chatbot-iframe';
  iframe.setAttribute('title', 'Asistente Virtual AtiqTec');
  iframe.style.position = 'fixed';
  iframe.style.bottom = '20px';
  iframe.style.right = '20px';
  iframe.style.width = '100px';
  iframe.style.height = '100px';
  iframe.style.border = '0';
  iframe.style.backgroundColor = 'transparent';
  iframe.style.zIndex = '2147483647';
  iframe.style.transition = 'width 0.3s ease, height 0.3s ease, box-shadow 0.3s ease';

  document.body.appendChild(iframe);

  window.addEventListener('message', function(event) {
    if (event.source !== iframe.contentWindow) return;
    const message = event.data;
    if (message.type === 'ATIQTEC_CHAT_STATE_CHANGE') {
      if (message.payload.isOpen) {
        iframe.style.width = '400px';
        iframe.style.height = '600px';
        iframe.style.maxWidth = '90vw';
        iframe.style.maxHeight = '80vh';
        iframe.style.boxShadow = '0 10px 15px -3px rgba(0,0,0,0.1), 0 4px 6px -2px rgba(0,0,0,0.05)';
        iframe.style.borderRadius = '12px';
      } else {
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