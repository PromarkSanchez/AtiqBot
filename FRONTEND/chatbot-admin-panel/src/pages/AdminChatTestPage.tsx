// src/pages/AdminChatTestPage.tsx

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useReadAllApiClients, useProcessChatMessageApiV1ChatPost } from '../services/api/endpoints';
import type { ReadAllApiClientsParams, ApiClientResponse, ApiClientSettingsSchema, ChatRequest, ChatResponse } from '../services/api/schemas';

import toast, { Toaster } from 'react-hot-toast';
import { PaperAirplaneIcon } from '@heroicons/react/24/outline';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Button } from '../components/shared/Button';

// Interfaz para los mensajes
interface Message {
  id: string; text: string; sender: 'user' | 'bot'; timestamp: Date; metadata?: any; 
}
// Función de ayuda
const getAppIdFromSettings = (settings: ApiClientSettingsSchema | undefined | null): string => {
  return settings?.application_id || '';
};

const AdminChatTestPage: React.FC = () => {
  const [selectedApiClientId, setSelectedApiClientId] = useState<string>('');
  const [apiKey, setApiKey] = useState<string>('');
  const [appId, setAppId] = useState<string>('');
  
  const [sessionId, setSessionId] = useState<string>(`test-session-${Date.now()}`);
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [realUserDni, setRealUserDni] = useState<string>('');
  const [userName, setUserName] = useState<string>('Visitante');
  
  const [currentMessageText, setCurrentMessageText] = useState<string>('');
  const [chatHistory, setChatHistory] = useState<Message[]>([]);
  const chatContainerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const queryParams: ReadAllApiClientsParams = { skip: 0, limit: 100 };
  const { 
    data: apiClients = [], 
    isLoading: isLoadingApiClients
  } = useReadAllApiClients(
    queryParams, 
    { query: { queryKey: ['adminApiClientsListForChatTest', queryParams] } }
  );
  
  const sendMessageMutation = useProcessChatMessageApiV1ChatPost();
  
  useEffect(() => {
    if (!isLoadingApiClients && apiClients.length > 0 && !selectedApiClientId) {
      const firstClient = apiClients[0];
      setSelectedApiClientId(String(firstClient.id));
      setAppId(getAppIdFromSettings(firstClient.settings));
    }
  }, [isLoadingApiClients, apiClients, selectedApiClientId]);

  useEffect(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTo({ top: chatContainerRef.current.scrollHeight, behavior: 'smooth' });
    }
  }, [chatHistory]);

  const sendRequest = useCallback(async (messageToSend: string) => {
    if (!sessionId || !apiKey.trim() || !appId.trim()) {
      toast.error("Asegúrate de que el Cliente API, API Key y App ID estén listos.", { id: "configError" });
      if (messageToSend === '__INICIAR_CHAT__') setChatHistory([]);
      return;
    }

    localStorage.setItem('admin_test_x_api_key', apiKey);
    localStorage.setItem('admin_test_x_application_id', appId);

    const requestBody: ChatRequest = {
      session_id: sessionId, message: messageToSend,
      is_authenticated_user: isAuthenticated,
      user_dni: isAuthenticated ? realUserDni.trim() || undefined : undefined,
      user_name: userName,
    };
    
    try {
      const responseData = await sendMessageMutation.mutateAsync({ data: requestBody });
      const botMessage: Message = { id: `bot-${Date.now()}`, text: responseData.bot_response, sender: 'bot', timestamp: new Date(), metadata: responseData.metadata_details };
      setChatHistory(prev => [...prev.filter(m => m.id !== 'start'), botMessage]);
    } catch (error) {
      const axiosError = error as any;
      const errorDetailMessage = axiosError.response?.data?.detail || "Error al conectar con el chatbot.";
      toast.error(errorDetailMessage);
      const errorMessage: Message = { id: `err-${Date.now()}`, text: `Error: ${errorDetailMessage}`, sender: 'bot', timestamp: new Date() };
      setChatHistory(prev => [...prev.filter(m => m.id !== 'start'), errorMessage]);
    } finally {
      localStorage.removeItem('admin_test_x_api_key');
      localStorage.removeItem('admin_test_x_application_id');
    }
  // ---> CORRECCIÓN CLAVE: AÑADIMOS LAS DEPENDENCIAS A useCallback <---
  }, [sessionId, apiKey, appId, isAuthenticated, realUserDni, userName, sendMessageMutation]);

  const startConversation = useCallback(() => {
    if (chatHistory.length > 0) return;
    setChatHistory([{ id: 'start', text: 'Iniciando conversación...', sender: 'bot', timestamp: new Date() }]);
    sendRequest("__INICIAR_CHAT__");
  // ---> CORRECCIÓN CLAVE: DEPENDENCIAS <---
  }, [chatHistory.length, sendRequest]);
  
  useEffect(() => {
    if (sessionId && !isLoadingApiClients && apiClients.length > 0 && chatHistory.length === 0) {
      startConversation();
    }
  // ---> CORRECCIÓN CLAVE: DEPENDENCIAS <---
  }, [sessionId, isLoadingApiClients, apiClients, chatHistory.length, startConversation]);
  
  const handleSendMessage = useCallback(async () => {
    if (!currentMessageText.trim()) return;
    const userMessage: Message = { id: `user-${Date.now()}`, text: currentMessageText, sender: 'user', timestamp: new Date() };
    setChatHistory(prev => [...prev, userMessage]);
    sendRequest(currentMessageText);
    setCurrentMessageText('');
    inputRef.current?.focus();
  // ---> CORRECCIÓN CLAVE: DEPENDENCIAS <---
  }, [currentMessageText, sendRequest]);

  const handleResetSession = () => {
    const newSessionId = `test-session-${Date.now()}`;
    setSessionId(newSessionId);
    setChatHistory([]);
  };
  
  return (
    <div className="container mx-auto px-4 sm:px-6 lg:px-8 py-8 flex flex-col h-[calc(100vh-8rem)] bg-slate-900 text-white">
      <Toaster position="top-center" toastOptions={{ style: { background: '#334155', color: '#FFFFFF' } }}/>
      <h1 className="text-3xl font-bold mb-4">Prueba de Chat Interactivo</h1>
      <div className="mb-4 p-4 border border-slate-700 rounded-lg bg-slate-800 shadow-md">
        <h2 className="text-lg font-semibold mb-3">Configuración de la Sesión</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 items-end">
          <div>
            <label htmlFor="apiClientSelect" className="block text-sm font-medium text-slate-300">Cliente API</label>
            <select
              id="apiClientSelect"
              value={selectedApiClientId}
              onChange={(e) => {
                const newClientId = e.target.value;
                setSelectedApiClientId(newClientId);
                const client = apiClients.find(c => String(c.id) === newClientId);
                if (client) setAppId(getAppIdFromSettings(client.settings));
              }}
              disabled={isLoadingApiClients || apiClients.length === 0}
              className="mt-1 block w-full pl-3 pr-10 py-2 text-base border-slate-600 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm rounded-md bg-slate-700 text-white disabled:opacity-50">
              <option value="" disabled>{isLoadingApiClients ? "Cargando..." : (apiClients.length === 0 ? "No hay clientes" : "Selecciona...")}</option>
              {apiClients.map(client => (
                <option key={client.id} value={String(client.id)}>{client.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="apiKey" className="block text-sm font-medium text-slate-300">X-API-Key</label>
            <input type="password" id="apiKey" value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder="Clave de tu Cliente API" className="mt-1 block w-full px-3 py-2 border border-slate-600 rounded-md shadow-sm sm:text-sm bg-slate-700 text-white"/>
          </div>
          <div>
            <label htmlFor="appId" className="block text-sm font-medium text-slate-300">X-Application-ID (automático)</label>
            <input type="text" id="appId" value={appId} readOnly className="mt-1 block w-full px-3 py-2 border border-slate-600 rounded-md shadow-sm sm:text-sm bg-slate-900 text-slate-400 cursor-not-allowed"/>
          </div>
          <div><Button onClick={handleResetSession} variant="secondary" className="w-full">Nueva Sesión</Button></div>
        </div>
        <div className="mt-4 pt-4 border-t border-slate-700 flex items-center space-x-4">
          <div className="flex items-center">
            <input type="checkbox" id="isAuthenticated" checked={isAuthenticated} onChange={(e) => setIsAuthenticated(e.target.checked)} className="h-4 w-4 rounded text-indigo-500 focus:ring-indigo-500 bg-slate-600 border-slate-500"/>
            <label htmlFor="isAuthenticated" className="ml-2 text-sm text-slate-300 cursor-pointer">Simular Login</label>
          </div>
          <div className={`flex-grow ${isAuthenticated ? 'opacity-100' : 'opacity-50'}`}>
            <input type="text" id="realUserDni" value={realUserDni} onChange={e => setRealUserDni(e.target.value)} placeholder="Ingresa DNI real aquí..." disabled={!isAuthenticated} className="w-full px-3 py-2 border border-slate-600 rounded-md text-sm bg-slate-700 text-white disabled:cursor-not-allowed"/>
          </div>
        </div>
      </div>
      <div ref={chatContainerRef} className="flex-grow overflow-y-auto p-4 mb-4 bg-slate-950/50 border border-slate-800 rounded-lg shadow-inner">
        {chatHistory.map(msg => (
          <div key={msg.id} className={`flex mb-4 ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`relative group max-w-2xl px-4 py-3 rounded-xl shadow-lg ${msg.sender === 'user' ? 'bg-indigo-600 text-white rounded-br-none' : 'bg-slate-700 text-slate-200 rounded-bl-none'}`}>
              {msg.sender === 'bot' ? (
                <div className="prose prose-sm prose-invert max-w-none text-left">
                  <ReactMarkdown children={msg.text} remarkPlugins={[remarkGfm]} components={{ a: ({node, ...props}) => <a {...props} target="_blank" rel="noopener noreferrer" className="text-indigo-400 hover:underline"/>, p: ({node, ...props}) => <p {...props} className="my-1"/>}}/>
                </div>
              ) : ( <p className="text-sm">{msg.text}</p> )}
              {msg.metadata && Object.keys(msg.metadata).length > 0 && (<details className="mt-2 text-xs"><summary className="cursor-pointer text-slate-400 hover:underline">Ver Metadatos</summary><pre className="mt-1 p-2 bg-black/20 rounded text-xs whitespace-pre-wrap break-all max-h-40 overflow-auto text-slate-300">{JSON.stringify(msg.metadata, null, 2)}</pre></details>)}
            </div>
          </div>
        ))}
        {sendMessageMutation.isPending && <div className="flex justify-start mb-4"><div className="px-4 py-3 rounded-xl bg-slate-700 animate-pulse w-40 h-10"></div></div>}
      </div>
      <form onSubmit={(e) => { e.preventDefault(); handleSendMessage(); }} className="p-4 bg-slate-800 border-t border-slate-700">
        <div className="flex items-center space-x-3">
          <input ref={inputRef} type="text" value={currentMessageText} onChange={(e) => setCurrentMessageText(e.target.value)}
            placeholder="Escribe tu mensaje..." disabled={sendMessageMutation.isPending || isLoadingApiClients}
            className="flex-grow px-4 py-2 border border-slate-600 rounded-full text-base bg-slate-700 text-white focus:ring-2 focus:ring-indigo-500 focus:outline-none"/>
          <Button type="submit" disabled={sendMessageMutation.isPending || !currentMessageText.trim() || !apiKey.trim()}
            isLoading={sendMessageMutation.isPending} icon={!sendMessageMutation.isPending && <PaperAirplaneIcon className="h-5 w-5" />}>
                <span className="sr-only">Enviar</span>
          </Button>
        </div>
      </form>
    </div>
  );
};

export default AdminChatTestPage;