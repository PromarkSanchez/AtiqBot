// src/pages/AdminDocSourcesPage.tsx
import React, { useState, useCallback } from 'react';
import {
  useReadAllDocumentSourcesApiV1AdminDocSourcesGet,
  useCreateNewDocumentSourceApiV1AdminDocSourcesPost,
  useUpdateExistingDocumentSourceApiV1AdminDocSourcesSourceIdPut,
  useDeleteDocumentSourceEntryApiV1AdminDocSourcesSourceIdDelete,
} from '../services/api/endpoints';
import type { 
  DocumentSourceResponse, 
  DocumentSourceCreate, 
  DocumentSourceUpdate,
} from '../services/api/schemas';
import toast, { Toaster } from 'react-hot-toast';

import PageHeader from '../components/ui/PageHeader';
import Modal from '../components/shared/Modal';
import { Button, IconButton } from '../components/shared/Button';
import { PencilSquareIcon, TrashIcon, PlusIcon, InformationCircleIcon, ArrowPathIcon } from '@heroicons/react/24/outline';
import DocSourceForm from '../components/admin/doc_sources/DocSourceForm';

const AdminDocSourcesPage: React.FC = () => {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isEditMode, setIsEditMode] = useState(false);
  const [selectedDocSource, setSelectedDocSource] = useState<DocumentSourceResponse | null>(null);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);

  // Hook para obtener todas las fuentes de documentos
  const {
    data: docSourcesData,
    isLoading,
    error,
    refetch,
  } = useReadAllDocumentSourcesApiV1AdminDocSourcesGet({ limit: 1000 }, {
    query: { queryKey: ['adminDocSourcesList'], staleTime: 60000 }
  });
  const docSources = docSourcesData || [];

  // --- Lógica de Mutaciones y Manejo de Errores ---
  const handleMutationError = useCallback((_err: unknown, defaultMessage: string) => {
    let message = defaultMessage;
    // ... tu lógica de manejo de errores si la tienes ...
    toast.error(message, { duration: 5000 });
  }, []);

  const createMutation = useCreateNewDocumentSourceApiV1AdminDocSourcesPost({
    mutation: {
      onSuccess: () => {
        toast.success("Fuente de Documento creada con éxito.");
        refetch();
        setIsModalOpen(false);
      },
      onError: (err) => handleMutationError(err, "Error al crear la fuente."),
    }
  });

  const updateMutation = useUpdateExistingDocumentSourceApiV1AdminDocSourcesSourceIdPut({
    mutation: {
      onSuccess: () => {
        toast.success("Fuente de Documento actualizada con éxito.");
        refetch();
        setIsModalOpen(false);
      },
      onError: (err) => handleMutationError(err, "Error al actualizar la fuente."),
    }
  });

  const deleteMutation = useDeleteDocumentSourceEntryApiV1AdminDocSourcesSourceIdDelete({
    mutation: {
      onSuccess: () => {
        toast.success("Fuente de Documento eliminada con éxito.");
        refetch();
        setIsDeleteModalOpen(false);
      },
      onError: (err) => handleMutationError(err, "Error al eliminar la fuente."),
    }
  });

  // --- Handlers para Modales y Formularios ---
  const handleOpenCreateModal = () => {
    setIsEditMode(false);
    setSelectedDocSource(null);
    setIsModalOpen(true);
  };

  const handleOpenEditModal = (source: DocumentSourceResponse) => {
    setIsEditMode(true);
    setSelectedDocSource(source);
    setIsModalOpen(true);
  };
  
  const handleOpenDeleteModal = (source: DocumentSourceResponse) => {
    setSelectedDocSource(source);
    setIsDeleteModalOpen(true);
  };
  
  const handleCloseModal = () => {
      if(isSubmitting) return;
      setIsModalOpen(false);
      setSelectedDocSource(null);
  }

  const handleCloseDeleteModal = () => {
      if(deleteMutation.isPending) return;
      setIsDeleteModalOpen(false);
      setSelectedDocSource(null);
  }

  const handleFormSubmit = (data: DocumentSourceCreate | DocumentSourceUpdate) => {
    if (isEditMode && selectedDocSource) {
      updateMutation.mutate({ sourceId: selectedDocSource.id, data: data as DocumentSourceUpdate });
    } else {
      createMutation.mutate({ data: data as DocumentSourceCreate });
    }
  };

  const handleConfirmDelete = () => {
    if (selectedDocSource) {
      deleteMutation.mutate({ sourceId: selectedDocSource.id });
    }
  };
  
  const handleForceSync = (source: DocumentSourceResponse) => {
    toast.loading(`Iniciando sincronización para "${source.name}"...`, {id: `sync-${source.id}`});
    // Aquí iría la llamada a la mutación de sincronización
    // e.g., syncMutation.mutate({ sourceId: source.id });
    setTimeout(() => toast.success(`Sincronización para "${source.name}" completada (simulado).`, {id: `sync-${source.id}`}), 2000);
  };

  const isSubmitting = createMutation.isPending || updateMutation.isPending;

  return (
    <div>
      <Toaster position="top-center" />
      <PageHeader title="Fuentes de Documentos">
        <Button onClick={handleOpenCreateModal} icon={<PlusIcon className="h-5 w-5" />} disabled={isSubmitting}>
          Nueva Fuente
        </Button>
      </PageHeader>
      
      {isLoading && docSources.length === 0 && (
         <div className="p-8 text-center"><p className="animate-pulse text-lg text-gray-600 dark:text-gray-300">Cargando fuentes...</p></div> 
      )}
      {error && (
         <div className="p-8 text-center text-red-500">Error al cargar datos: {error.message}</div> 
      )}
      {!isLoading && docSources.length === 0 && !error && (
         <div className="text-center py-10 bg-white dark:bg-slate-800 shadow rounded-lg">
            <InformationCircleIcon className="mx-auto h-12 w-12 text-gray-400" />
            <h3 className="mt-2 text-sm font-medium text-gray-900 dark:text-white">No hay Fuentes de Documentos</h3>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">Crea una nueva fuente para empezar a ingestar documentos.</p>
            <div className="mt-6">
                <Button onClick={handleOpenCreateModal} disabled={isSubmitting} icon={<PlusIcon className="h-5 w-5" />}>
                    Crear Fuente de Documentos
                </Button>
            </div>
         </div>
      )}
      {docSources.length > 0 && (
        <div className="shadow-md overflow-hidden border border-gray-200 dark:border-gray-700 rounded-lg">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200 dark:divide-slate-700">
              <thead className="bg-gray-50 dark:bg-slate-900/70">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 dark:text-gray-300 uppercase tracking-wider">Nombre</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 dark:text-gray-300 uppercase tracking-wider">Tipo</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 dark:text-gray-300 uppercase tracking-wider">Path / Config</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 dark:text-gray-300 uppercase tracking-wider">Última Sincronización</th>
                  <th className="px-4 py-3 text-center text-xs font-semibold text-gray-500 dark:text-gray-300 uppercase tracking-wider">Acciones</th>
                </tr>
              </thead>
              <tbody className="bg-white dark:bg-slate-800 divide-y divide-gray-200 dark:divide-slate-700">
                {docSources.map((source) => (
                  <tr key={source.id} className="hover:bg-gray-50 dark:hover:bg-slate-700/50">
                    <td className="px-4 py-3 whitespace-nowrap text-sm font-medium text-gray-900 dark:text-white">{source.name}</td>
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500 dark:text-gray-300">{source.source_type.replace(/_/g, ' ')}</td>
                    <td className="px-4 py-3 text-xs text-gray-500 dark:text-gray-400 font-mono max-w-xs overflow-hidden hover:overflow-visible hover:whitespace-normal" title={typeof source.path_or_config === 'object' ? JSON.stringify(source.path_or_config, null, 2) : String(source.path_or_config)}>
                      {typeof source.path_or_config === 'object' ? JSON.stringify(source.path_or_config) : String(source.path_or_config)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-center">
                        <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${
                            source.is_active 
                                ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200' 
                                : 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300'
                        }`}>
                            {source.is_active ? 'Activa' : 'Inactiva'}
                        </span>
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500 dark:text-gray-300">{source.last_synced_at ? new Date(source.last_synced_at).toLocaleString() : 'Nunca'}</td>
                    <td className="px-4 py-3 whitespace-nowrap text-center text-sm">
                      <div className="flex items-center justify-center space-x-2">
                        <IconButton icon={<ArrowPathIcon className="h-5 w-5"/>} onClick={() => handleForceSync(source)} aria-label="Forzar Sincronización" variant="ghost" className="text-sky-600 hover:text-sky-800 dark:text-sky-400 dark:hover:text-sky-300" />
                        <IconButton icon={<PencilSquareIcon className="h-5 w-5"/>} onClick={() => handleOpenEditModal(source)} aria-label="Editar" variant="ghost" className="text-indigo-600 hover:text-indigo-800 dark:text-indigo-400 dark:hover:text-indigo-300" />
                        <IconButton icon={<TrashIcon className="h-5 w-5"/>} onClick={() => handleOpenDeleteModal(source)} aria-label="Eliminar" variant="ghost" className="text-red-600 hover:text-red-800 dark:text-red-400 dark:hover:text-red-300" />
                      </div>
                    </td>
                    
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
      
      {/* --- Modales --- */}
      <Modal 
        isOpen={isModalOpen} 
        onClose={handleCloseModal} 
        title={isEditMode ? 'Editar Fuente de Documento' : 'Nueva Fuente de Documento'}
        size="2xl"
      >
        <DocSourceForm 
          onFormSubmit={handleFormSubmit}
          onCancel={handleCloseModal}
          isSubmitting={isSubmitting}
          isEditMode={isEditMode}
          docSource={selectedDocSource}
        />
      </Modal>

      {selectedDocSource && (
        <Modal 
          isOpen={isDeleteModalOpen} 
          onClose={handleCloseDeleteModal}
          title="Confirmar Eliminación"
          footerContent={
            <div className="flex justify-end space-x-3">
              <Button variant="secondary" onClick={handleCloseDeleteModal} disabled={deleteMutation.isPending}>Cancelar</Button>
              <Button variant="danger" onClick={handleConfirmDelete} isLoading={deleteMutation.isPending}>
                {deleteMutation.isPending ? "Eliminando..." : "Sí, Eliminar"}
              </Button>
            </div>
          }
        >
          <p className="text-sm text-gray-700 dark:text-gray-300">¿Seguro que quieres eliminar la fuente "<strong>{selectedDocSource.name}</strong>"?</p>
        </Modal>
      )}
    </div>
  );
};

export default AdminDocSourcesPage;