// Archivo: src/components/shared/ChatTestModal.tsx

import React, { useState, useRef, useEffect } from 'react';
import { useMutation } from '@tanstack/react-query';
import axios from 'axios';
import ReactMarkdown from 'react-markdown';
import { PaperAirplaneIcon } from '@heroicons/react/24/solid';

// Tipos para los mensajes
interface Message {
  text: string;
  isUser: boolean;
}

// Este es el cuerpo de la petición que tu backend espera
interface ChatRequestBody {
  session_id: string;
  message: string;
  is_authenticated_user: boolean; // Simulare mos como no-autenticado
  user_name: string;
  user_dni?: string; // Lo dejaremos opcional
}

const axiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
});

// Props que el modal necesitará para funcionar
interface ChatTestModalProps {
  apiKey: string;
  applicationId: string;
}

export const ChatTestModal: React.FC<ChatTestModalProps> = ({ apiKey, applicationId }) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [sessionId] = useState(`test_session_${Date.now()}`);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };
  
  useEffect(scrollToBottom, [messages]);
  
  useEffect(() => {
    // Enviar el mensaje inicial para empezar la conversación
    sendMessage('__INICIAR_CHAT__');
  }, []); // El array vacío asegura que se ejecute solo una vez

  // `useMutation` para manejar la llamada a la API
  const { mutate, isPending: isSendingMessage } = useMutation<any, Error, string>({
    mutationFn: (messageText: string) => {
      const body: ChatRequestBody = {
        session_id: sessionId,
        message: messageText,
        is_authenticated_user: false,
        user_name: "Usuario de Prueba",
      };

      return axiosInstance.post('/api/v1/chat/', body, {
        headers: {
          'X-API-KEY': apiKey,
          'X-Application-ID': applicationId,
        },
      });
    },
    onSuccess: (response) => {
      const botResponse: Message = { text: response.data.bot_response, isUser: false };
      setMessages((prev) => [...prev, botResponse]);
    },
    onError: (error: any) => {
        const errorMessage = error?.response?.data?.detail || error.message || 'Error desconocido';
        const botError: Message = { text: `Error: ${errorMessage}`, isUser: false };
        setMessages((prev) => [...prev, botError]);
    }
  });

  const sendMessage = (messageText: string) => {
      if (messageText.trim() === '') return;
      if (messageText !== '__INICIAR_CHAT__') {
          const userMessage: Message = { text: messageText, isUser: true };
          setMessages((prev) => [...prev, userMessage]);
      }
      mutate(messageText);
      if (messageText !== '__INICIAR_CHAT__') setInput('');
  };
  
  return (
    <div className="flex flex-col h-[70vh] bg-white dark:bg-slate-800 rounded-lg">
      <header className="p-4 bg-gray-100 dark:bg-slate-900 border-b dark:border-slate-700">
        <h3 className="font-semibold text-lg text-gray-800 dark:text-white">Prueba de Chat en Vivo</h3>
        <p className="text-xs text-gray-500 dark:text-gray-400">Cliente App ID: <span className="font-mono">{applicationId}</span></p>
      </header>
      
      <div className="flex-grow p-4 overflow-y-auto space-y-4">
        {messages.map((msg, index) => (
          <div key={index} className={`flex items-start gap-3 ${msg.isUser ? 'justify-end' : ''}`}>
            {!msg.isUser && <span className="flex-shrink-0 w-8 h-8 rounded-full bg-indigo-500 text-white flex items-center justify-center font-bold">B</span>}
            <div className={`rounded-lg p-3 max-w-sm ${msg.isUser ? 'bg-indigo-600 text-white' : 'bg-gray-200 dark:bg-slate-700 text-gray-800 dark:text-gray-200'}`}>
              <ReactMarkdown>{msg.text}</ReactMarkdown>
            </div>
          </div>
        ))}
         {isSendingMessage && <p className="text-center text-sm animate-pulse text-gray-500">Escribiendo...</p>}
        <div ref={messagesEndRef} />
      </div>

      <div className="p-4 border-t dark:border-slate-700">
        <form onSubmit={(e) => { e.preventDefault(); sendMessage(input); }} className="flex items-center space-x-2">
            <input 
              type="text" value={input} onChange={(e) => setInput(e.target.value)} 
              placeholder="Escribe tu mensaje..." disabled={isSendingMessage}
              className="w-full px-3 py-2 text-sm bg-white border border-gray-300 rounded-md shadow-sm dark:text-white dark:bg-slate-900 dark:border-slate-600 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
            />
            <button type="submit" disabled={isSendingMessage} className="p-2 rounded-full text-white bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-400">
              <PaperAirplaneIcon className="h-5 w-5"/>
            </button>
        </form>
      </div>
    </div>
  );
};