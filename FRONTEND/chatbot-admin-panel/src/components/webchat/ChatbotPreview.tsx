// Archivo: src/components/webchat/ChatbotPreview.tsx

import React, { useState, useRef, useEffect, useMemo } from 'react';
import { useMutation } from '@tanstack/react-query';
import axios from 'axios';
import ReactMarkdown from 'react-markdown';
import { PaperAirplaneIcon } from '@heroicons/react/24/solid';
import type { WebchatUIConfig } from '../../services/api/schemas';

// --- Tipos, Axios, etc. ---
interface Message { text: string; isUser: boolean; }
interface ChatRequestBody { session_id: string; message: string; is_authenticated_user: boolean; user_name: string; }
const axiosInstance = axios.create({ baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000' });
interface ChatbotPreviewProps { config: WebchatUIConfig; apiKey: string | null; applicationId: string | null; }

// --- Componentes y Utilidades ---
const TypingIndicator = () => (<div className="flex items-center space-x-1.5 p-3"><span className="h-2 w-2 rounded-full bg-gray-300 dark:bg-slate-500 animate-bounce" style={{ animationDelay: '-0.3s' }}></span><span className="h-2 w-2 rounded-full bg-gray-300 dark:bg-slate-500 animate-bounce" style={{ animationDelay: '-0.15s' }}></span><span className="h-2 w-2 rounded-full bg-gray-300 dark:bg-slate-500 animate-bounce"></span></div>);
const getInitials = (name: string): string => { if (!name) return 'B'; return name.split(' ').map(w => w[0]).slice(0, 2).join('').toUpperCase(); };
function isColorLight(hexColor: string): boolean { if (!hexColor || hexColor.length < 4) return true; const color = hexColor.charAt(0) === '#' ? hexColor.substring(1, 7) : hexColor; if (color.length < 6) return true; const r = parseInt(color.substring(0, 2), 16), g = parseInt(color.substring(2, 4), 16), b = parseInt(color.substring(4, 6), 16); return ((r * 299) + (g * 587) + (b * 114)) / 1000 > 150; }

const ChatbotPreview: React.FC<ChatbotPreviewProps> = ({ config, apiKey, applicationId }) => {
  const { botName, botDescription, composerPlaceholder, showBetaBadge, footerEnabled, footerText, footerLink, theme, initialState, initialStateText, avatarImageUrl, floatingButtonImageUrl, themeMode } = config;
  const initials = getInitials(botName);

  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [sessionId] = useState(`session_${Date.now()}`);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  
  const { mutate } = useMutation<any, Error, string>({
    mutationFn: (messageText: string) => { if (!apiKey || !applicationId) return Promise.reject(new Error("Falta Client ID o Application ID.")); const body: ChatRequestBody = { session_id: sessionId, message: messageText, is_authenticated_user: false, user_name: "Usuario" }; return axiosInstance.post('/api/v1/chat/', body, { headers: { 'X-API-KEY': apiKey, 'X-Application-ID': applicationId } }); },
    onSuccess: (response) => setMessages((prev) => [...prev, { text: response.data.bot_response, isUser: false }]),
    onError: (error: any) => {
        const errorText = error?.response?.data?.detail || error.message || "Error desconocido.";
        // Prevenir mensajes de error duplicados si el usuario hace varios clics
        if (messages.every(msg => !msg.text.includes(errorText))) {
           setMessages((prev) => [...prev, { text: `**Error:** ${errorText}`, isUser: false }]);
        }
    },
    onSettled: () => setIsTyping(false),
  });
  
  const handleSendMessage = (text: string) => { if (!text.trim() || isTyping) return; setMessages((prev) => [...prev, { text, isUser: true }]); setIsTyping(true); mutate(text); setInput(''); };

  const handleOpenChat = () => {
    if (isChatOpen) return;
    
    if (apiKey) {
        setIsChatOpen(true);
        if (messages.length === 0) {
            setIsTyping(true);
            mutate('__INICIAR_CHAT__');
        }
    } else {
        setIsChatOpen(true);
        setMessages([{ text: '**Error:** Introduce un Client ID válido para activar la vista previa.', isUser: false }]);
    }
  };

  // ---> INICIO DE LA ÚNICA MODIFICACIÓN <---

  // Este useEffect maneja la VISIBILIDAD inicial del chat según la configuración
  useEffect(() => {
    setIsChatOpen(initialState === 'open');
  }, [initialState]);

  // Este useEffect maneja la INICIALIZACIÓN de la conversación.
  // Es la clave para el comportamiento de "auto-inicio"
  useEffect(() => {
    // Si la API key cambia (ej, de null a un valor) Y el chat está o debe estar abierto...
    if (apiKey && isChatOpen) {
      // Y si aún no hay mensajes (significa que es la primera vez que tenemos una clave válida)...
      if (messages.length === 0 || (messages.length === 1 && messages[0].text.startsWith('**Error:**'))) {
          // Limpiamos los posibles mensajes de error y comenzamos.
          setMessages([]);
          setIsTyping(true);
          mutate('__INICIAR_CHAT__');
      }
    } 
    // Si la clave se borra (pasa a ser null), limpiamos el chat
    else if (!apiKey) {
      setMessages([]);
    }
  }, [apiKey, isChatOpen]); // Depende de la clave Y de si la ventana está abierta

  // ---> FIN DE LA MODIFICACIÓN <---
  
  useEffect(() => { if (window.self !== window.top) { window.parent.postMessage({ type: 'ATIQTEC_CHAT_STATE_CHANGE', payload: { isOpen: isChatOpen } }, '*'); } }, [isChatOpen]);
  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages, isTyping]);
  
  const systemTheme = useMemo(() => typeof window !== 'undefined' && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light', []);
  const activeTheme = themeMode === 'system' ? systemTheme : themeMode;

  const Avatar = ({ size }: { size: 'large' | 'small' }) => ( <div className={`rounded-full flex-shrink-0 flex items-center justify-center font-bold ${size === 'large' ? 'w-10 h-10 text-lg' : 'w-6 h-6 text-xs'}`}>{avatarImageUrl ? <img src={avatarImageUrl} alt="Bot Avatar" className="w-full h-full rounded-full object-cover" /> : <div className="w-full h-full rounded-full flex items-center justify-center" style={{ backgroundColor: theme.avatarBackgroundColor, color: isColorLight(theme.avatarBackgroundColor) ? '#000' : '#FFF' }}>{initials}</div>}</div> );
  
  const containerClasses = `w-full h-full font-sans bg-transparent ${activeTheme === 'dark' ? 'dark' : ''} ${activeTheme === 'light' ? 'light' : ''}`.trim();

  return (
    <div className={containerClasses} >
      <div className="relative w-full h-full">
        <div className={`w-full h-full transition-all duration-300 ease-in-out origin-bottom-right ${isChatOpen ? 'opacity-100 scale-100' : 'opacity-0 scale-90 pointer-events-none'}`}>
          <div className="w-full h-full bg-white dark:bg-slate-800 rounded-xl shadow-lg flex flex-col font-sans overflow-hidden">
            <header className="flex items-center p-3 text-white shadow-md relative" style={{ backgroundColor: theme.primaryColor }}>
              <div className="flex-shrink-0 mr-3"><Avatar size="large" /></div>
              <div><div className="flex items-center"><h2 className="font-bold text-md">{botName}</h2>{showBetaBadge && <span className="ml-2 px-1.5 py-0.5 text-xs font-semibold uppercase bg-white/30 rounded-full">Beta</span>}</div>{botDescription && <p className="text-xs opacity-80">{botDescription}</p>}</div>
              <button onClick={() => setIsChatOpen(false)} aria-label="Cerrar chat" className="absolute top-1 right-1 p-2 rounded-full text-white/70 hover:text-white hover:bg-white/20"><svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" /></svg></button>
            </header>
            <main className="flex-grow p-4 space-y-4 overflow-y-auto">{messages.map((msg, index) => (<div key={index} className={`flex items-start gap-3 ${msg.isUser ? 'justify-end' : ''}`}>{!msg.isUser && <div className="flex-shrink-0"><Avatar size="small" /></div>}<div className={`rounded-lg p-3 max-w-[85%] prose prose-sm dark:prose-invert max-w-none ${msg.isUser ? 'text-white' : 'bg-gray-200 dark:bg-slate-700 text-gray-800 dark:text-gray-200'}`} style={{ backgroundColor: msg.isUser ? theme.primaryColor : undefined }}><ReactMarkdown>{msg.text}</ReactMarkdown></div></div>))}{isTyping && (<div className="flex items-start gap-3"><div className="flex-shrink-0"><Avatar size="small" /></div><div className="bg-gray-200 dark:bg-slate-700 rounded-lg"><TypingIndicator /></div></div>)}<div ref={messagesEndRef} />
            </main>
            <footer className="p-3 border-t border-gray-200 dark:border-slate-700 bg-gray-50 dark:bg-slate-800">
              <form onSubmit={(e) => { e.preventDefault(); handleSendMessage(input); }} className="flex items-center bg-white dark:bg-slate-900 rounded-full border border-gray-300 dark:border-slate-600 px-4 py-1.5">
                <input type="text" placeholder={composerPlaceholder || "Escribe tu mensaje..."} value={input} onChange={(e) => setInput(e.target.value)} disabled={isTyping} className="flex-grow bg-transparent focus:outline-none text-sm text-gray-700 dark:text-gray-300 disabled:opacity-50" />
                <button type="submit" disabled={isTyping} className="ml-2 w-8 h-8 rounded-full flex items-center justify-center text-white" style={{ backgroundColor: theme.primaryColor }}><PaperAirplaneIcon className="w-4 h-4" /></button>
              </form>
              {footerEnabled && footerText && (<div className="text-center mt-2"><a href={footerLink || '#'} target="_blank" rel="noopener noreferrer" className="text-xs text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300">{footerText}</a></div>)}
            </footer>
          </div>
        </div>
        <div className={`absolute bottom-0 right-0 transition-all duration-300 ease-in-out origin-bottom-right ${!isChatOpen ? 'opacity-100 scale-100' : 'opacity-0 scale-90 pointer-events-none'}`}>
          <div className="flex flex-col items-end">
            {initialStateText && <div className="mb-2 p-2 px-3 rounded-lg text-center text-sm shadow-md text-white" style={{ backgroundColor: theme.primaryColor }}>{initialStateText}</div>}
            <button onClick={() => handleOpenChat()} aria-label="Abrir chat">
              {floatingButtonImageUrl ? <img src={floatingButtonImageUrl} alt="Chat Icon" className="w-16 h-16 rounded-full shadow-lg object-cover" /> : <div className="w-16 h-16 rounded-full shadow-lg flex items-center justify-center text-white" style={{ backgroundColor: theme.primaryColor }}><svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-8 h-8"><path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12.76c0 1.6 1.123 2.994 2.707 3.227c1.087.16 2.185.283 3.293.369V21l4.076-4.076a1.526 1.526 0 011.037-.443 48.282 48.282 0 005.68-.494c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z" /></svg></div>}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ChatbotPreview;