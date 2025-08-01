// src/pages/AdminWebchatCustomizerPage.tsx
import React, { useState } from 'react';

// Este es el tipo de objeto que guardará la configuración del chat.
// Lo iremos ampliando a medida que añadamos más opciones.
type WebchatConfig = {
  botName: string;
  theme: {
    primaryColor: string;
    avatarBackgroundColor: string;
  };
  // Aquí añadiremos más cosas como avatar, textos, etc.
};

const initialConfig: WebchatConfig = {
  botName: 'Mi Asistente Virtual',
  theme: {
    primaryColor: '#1d4ed8', // Azul oscuro
    avatarBackgroundColor: '#bfdbfe', // Azul claro
  },
};

const AdminWebchatCustomizerPage: React.FC = () => {
  const [config, setConfig] = useState<WebchatConfig>(initialConfig);

  const handleConfigChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value, dataset } = e.target;
    
    // Si el input tiene 'data-section', es un campo anidado como el color
    if (dataset.section) {
      setConfig(prevConfig => ({
        ...prevConfig,
        [dataset.section as keyof WebchatConfig]: {
          ...(prevConfig[dataset.section as keyof typeof prevConfig] as object),
          [name]: value,
        },
      }));
    } else {
      setConfig(prevConfig => ({
        ...prevConfig,
        [name]: value,
      }));
    }
  };
  
  const handleSave = () => {
    // En un futuro, aquí se llamará a la API del backend para guardar.
    // Por ahora, solo lo mostramos en la consola.
    alert('Configuración "guardada". Revisa la consola del navegador.');
    console.log('CONFIGURACIÓN A GUARDAR:', JSON.stringify(config, null, 2));
  };

  // --- CLASES DE TAILWIND ---
  const labelClass = "block text-sm font-medium text-gray-700 dark:text-gray-300";
  const inputClass = "mt-1 block w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm text-gray-900 dark:text-white bg-white dark:bg-gray-900";

  return (
    <div className="p-4 md:p-6 bg-gray-50 dark:bg-gray-900/50 flex-grow">
      <div className="flex justify-between items-center mb-6">
          <div>
              <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
                  Personalizador de Webchat
              </h1>
              <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
                  Modifica la apariencia de tu ventana de chat flotante.
              </p>
          </div>
          <button onClick={handleSave} className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-md shadow-sm disabled:opacity-50">
              Guardar Cambios
          </button>
      </div>
      
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

          {/* COLUMNA DE FORMULARIO */}
          <div className="lg:col-span-2 bg-white dark:bg-slate-800 p-6 rounded-lg shadow-md space-y-8">
              <div className="space-y-4">
                <h3 className="text-lg font-medium leading-6 text-gray-900 dark:text-white">General</h3>
                <div>
                  <label htmlFor="botName" className={labelClass}>Nombre del Bot</label>
                  <input type="text" id="botName" name="botName" value={config.botName} onChange={handleConfigChange} className={inputClass} />
                </div>
              </div>
              
              <div className="space-y-4">
                <h3 className="text-lg font-medium leading-6 text-gray-900 dark:text-white">Apariencia</h3>
                <div>
                  <label htmlFor="primaryColor" className={labelClass}>Color Principal</label>
                  <input 
                    type="color" id="primaryColor" name="primaryColor" 
                    data-section="theme" value={config.theme.primaryColor} onChange={handleConfigChange} 
                    className="w-16 h-10 p-1 bg-white border border-gray-300 rounded-md cursor-pointer"
                  />
                  <span className='ml-2 text-gray-600 dark:text-gray-300 align-middle'>{config.theme.primaryColor}</span>
                </div>
              </div>
          </div>
          
          {/* COLUMNA DE VISTA PREVIA */}
          <div className="lg:col-span-1">
              <div className="sticky top-20">
                <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">Vista Previa</h3>
                <div className="aspect-w-9 aspect-h-16 bg-gray-200 dark:bg-slate-700 rounded-lg shadow-inner flex items-center justify-center p-4">
                  {/* Aquí, en el futuro, pondremos el componente de chat real */}
                  <p className="text-gray-500 dark:text-gray-400">La vista previa aparecerá aquí</p>
                </div>
              </div>
          </div>

      </div>
    </div>
  );
};

export default AdminWebchatCustomizerPage;