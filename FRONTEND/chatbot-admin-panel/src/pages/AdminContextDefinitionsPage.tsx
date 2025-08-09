// src/pages/AdminContextDefinitionsPage.tsx

import React, { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import toast, { Toaster } from 'react-hot-toast';
import type { AxiosError } from 'axios';

// Componentes UI
import Modal from '../components/shared/Modal';
import { IconButton, Button } from '../components/shared/Button'; // Asegúrate de importar Button
import { CubeIcon, DocumentArrowUpIcon, PencilSquareIcon, TrashIcon, PlusIcon } from '@heroicons/react/24/outline';
import ContextDefinitionForm from '../components/admin/context-definitions/ContextDefinitionForm';
import DocumentUploaderForm from '../components/admin/context-definitions/DocumentUploaderForm';
import ManageDocumentsModal from '../components/admin/context-definitions/ManageDocumentsModal';

// Tipos de la API
import type {
  ContextDefinitionResponse,
  ContextDefinitionCreate,
  ContextDefinitionUpdate,
} from '../services/api/schemas';

// Hooks de la API
import {
  useReadAllContextDefinitionsEndpointApiV1AdminContextDefinitionsGet,
  useCreateNewContextDefinitionEndpointApiV1AdminContextDefinitionsPost,
  useUpdateExistingContextDefinitionEndpointApiV1AdminContextDefinitionsContextIdPut,
  useDeleteContextDefinitionEndpointApiV1AdminContextDefinitionsContextIdDelete,
} from '../services/api/endpoints';

const AdminContextDefinitionsPage: React.FC = () => {
  // Estados para los modales
  const [isFormModalOpen, setIsFormModalOpen] = useState(false);
  const [contextToEdit, setContextToEdit] = useState<ContextDefinitionResponse | null>(null);

  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [contextToDelete, setContextToDelete] = useState<ContextDefinitionResponse | null>(null);

  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [contextToUploadTo, setContextToUploadTo] = useState<ContextDefinitionResponse | null>(null);

  const [isManageModalOpen, setIsManageModalOpen] = useState(false);
  const [contextToManage, setContextToManage] = useState<ContextDefinitionResponse | null>(null);
  
  const queryClient = useQueryClient();

  // Hooks de datos y mutaciones
  const { data: contextDefinitionsData, isLoading, isError, error } = 
    useReadAllContextDefinitionsEndpointApiV1AdminContextDefinitionsGet(
      { skip: 0, limit: 100 },
      { query: { queryKey: ['adminContextDefinitionsList'], staleTime: 5 * 60 * 1000 } }
    );
  const contextDefinitions = contextDefinitionsData || [];

  const createMutation = useCreateNewContextDefinitionEndpointApiV1AdminContextDefinitionsPost({
    mutation: {
      onSuccess: (newContext) => { toast.success(`Definición "${newContext.name}" creada!`); queryClient.invalidateQueries({ queryKey: ['adminContextDefinitionsList'] }); handleCloseFormModal(); },
      onError: (err: any) => { const message = err.response?.data?.detail || "Error al crear."; toast.error(message); },
    },
  });

  const updateMutation = useUpdateExistingContextDefinitionEndpointApiV1AdminContextDefinitionsContextIdPut({
    mutation: {
      onSuccess: (updatedContext) => { toast.success(`Definición "${updatedContext.name}" actualizada!`); queryClient.invalidateQueries({ queryKey: ['adminContextDefinitionsList'] }); handleCloseFormModal(); },
      onError: (err: any) => { const message = err.response?.data?.detail || "Error al actualizar."; toast.error(message); },
    },
  });

  const deleteMutation = useDeleteContextDefinitionEndpointApiV1AdminContextDefinitionsContextIdDelete({
    mutation: {
      onSuccess: () => { toast.success(`Definición "${contextToDelete?.name}" eliminada.`); queryClient.invalidateQueries({ queryKey: ['adminContextDefinitionsList'] }); handleCloseDeleteModal(); },
      onError: (err: any) => { const message = err.response?.data?.detail || "Error al eliminar."; toast.error(message); handleCloseDeleteModal(); },
    }
  });

  const isMutationLoading = createMutation.isPending || updateMutation.isPending || deleteMutation.isPending;

  // Manejadores de eventos
  const handleOpenCreateModal = () => { setContextToEdit(null); setIsFormModalOpen(true); };
  const handleOpenEditModal = (contextDef: ContextDefinitionResponse) => { setContextToEdit(contextDef); setIsFormModalOpen(true); };
  const handleCloseFormModal = () => { setIsFormModalOpen(false); setContextToEdit(null); };

  const handleOpenDeleteModal = (contextDef: ContextDefinitionResponse) => { setContextToDelete(contextDef); setIsDeleteModalOpen(true); };
  const handleCloseDeleteModal = () => { setIsDeleteModalOpen(false); setContextToDelete(null); };
  
  const handleOpenUploadModal = (contextDef: ContextDefinitionResponse) => { setContextToUploadTo(contextDef); setIsUploadModalOpen(true); };
  const handleCloseUploadModal = () => { setIsUploadModalOpen(false); setContextToUploadTo(null); };

  const handleOpenManageModal = (contextDef: ContextDefinitionResponse) => { setContextToManage(contextDef); setIsManageModalOpen(true); };
  const handleCloseManageModal = () => { setIsManageModalOpen(false); setContextToManage(null); };

  const handleConfirmDelete = () => { if (contextToDelete?.id) { deleteMutation.mutate({ contextId: contextToDelete.id }); }};
  
  // --- ¡CORRECCIÓN EN EL MANEJADOR DEL FORMULARIO! ---
  // El formulario (`ContextDefinitionForm`) llama a `onSubmit` con dos argumentos,
  // pero solo nos interesa el primero (`formData`).
  const handleFormSubmit = async (formData: ContextDefinitionCreate | ContextDefinitionUpdate, isEditMode: boolean): Promise<void> => {
    try {
        if (isEditMode && contextToEdit && contextToEdit.id) {
            await updateMutation.mutateAsync({ 
                contextId: contextToEdit.id, 
                data: formData as ContextDefinitionUpdate 
            });
        } else {
            await createMutation.mutateAsync({ 
                data: formData as ContextDefinitionCreate 
            });
        }
    } catch (e) {
        // El hook onError ya muestra el toast, así que no necesitamos hacer nada aquí.
        // Pero el try/catch es una buena práctica por si mutateAsync falla de forma inesperada.
        console.error("Fallo la mutación del formulario de contexto:", e);
    }
};
  
  if (isLoading) { return <div className="p-6 text-center text-lg animate-pulse">Cargando definiciones...</div>; }
  if (isError) {
    const axiosError = error as AxiosError<{ detail?: string }>;
    const message = axiosError.response?.data?.detail || error.message || "Error cargando lista.";
    return <div className="p-6 text-red-600 text-center">Error: {message}</div>;
  }
  
  return (
    <div className="container mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <Toaster position="top-right" />
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-bold text-gray-800 dark:text-white">Definiciones de Contexto</h1>
        <Button onClick={handleOpenCreateModal} disabled={isMutationLoading} icon={<PlusIcon className="h-5 w-5"/>}>
          Crear Nueva
        </Button>
      </div>

      {contextDefinitions.length > 0 ? (
        <div className="shadow-lg overflow-hidden border border-gray-200 dark:border-gray-700 rounded-lg">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
              <thead className="bg-gray-50 dark:bg-slate-800">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">Nombre</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">Tipo</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">Estado</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">Visibilidad</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">Fuentes Doc.</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">Conex. BD</th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">Acciones</th>
                </tr>
              </thead>
              <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                {contextDefinitions.map((contextDef) => (
                  <tr key={contextDef.id} className={`${!contextDef.is_active ? 'opacity-60 bg-gray-100 dark:bg-slate-900' : ''} hover:bg-gray-50 dark:hover:bg-slate-700 transition-colors duration-150`}>
                    <td className="px-6 py-4 whitespace-nowrap"><div className="text-sm font-medium text-gray-900 dark:text-white">{contextDef.name}</div><div className="text-xs text-gray-500 dark:text-gray-400 max-w-xs truncate" title={contextDef.description || undefined}>{contextDef.description || '-'}</div></td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-700 dark:text-gray-300">{contextDef.main_type}</td>
                    <td className="px-6 py-4 whitespace-nowrap"><span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${contextDef.is_active ? 'bg-green-100 text-green-800 dark:bg-green-700/80 dark:text-green-100' : 'bg-red-100 text-red-800 dark:bg-red-700/80 dark:text-red-100'}`}>{contextDef.is_active ? 'Activo' : 'Inactivo'}</span></td>
                    <td className="px-6 py-4 whitespace-nowrap"><span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${contextDef.is_public ? 'bg-blue-100 text-blue-800 dark:bg-blue-700/80 dark:text-blue-100' : 'bg-yellow-100 text-yellow-800 dark:bg-yellow-700/80 dark:text-yellow-100'}`}>{contextDef.is_public ? 'Público' : 'Privado'}</span></td>
                    <td className="px-6 py-4 text-sm text-gray-700 dark:text-gray-300 max-w-xs truncate" title={contextDef.document_sources?.map(ds => ds.name).join(', ')}>{contextDef.document_sources?.map(ds => ds.name).join(', ') || '-'}</td>
                    <td className="px-6 py-4 text-sm text-gray-700 dark:text-gray-300 max-w-xs truncate">{contextDef.db_connection_config?.name || '-'}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                      <div className="flex justify-end items-center space-x-1">
                        {contextDef.main_type === 'DOCUMENTAL' && (
                          <>
                            <IconButton title="Gestionar Documentos" onClick={() => handleOpenManageModal(contextDef)} disabled={isMutationLoading} icon={<CubeIcon className="h-5 w-5" />} variant="ghost" className="text-blue-600 hover:text-blue-800" aria-label="Gestionar Documentos"/>
                            <IconButton title="Añadir Documentos" onClick={() => handleOpenUploadModal(contextDef)} disabled={isMutationLoading} icon={<DocumentArrowUpIcon className="h-5 w-5" />} variant="ghost" className="text-teal-600 hover:text-teal-800" aria-label="Añadir Documentos" />
                          </>
                        )}
                        <IconButton title="Editar Contexto" onClick={() => handleOpenEditModal(contextDef)} disabled={isMutationLoading} icon={<PencilSquareIcon className="h-5 w-5" />} variant="ghost" className="text-indigo-600 hover:text-indigo-800" aria-label="Editar" />
                        <IconButton title="Eliminar Contexto" onClick={() => handleOpenDeleteModal(contextDef)} disabled={isMutationLoading} icon={<TrashIcon className="h-5 w-5" />} variant="ghost" className="text-red-600 hover:text-red-800" aria-label="Eliminar" />
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div className="text-center py-10"><p className="text-lg text-gray-600 dark:text-gray-400">{isLoading ? 'Cargando...' : 'No hay definiciones de contexto.'}</p></div>
      )}

      {isFormModalOpen && (
        <Modal isOpen={isFormModalOpen} onClose={handleCloseFormModal} title={contextToEdit ? `Editar: ${contextToEdit.name}` : 'Crear Contexto'} size="4xl">
          <ContextDefinitionForm initialData={contextToEdit} onSubmit={handleFormSubmit} onCancel={handleCloseFormModal} isSubmittingGlobal={createMutation.isPending || updateMutation.isPending} isEditMode={!!contextToEdit} />
        </Modal>
      )}

      {isDeleteModalOpen && contextToDelete && (
        <Modal isOpen={isDeleteModalOpen} onClose={handleCloseDeleteModal} title="Confirmar Eliminación" footerContent={<><Button variant="secondary" onClick={handleCloseDeleteModal}>Cancelar</Button><Button variant="danger" onClick={handleConfirmDelete} isLoading={deleteMutation.isPending}>Eliminar</Button></>}>
          <p className="text-sm">¿Seguro que quieres eliminar <strong className="font-semibold">{contextToDelete?.name}</strong>?</p>
        </Modal>
      )}

      {isUploadModalOpen && contextToUploadTo && (
        <Modal isOpen={isUploadModalOpen} onClose={handleCloseUploadModal} title={`Añadir Documentos`} size="xl">
          <DocumentUploaderForm contextId={contextToUploadTo.id} contextName={contextToUploadTo.name} onUploadSuccess={handleCloseUploadModal} onCancel={handleCloseUploadModal} />
        </Modal>
      )}

      {isManageModalOpen && contextToManage && (
        <Modal isOpen={isManageModalOpen} onClose={handleCloseManageModal} title={`Gestionar Documentos de "${contextToManage.name}"`} size="lg">
          <ManageDocumentsModal contextId={contextToManage.id} contextName={contextToManage.name} onClose={handleCloseManageModal} />
        </Modal>
      )}
    </div>
  );
};

export default AdminContextDefinitionsPage;