// src/pages/AdminApiClientsPage.tsx
import React, { useState, useEffect, useCallback } from 'react';
import {
  // Hooks generados por Orval con los nuevos operation_id
  useReadAllApiClientsEndpointApiV1AdminApiClientsGet as useReadAllApiClients,
  useCreateNewApiClientEndpointApiV1AdminApiClientsPost as useCreateNewApiClient,
  useUpdateExistingApiClientEndpointApiV1AdminApiClientsApiClientIdPut as useUpdateApiClientById,
  useDeleteApiClientEndpointApiV1AdminApiClientsApiClientIdDelete as  useDeleteApiClientById,
  useRegenerateApiKeyForClientEndpointApiV1AdminApiClientsApiClientIdRegenerateKeyPost  as useRegenerateApiKeyForClient,
} from '../services/api/endpoints'; 

import type { 
  ApiClientResponse,                 // Para GET all, GET by ID, PUT
  ApiClientWithPlainKeyResponse,     // Para POST create, POST regenerate_key
  ApiClientCreate, 
  ApiClientUpdate, 
  HTTPValidationError,
  ApiClientSettingsSchema,
  ReadAllApiClientsParams,           // Tipo para los parámetros del hook readAllApiClients
} from '../services/api/schemas';
import type { AxiosError } from 'axios';
import toast, { Toaster } from 'react-hot-toast';

import Modal from '../components/shared/Modal';
import ApiClientForm from '../components/admin/api_clients/ApiClientForm'; 
import { Button, IconButton } from '../components/shared/Button'; 
import { PencilSquareIcon, PlusIcon, PlayCircleIcon, InformationCircleIcon, KeyIcon, TrashIcon, PaintBrushIcon } from '@heroicons/react/24/outline'; 
 
// Al principio de src/pages/AdminApiClientsPage.tsx
import { Link } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query'; 

// ...resto de tus imports


const getAppIdFromSettings = (settings: ApiClientSettingsSchema | undefined | null): string | undefined => {
  return settings?.application_id; 
};

