// Archivo: src/pages/AdminWebchatCustomizerPage.tsx


import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import toast from 'react-hot-toast';
import { useQueryClient } from '@tanstack/react-query';

import ChatbotPreview from '../components/webchat/ChatbotPreview';
import type { WebchatUIConfig } from '../services/api/schemas';
import {
  useReadApiClientByIdEndpointApiV1AdminApiClientsApiClientIdGet as useReadApiClientById,
  useUpdateWebchatUiConfigEndpointApiV1AdminApiClientsApiClientIdWebchatUiConfigPut as useUpdateWebchatUiConfig,
} from '../services/api/endpoints';


const initialConfig: WebchatUIConfig = {
  botName: 'Asistente Virtual',
  botDescription: 'Pregúntame lo que necesites',
  composerPlaceholder: 'Escribe tu mensaje aquí...',
  showBetaBadge: false,
  footerEnabled: true,
  footerText: 'Powered by AtiqTec',
  footerLink: 'https://atiqtec.com',
  initialState: 'closed',
  initialStateText: '¡Hola! ¿Necesitas ayuda?',
  avatarImageUrl: '/logoUpch.jpg',
  floatingButtonImageUrl: '/logoUpch.jpg',
  themeMode: 'system',
  theme: {
    primaryColor: '#2a4dac',
    avatarBackgroundColor: '#bfdbfe',
  },
};

const AdminWebchatCustomizerPage: React.FC = () => {
  const { apiClientId } = useParams<{ apiClientId: string }>();
  const numericApiClientId = apiClientId ? Number(apiClientId) : undefined;
  const queryClient = useQueryClient();
  const [config, setConfig] = useState<WebchatUIConfig | null>(null);
  const testApiKey = localStorage.getItem('test_chat_api_key');
  const testAppId = localStorage.getItem('test_chat_app_id');

  const { data: apiClientData, isLoading: isLoadingApiClient, isError, error: loadError } = useReadApiClientById(numericApiClientId!, { query: { enabled: !!numericApiClientId }, });
  const { mutate: saveConfig, isPending: isSaving } = useUpdateWebchatUiConfig({
    mutation: {
      onSuccess: () => { 
        toast.success('¡Configuración guardada!'); 
        if (numericApiClientId) { queryClient.invalidateQueries({ queryKey: [`/api/v1/admin/api_clients/${numericApiClientId}`] }); }
      },
      onError: (error: any) => { 
        const errorMessage = error?.response?.data?.detail || error.message || 'Error desconocido al guardar';
        toast.error(`Error: ${errorMessage}`);
      },
    },
  });

  useEffect(() => {
    if (apiClientData) {
      const existingConfig = (apiClientData.webchat_ui_config || {}) as Partial<WebchatUIConfig>;
      setConfig({ ...initialConfig, ...existingConfig, theme: { ...initialConfig.theme, ...existingConfig.theme } });
    }
  }, [apiClientData]);
  
  const handleConfigChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    if (!config) return;
    const { name, value, type, dataset } = e.target;
    const realValue = type === 'checkbox' ? (e.target as HTMLInputElement).checked : value;
    setConfig((prev) => {
      if (!prev) return null;
      if (dataset.section === 'theme') { return { ...prev, theme: { ...prev.theme, [name]: realValue } }; }
      return { ...prev, [name]: realValue };
    });
  };

  const handleSave = () => { if (config && numericApiClientId) saveConfig({ apiClientId: numericApiClientId, data: config }); };
  
  if (isLoadingApiClient || !config) { return <div className="p-8 text-center text-gray-400">Cargando...</div>; }
  if (isError) { return <div className="p-8 text-center text-red-500">Error al cargar: {(loadError as any)?.message || 'Desconocido'}</div>; }
  
  const labelClass = "block text-sm font-medium text-gray-700 dark:text-gray-300";
  const inputClass = "block w-full px-3 py-2 mt-1 text-sm text-gray-900 bg-white border border-gray-300 rounded-md shadow-sm dark:text-white dark:bg-slate-900 dark:border-slate-600 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 disabled:opacity-60 disabled:cursor-not-allowed";
  const switchBase = "relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-600 focus:ring-offset-2";
  const switchChecked = "bg-indigo-600";
  const switchUnchecked = "bg-gray-200 dark:bg-slate-600";
  const switchKnobBase = "pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out";
  const switchKnobChecked = "translate-x-5";
  const switchKnobUnchecked = "translate-x-0";
  const sectionTitleClass = "text-lg font-semibold text-gray-900 dark:text-white border-b border-gray-200 dark:border-slate-700 pb-3 mb-4";
  const btnPrimaryClass = "inline-flex items-center justify-center px-4 py-2 text-sm font-medium text-white bg-indigo-600 border border-transparent rounded-md shadow-sm hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed";
  // Ensure the type includes is_premium or use a type assertion
  const isPremiumUser = apiClientData?.is_premium ?? false;

  return (
    <div className="p-4 md:p-6 flex-grow">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Personalizador de Webchat</h1>
          <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">{`Modificando la apariencia para: `}<span className="font-semibold">{apiClientData?.name || `Cliente ID ${numericApiClientId}`}</span></p>
        </div>
        <button onClick={handleSave} disabled={isSaving} className={btnPrimaryClass}>{isSaving ? 'Guardando...' : 'Guardar Cambios'}</button>
      </div>
      
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <div className="bg-white dark:bg-slate-800 p-6 rounded-lg shadow-sm space-y-8">
            <div>
              <h3 className={sectionTitleClass}>General</h3>
              <div className="flex items-start justify-between gap-4">
                <div className="flex-grow"><label htmlFor="botName" className={labelClass}>Nombre del Bot</label><input id="botName" name="botName" value={config.botName} onChange={handleConfigChange} className={inputClass} /></div>
                <div className="text-right flex-shrink-0 pt-1"><label className={labelClass}>Mostrar "(beta)"</label><button type="button" onClick={() => setConfig(c => c ? {...c, showBetaBadge: !c.showBetaBadge} : null)} className={`${switchBase} mt-1 ${config.showBetaBadge ? switchChecked : switchUnchecked}`}><span className={`${switchKnobBase} ${config.showBetaBadge ? switchKnobChecked : switchKnobUnchecked}`} /></button></div>
              </div>
              <div className="mt-4"><label htmlFor="botDescription" className={labelClass}>Descripción (subtítulo)</label><input id="botDescription" name="botDescription" value={config.botDescription || ''} onChange={handleConfigChange} className={inputClass} /></div>
              <div className="mt-4"><label htmlFor="composerPlaceholder" className={labelClass}>Texto de la caja de mensaje</label><input id="composerPlaceholder" name="composerPlaceholder" value={config.composerPlaceholder || ''} onChange={handleConfigChange} className={inputClass} /></div>
            </div>
            <div>
              <h3 className={sectionTitleClass}>Comportamiento Inicial</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
                <div><label htmlFor="initialState" className={labelClass}>Estado Inicial del Chat</label><select id="initialState" name="initialState" value={config.initialState || ''} onChange={handleConfigChange} className={inputClass}><option value="closed">Cerrado</option><option value="open">Abierto</option></select></div>
                <div className={config.initialState === 'closed' ? '' : 'opacity-40 pointer-events-none'}><label htmlFor="initialStateText" className={labelClass}>Texto de Invitación</label><input id="initialStateText" name="initialStateText" value={config.initialStateText || ''} onChange={handleConfigChange} disabled={config.initialState !== 'closed'} className={inputClass}/></div>
              </div>
            </div>
            <div>
              <h3 className={sectionTitleClass}>Apariencia</h3>
              <div className="mb-4"><label htmlFor="themeMode" className={labelClass}>Tema de Color</label><select id="themeMode" name="themeMode" value={config.themeMode || 'system'} onChange={handleConfigChange} className={inputClass}><option value="light">Claro</option><option value="dark">Oscuro</option><option value="system">Automático (del Sistema Operativo)</option></select></div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div><label htmlFor="primaryColor" className={labelClass}>Color Principal</label><div className='flex items-center mt-1 space-x-3'><input type="color" id="primaryColor" name="primaryColor" data-section="theme" value={config.theme.primaryColor} onChange={handleConfigChange} className="w-12 h-10 p-1 bg-white border rounded-md cursor-pointer"/><span className='font-mono text-sm text-gray-500 dark:text-gray-400'>{config.theme.primaryColor}</span></div></div>
                <div><label htmlFor="avatarBackgroundColor" className={labelClass}>Fondo del Avatar</label><div className='flex items-center mt-1 space-x-3'><input type="color" id="avatarBackgroundColor" name="avatarBackgroundColor" data-section="theme" value={config.theme.avatarBackgroundColor} onChange={handleConfigChange} className="w-12 h-10 p-1 bg-white border rounded-md cursor-pointer"/><span className='font-mono text-sm text-gray-500 dark:text-gray-400'>{config.theme.avatarBackgroundColor}</span></div></div>
              </div>
            </div>
            <div>
              <h3 className={sectionTitleClass}>Avatares e Imágenes</h3>
              <div className="mt-4 space-y-4">
                <div><label htmlFor="avatarImageUrl" className={labelClass}>URL del Avatar (en el chat)</label><input id="avatarImageUrl" name="avatarImageUrl" type="text" placeholder="https-ejemplo.com/avatar.png" value={config.avatarImageUrl || ''} onChange={handleConfigChange} className={inputClass}/></div>
                <div><label htmlFor="floatingButtonImageUrl" className={labelClass}>URL del Botón Flotante</label><input id="floatingButtonImageUrl" name="floatingButtonImageUrl" type="text" placeholder="https-ejemplo.com/icono_chat.svg" value={config.floatingButtonImageUrl || ''} onChange={handleConfigChange} className={inputClass}/></div>
              </div>
            </div>
        </div>

        {/* --- COLUMNA DE VISTA PREVIA CORREGIDA --- */}
        <div className="lg:col-span-1">
          <div className="sticky top-24">
            <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-3">Vista Previa</h3>
            {/* ---> ESTE DIV YA NO TIENE COLOR DE FONDO <--- */}
            <div className="w-full max-w-sm mx-auto h-[600px] rounded-xl relative overflow-hidden">
                <ChatbotPreview 
                    config={config} 
                    apiKey={testApiKey} 
                    applicationId={testAppId} 
                />
            </div>
          </div>
        </div>
         {/* --- SECCIÓN DEL FOOTER MODIFICADA --- */}
            <div className={`${!isPremiumUser ? 'opacity-60' : ''}`}>
              <h3 className={sectionTitleClass}>Footer</h3>
              <div className={`p-4 mt-4 border rounded-md space-y-4 ${!isPremiumUser ? 'border-dashed dark:border-slate-600' : 'dark:border-slate-700'}`}>
                
                {/* Switch de Activar/Desactivar */}
                <div className="flex justify-between items-center">
                  <span className="text-sm font-medium dark:text-gray-300">Activar "Powered By"</span>
                  <button 
                    type="button" 
                    onClick={() => setConfig(c => c ? {...c, footerEnabled: !c.footerEnabled} : null)} 
                    disabled={!isPremiumUser}
                    className={`${switchBase} ${config.footerEnabled ? switchChecked : switchUnchecked} ${!isPremiumUser ? 'cursor-not-allowed' : ''}`}
                  >
                    <span className={`${switchKnobBase} ${config.footerEnabled ? switchKnobChecked : switchKnobUnchecked}`} />
                  </button>
                </div>
                
                {/* Inputs de Texto y Enlace */}
                <div className={`space-y-4 ${!config.footerEnabled || !isPremiumUser ? 'opacity-50 pointer-events-none' : ''}`}>
                    <div>
                      <label htmlFor="footerText" className={labelClass}>Texto del Footer</label>
                      <input id="footerText" name="footerText" value={config.footerText || ''} onChange={handleConfigChange} className={inputClass} disabled={!isPremiumUser} />
                    </div>
                    <div>
                      <label htmlFor="footerLink" className={labelClass}>Enlace del Footer</label>
                      <input id="footerLink" name="footerLink" value={config.footerLink || ''} onChange={handleConfigChange} className={inputClass} disabled={!isPremiumUser} />
                    </div>
                </div>

                {/* Mensaje de Premium */}
                {!isPremiumUser && (
                  <p className="mt-2 text-xs text-center text-indigo-500 dark:text-indigo-400 font-semibold">
                    ✨ Opción personalizable en el plan Premium
                  </p>
                )}

              </div>
            </div>

        </div>
      </div>
     
  );
};

export default AdminWebchatCustomizerPage;