const AdminApiClientsPage: React.FC = () => {
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [selectedApiClientForOps, setSelectedApiClientForOps] = useState<ApiClientResponse | ApiClientWithPlainKeyResponse | null>(null);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [apiKeyToDisplay, setApiKeyToDisplay] = useState<string | null>(null);

  const queryParams: ReadAllApiClientsParams = { skip: 0, limit: 100 }; 
  // <--- CAMBIO 2: Obtén la instancia del Query Client
  const queryClient = useQueryClient();
  const {
    data: apiClientsData, 
    isLoading: isLoadingApiClients,
    error: apiClientsQueryError,
    isError: isApiClientsQueryError,
    refetch: refetchApiClients,
  } = useReadAllApiClients( // <-- Usando el nombre de hook corto/nuevo
    queryParams, 
    { query: { queryKey: ['adminApiClientsList', queryParams], staleTime: 60000 } }
  );

  const apiClients: ApiClientResponse[] = apiClientsData || [];

  const handleMutationError = useCallback((error: unknown, defaultMessage: string, toastId?: string) => { 
    const axiosError = error as AxiosError<HTTPValidationError | { detail?: string }>;
    let message = defaultMessage;
    const errorData = axiosError.response?.data;

    if (errorData && typeof errorData === 'object' && 'detail' in errorData) {
      const detail = (errorData as { detail: any }).detail;
      if (typeof detail === 'string') { message = detail; }
      else if (Array.isArray(detail) && detail.length > 0 && 'msg' in detail[0] && 'loc' in detail[0]) {
        message = detail.map((d: any) => `${d.loc?.join(' -> ') || 'Error'} - ${d.msg}`).join('; ');
      }
    } else if (axiosError.message) { message = axiosError.message; }
    
    toast.error(message, { id: toastId || String(Date.now()), duration: 7000 });
    console.error(`API Client Op Error: ${defaultMessage}`, JSON.stringify(errorData) || axiosError.message || error);
  }, []);
  
  useEffect(() => { 
     if (isApiClientsQueryError && apiClientsQueryError && !isLoadingApiClients) {
        handleMutationError(apiClientsQueryError, "Error al cargar Clientes API.", "apiClientsListError");
    }
  }, [isApiClientsQueryError, apiClientsQueryError, isLoadingApiClients, handleMutationError]);

  // IMPORTANTE: El tipo de `responseFromApi` es inferido por el hook de Orval.
  // Debe ser `ApiClientWithPlainKeyResponse` para que `api_key_plain` esté disponible.
  const createApiClientMutation = useCreateNewApiClient({ // <-- Usando el nombre de hook corto/nuevo
    mutation: {
      onSuccess: (responseFromApi: ApiClientWithPlainKeyResponse) => { 
        toast.success(`Cliente API "${responseFromApi.name}" creado.`);
        queryClient.invalidateQueries({ queryKey: ['adminApiClientsList'] });

        if (responseFromApi.api_key_plain) { 
          setApiKeyToDisplay(responseFromApi.api_key_plain);
            localStorage.setItem('test_chat_api_key', responseFromApi.api_key_plain);
          if(responseFromApi.settings?.application_id) {
              localStorage.setItem('test_chat_app_id', responseFromApi.settings.application_id);
          }
        } else {
          toast((t) => (
            <div className={`${t.visible ? 'animate-enter' : 'animate-leave'} max-w-md w-full bg-yellow-100 dark:bg-yellow-800 shadow-lg rounded-lg pointer-events-auto flex ring-1 ring-black ring-opacity-5 p-3`}>
              <InformationCircleIcon className="h-6 w-6 text-yellow-500 mr-2 shrink-0"/>
              <div className="flex-1">
                  <p className="text-sm font-medium text-yellow-800 dark:text-yellow-200">Atención</p>
                  <p className="mt-1 text-sm text-yellow-700 dark:text-yellow-300">Cliente ID creada pero el backend no devolvió el valor visible. Intenta regenerarla.</p>
              </div>
            </div>
          ), {id: 'createKeyInfoNotVisible', duration: 8000});
        }
        refetchApiClients(); 
        setIsCreateModalOpen(false);
      },
      onError: (error) => handleMutationError(error, "Error al crear Cliente API", "createClientError"),
    },
  });

  const updateApiClientMutation = useUpdateApiClientById({ // <-- Usando el nombre de hook corto/nuevo
     mutation: {
      onSuccess: (updatedApiClient: ApiClientResponse) => { // El update no devuelve la clave
        toast.success(`Cliente API "${updatedApiClient.name}" actualizado.`);
        queryClient.invalidateQueries({ queryKey: ['adminApiClientsList'] });

        refetchApiClients(); 
        handleCloseEditModal();
      },
      onError: (error) => handleMutationError(error, "Error al actualizar Cliente API", "updateClientError"),
    },
  });

  const deleteApiClientMutation = useDeleteApiClientById({ // <-- Usando el nombre de hook corto/nuevo
     mutation: {
      onSuccess: () => {
        toast.success(`Cliente API "${selectedApiClientForOps?.name || 'seleccionado'}" eliminado.`);
        queryClient.invalidateQueries({ queryKey: ['adminApiClientsList'] });
        refetchApiClients(); 
        handleCloseDeleteModal();
      },
      onError: (error) => {
        handleMutationError(error, `Error al eliminar Cliente API "${selectedApiClientForOps?.name || ''}"`, "deleteClientError");
      },
    },
   });
  
  const regenerateApiKeyMutation = useRegenerateApiKeyForClient({ // <-- Usando el nombre de hook corto/nuevo
    mutation: {
      onSuccess: (responseFromApi: ApiClientWithPlainKeyResponse) => { // Correctamente tipado
      queryClient.invalidateQueries({ queryKey: ['adminApiClientsList'] });  
        if (responseFromApi?.api_key_plain) {
            toast.success(`Nueva Cliente ID Generado para "${responseFromApi.name}". Cópialo ahora.`);
            setApiKeyToDisplay(responseFromApi.api_key_plain);
              localStorage.setItem('test_chat_api_key', responseFromApi.api_key_plain);
          if(responseFromApi.settings?.application_id) {
            localStorage.setItem('test_chat_app_id', responseFromApi.settings.application_id);
          }
        } else {
           toast.error(`No se pudo mostrar la nueva Cliente ID para "${responseFromApi?.name}". Contacta soporte.`, {id: 'regenKeyErrorNotVisible'});
        }
        refetchApiClients();
      },
      onError: (error) => handleMutationError(error, "Error al regenerar Cliente ID.", "regenerateKeyError")
    }
  });

  // Lógica para el modal de CREACIÓN
  const handleOpenCreateModal = () => {
    setSelectedApiClientForOps(null);
    setIsCreateModalOpen(true);
  };

  const handleCloseCreateModal = () => {
    setIsCreateModalOpen(false); 
  };
  
  const handleCreateSubmit = (formData: ApiClientCreate | ApiClientUpdate) => {
      createApiClientMutation.mutate({ data: formData as ApiClientCreate });
  };


  // Lógica para el modal de EDICIÓN
  const handleOpenEditModal = (client: ApiClientResponse) => {
    setSelectedApiClientForOps(client);
    setIsEditModalOpen(true);
  };

  const handleCloseEditModal = () => {
    setIsEditModalOpen(false);
    setSelectedApiClientForOps(null);
  };

  const handleEditSubmit = (formData: ApiClientCreate | ApiClientUpdate) => { 
    if (!selectedApiClientForOps?.id) return;
    updateApiClientMutation.mutate({ apiClientId: selectedApiClientForOps.id, data: formData as ApiClientUpdate });
  };


  // Lógica para el modal de ELIMINACIÓN
  const handleOpenDeleteModal = (client: ApiClientResponse) => {
    setSelectedApiClientForOps(client);
    setIsDeleteModalOpen(true);
  };

  const handleCloseDeleteModal = () => {
    setIsDeleteModalOpen(false);
    setSelectedApiClientForOps(null);
  };
  
  const handleConfirmDelete = () => { 
    if (!selectedApiClientForOps?.id) return; 
    deleteApiClientMutation.mutate({ apiClientId: selectedApiClientForOps.id }); 
  };
  
  const handleRegenerateKey = (client: ApiClientResponse) => { 
    if (window.confirm(`¿Regenerar Cliente ID para "${client.name}"? La clave actual se invalidará y la nueva deberá copiarse inmediatamente.`)) { 
      setSelectedApiClientForOps(client); // Para que isLoadingSomeMutation refleje estado en el botón
      regenerateApiKeyMutation.mutate({ apiClientId: client.id }); 
    } 
  };
  const handleOpenChatTestWindow = () => { window.open('/admin/test-chat', '_blank', 'resizable=yes,scrollbars=yes,width=900,height=750'); };

  const isLoadingSomeMutation = 
    createApiClientMutation.isPending || 
    updateApiClientMutation.isPending || 
    deleteApiClientMutation.isPending || 
    regenerateApiKeyMutation.isPending;

  // --- JSX ---
  return (
    <div className="container mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <Toaster position="top-center" containerClassName="text-sm" toastOptions={{duration: 4000}}/>
      <header className="flex flex-wrap justify-between items-center mb-6 gap-4">
        <h1 className="text-2xl md:text-3xl font-bold text-gray-800 dark:text-white">Gestión de Clientes API</h1>
        <div className="flex space-x-3">
          <Button 
            variant="outline" 
            onClick={handleOpenChatTestWindow} 
            icon={<PlayCircleIcon className="h-5 w-5" />}
            className="border-green-600 text-green-700 hover:bg-green-50 dark:text-green-400 dark:border-green-500 dark:hover:bg-green-700/30"
            title="Abrir ventana para probar el chat"
          >
            Probar Chat
          </Button>
          <Button 
            onClick={handleOpenCreateModal} 
            disabled={isLoadingSomeMutation}
            icon={<PlusIcon className="h-5 w-5" />}
          >
            {createApiClientMutation.isPending ? 'Creando...' : 'Crear Cliente API'}
          </Button>
        </div>
      </header>

      {apiKeyToDisplay && (
        <Modal isOpen={!!apiKeyToDisplay} onClose={() => {if (!regenerateApiKeyMutation.isPending && !createApiClientMutation.isPending) setApiKeyToDisplay(null);}} title="Cliente ID Generado ¡Copia Inmediatamente!">
          <div className="p-4 md:p-6 space-y-4">
            <p className="text-sm text-gray-700 dark:text-gray-300">Esta es la <strong className="text-red-600 dark:text-red-400">única vez</strong> que se mostrará esta Cliente ID. Cópialo y guárdalo en un lugar seguro.</p>
            <textarea 
              value={apiKeyToDisplay} 
              readOnly 
              rows={3}
              className="w-full p-2 border border-gray-300 dark:border-gray-600 rounded bg-gray-100 dark:bg-gray-800 font-mono text-xs px-4 py-3 whitespace-nowrap text-sm text-gray-600 dark:text-gray-300 font-mono" 
              onClick={(e) => (e.target as HTMLTextAreaElement).select()}
            />
            <div className="flex justify-end space-x-3">
              <Button variant="primary" onClick={() => { navigator.clipboard.writeText(apiKeyToDisplay); toast.success("Cliente ID copiada!"); }} className="bg-blue-500 hover:bg-blue-600 text-xs px-3 py-1.5">Copiar</Button>
              <Button variant="secondary" onClick={() => setApiKeyToDisplay(null)} className="text-xs px-3 py-1.5">Cerrar</Button>
            </div>
          </div>
        </Modal>
      )}

      {isLoadingApiClients && apiClients.length === 0 && !isApiClientsQueryError && (
         <div className="p-8 text-center"><p className="animate-pulse text-lg text-gray-600 dark:text-gray-300">Cargando Clientes API...</p></div> 
      )}
      {!isLoadingApiClients && apiClients.length === 0 && !isApiClientsQueryError && (
         <div className="text-center py-10 bg-white dark:bg-slate-800 shadow rounded-lg">
            <InformationCircleIcon className="mx-auto h-12 w-12 text-gray-400" />
            <h3 className="mt-2 text-sm font-medium text-gray-900 dark:text-white">No hay Clientes API</h3>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">Empieza creando un nuevo cliente API para habilitar el acceso al chatbot.</p>
            <div className="mt-6">
                <Button onClick={handleOpenCreateModal} disabled={isLoadingSomeMutation} icon={<PlusIcon className="h-5 w-5" />}>
                    Crear Cliente API
                </Button>
            </div>
         </div>
      )}
      {apiClients.length > 0 && (
        <div className="shadow-md border border-gray-200 dark:border-gray-700 rounded-lg">
          <div className="table-responsive-wrapper">
            <table className="min-w-full divide-y divide-gray-200 dark:divide-slate-700">
              <thead className="bg-gray-50 dark:bg-slate-900/70 sticky top-0 z-10">
                <tr>
                  <th scope="col" className="px-4 py-3 text-left text-xs font-semibold text-gray-500 dark:text-gray-300 uppercase tracking-wider">ID</th>
                  <th scope="col" className="px-4 py-3 text-left text-xs font-semibold text-gray-500 dark:text-gray-300 uppercase tracking-wider">Nombre</th>
                  <th scope="col" className="px-4 py-3 text-left text-xs font-semibold text-gray-500 dark:text-gray-300 uppercase tracking-wider">App ID</th>
                  <th scope="col" className="px-4 py-3 text-left text-xs font-semibold text-gray-500 dark:text-gray-300 uppercase tracking-wider">Contextos</th>
                  <th scope="col" className="px-4 py-3 text-center text-xs font-semibold text-gray-500 dark:text-gray-300 uppercase tracking-wider">Activo</th>
                  <th scope="col" className="px-4 py-3 text-left text-xs font-semibold text-gray-500 dark:text-gray-300 uppercase tracking-wider whitespace-nowrap">Otros Settings</th>
                  <th scope="col" className="px-4 py-3 text-center text-xs font-semibold text-gray-500 dark:text-gray-300 uppercase tracking-wider">Acciones</th>
                </tr>
              </thead>
              <tbody className="bg-white dark:bg-slate-800 divide-y divide-gray-200 dark:divide-slate-700">
                {apiClients.map((client) => (
                  <tr key={client.id} className={`hover:bg-gray-50 dark:hover:bg-slate-700/50 transition-colors duration-150 ${!client.is_active ? 'opacity-60' : ''}`}>
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">{client.id}</td>
                    <td className={`px-4 py-3 whitespace-nowrap text-sm font-medium ${client.is_active ? 'text-gray-900 dark:text-white' : 'text-gray-500 dark:text-slate-400'}`}>{client.name}</td>
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-600 dark:text-gray-300 font-mono">
                        {getAppIdFromSettings(client.settings) || <span className="italic text-gray-400 dark:text-gray-500">-</span>}
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-600 dark:text-gray-300 max-w-xs truncate" title={client.allowed_contexts_details?.map(ctx => `${ctx.name || `ID:${ctx.id}`} (ID: ${ctx.id})`).join(', ') || 'Ninguno'}>
                        {client.allowed_contexts_details && client.allowed_contexts_details.length > 0 
                          ? client.allowed_contexts_details.map(ctx => ctx.name || `ID:${ctx.id}`).join(', ') 
                          : <span className="italic text-gray-400 dark:text-gray-500">-</span>
                        }
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-center">
                      <span className={`px-2.5 py-1 inline-flex text-xs leading-5 font-semibold rounded-full ${client.is_active ? 'bg-green-100 text-green-800 dark:bg-green-700/80 dark:text-green-100' : 'bg-red-100 text-red-800 dark:bg-red-700/80 dark:text-red-100'}`}>
                        {client.is_active ? 'Sí' : 'No'}
                      </span>
                    </td>
                     <td className="px-4 py-3 max-w-xs">
                      {client.settings && Object.keys(Object.fromEntries(Object.entries(client.settings).filter(([key]) => !['application_id', 'allowed_context_ids'].includes(key)))).length > 0 ? 
                        <details className="text-xs cursor-pointer">
                          <summary className="text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 outline-none focus:outline-none select-none">Ver JSON</summary>
                          <pre className="mt-1 p-2 bg-gray-100 dark:bg-slate-700/50 rounded text-gray-700 dark:text-gray-300 font-mono text-xs whitespace-pre-wrap break-all max-h-32 overflow-y-auto">
                            {JSON.stringify(
                              Object.fromEntries(Object.entries(client.settings).filter(([key]) => !['application_id', 'allowed_context_ids'].includes(key))),
                              null, 2
                            )}
                          </pre> 
                        </details>
                        : <span className="italic text-gray-400 dark:text-gray-500 text-xs">-</span>
                      }
                    </td>
                    
                     <td className="px-4 py-3 whitespace-nowrap text-center text-sm">
                        <div className="flex items-center justify-center space-x-1 md:space-x-2">
                          
                          {/* =============== INICIO DE LA MODIFICACIÓN =============== */}

                          {/* BOTÓN 1: PERSONALIZAR UI (¡NUESTRO BOTÓN!) */}
                          <Link to={`/admin/webchat-customizer/${client.id}`} className="block">
                            <IconButton 
                                aria-label="Personalizar Interfaz" 
                                title="Personalizar Webchat UI" 
                                icon={<PaintBrushIcon className="h-5 w-5"/>} 
                                variant="ghost" 
                                className="text-cyan-600 hover:text-cyan-800 dark:text-cyan-400 dark:hover:text-cyan-300" 
                            />
                          </Link>

                          {/* BOTÓN 2: EDITAR CLIENTE (el que ya tenías) */}
                          <IconButton aria-label="Editar" onClick={() => handleOpenEditModal(client)} icon={<PencilSquareIcon className="h-5 w-5"/>} variant="ghost" className="text-indigo-600 hover:text-indigo-900 dark:text-indigo-400 dark:hover:text-indigo-300" disabled={isLoadingSomeMutation && selectedApiClientForOps?.id === client.id}/>
                          
                          {/* BOTÓN 3: REGENERAR KEY (el que ya tenías) */}
                          <IconButton aria-label="Regenerar Cliente ID" onClick={() => handleRegenerateKey(client)} icon={<KeyIcon className="h-5 w-5"/>} variant="ghost" className="text-yellow-500 hover:text-yellow-700 dark:text-yellow-400 dark:hover:text-yellow-300" disabled={isLoadingSomeMutation && selectedApiClientForOps?.id === client.id}/>
                          
                          {/* BOTÓN 4: ELIMINAR (el que ya tenías) */}
                          <IconButton aria-label="Eliminar" onClick={() => handleOpenDeleteModal(client)} icon={<TrashIcon className="h-5 w-5"/>} variant="ghost" className="text-red-600 hover:text-red-800 dark:text-red-400 dark:hover:text-red-300" disabled={isLoadingSomeMutation && selectedApiClientForOps?.id === client.id}/>
                          
                          {/* ================ FIN DE LA MODIFICACIÓN ================ */}
                        </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
      {isLoadingApiClients && apiClients.length > 0 && (
            <div className="text-center text-xs text-gray-500 dark:text-gray-400 pt-2">Actualizando lista...</div>
      )}

      {isCreateModalOpen && ( 
        <Modal isOpen={isCreateModalOpen} onClose={handleCloseCreateModal} title="Crear Nuevo Cliente API" size="3xl"> 
          <ApiClientForm onFormSubmit={handleCreateSubmit} onCancel={handleCloseCreateModal} isSubmitting={createApiClientMutation.isPending} isEditMode={false} /> 
        </Modal> 
      )}
      {selectedApiClientForOps && isEditModalOpen && ( 
        <Modal isOpen={isEditModalOpen} onClose={handleCloseEditModal} title={`Editar Cliente API: ${selectedApiClientForOps.name}`} size="3xl"> 
          <ApiClientForm apiClient={selectedApiClientForOps as ApiClientResponse} onFormSubmit={handleEditSubmit} onCancel={handleCloseEditModal} isSubmitting={updateApiClientMutation.isPending} isEditMode={true} /> 
        </Modal> 
      )}
      {selectedApiClientForOps && isDeleteModalOpen && ( 
        <Modal isOpen={isDeleteModalOpen} onClose={handleCloseDeleteModal} title="Confirmar Eliminación"
            footerContent={
                <div className="flex justify-end space-x-3">
                    <Button variant="secondary" onClick={handleCloseDeleteModal} disabled={deleteApiClientMutation.isPending}>Cancelar</Button>
                    <Button variant="danger" onClick={handleConfirmDelete} isLoading={deleteApiClientMutation.isPending} icon={<TrashIcon className="h-5 w-5"/>}>
                        {deleteApiClientMutation.isPending ? "Eliminando..." : "Eliminar"}
                    </Button>
                </div>
            }> 
            <p className="text-sm text-gray-700 dark:text-gray-300">¿Seguro que quieres eliminar el cliente API <strong className="font-semibold px-1">{selectedApiClientForOps.name}</strong>? Esta acción no se puede deshacer.</p> 
        </Modal> 
      )}
    </div>
  );
};
export default AdminApiClientsPage;