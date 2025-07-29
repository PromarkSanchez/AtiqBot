// src/pages/AdminDbConnectionsPage.tsx
import React, { useState, useCallback } from 'react';
import {
  useReadAllDbConnectionsApiV1AdminDbConnectionsGet,
  useCreateNewDbConnectionApiV1AdminDbConnectionsPost,
  useUpdateExistingDbConnectionApiV1AdminDbConnectionsConnIdPut,
  useDeleteDbConnectionEntryApiV1AdminDbConnectionsConnIdDelete,
} from '../services/api/endpoints';
import type { 
  DatabaseConnectionResponse, 
  DatabaseConnectionCreate, 
  DatabaseConnectionUpdate,
  HTTPValidationError,
} from '../services/api/schemas';
import toast, { Toaster } from 'react-hot-toast';
import type { AxiosError } from 'axios';

import PageHeader from '../components/ui/PageHeader';
import Modal from '../components/shared/Modal';
import { Button, IconButton } from '../components/shared/Button';
import { PlusIcon, PencilSquareIcon, TrashIcon, InformationCircleIcon, WifiIcon } from '@heroicons/react/24/outline';
import DbConnectionForm from '../components/admin/db_connections/DbConnectionForm';

const AdminDbConnectionsPage: React.FC = () => {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isEditMode, setIsEditMode] = useState(false);
  const [selectedDbConnection, setSelectedDbConnection] = useState<DatabaseConnectionResponse | null>(null);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);

  const { data: dbConnectionsData, isLoading, error, refetch } = useReadAllDbConnectionsApiV1AdminDbConnectionsGet(
    { limit: 100 }, { query: { queryKey: ['adminDbConnectionsList'], staleTime: 60000 } }
  );
  
  const handleMutationError = useCallback((err: unknown, defaultMessage: string) => {
    const axiosError = err as AxiosError<HTTPValidationError | { detail?: string }>;
    const message = (axiosError.response?.data as any)?.detail || defaultMessage;
    toast.error(message, { duration: 5000 });
  }, []);

  const createMutation = useCreateNewDbConnectionApiV1AdminDbConnectionsPost({
    mutation: {
      onSuccess: () => { toast.success("Conexión creada con éxito."); refetch(); setIsModalOpen(false); },
      onError: (err) => handleMutationError(err, "Error al crear la conexión."),
    },
  });

  const updateMutation = useUpdateExistingDbConnectionApiV1AdminDbConnectionsConnIdPut({
    mutation: {
      onSuccess: () => { toast.success("Conexión actualizada con éxito."); refetch(); handleCloseModals(); },
      onError: (err) => handleMutationError(err, "Error al actualizar la conexión."),
    },
  });

  const deleteMutation = useDeleteDbConnectionEntryApiV1AdminDbConnectionsConnIdDelete({
    mutation: {
      onSuccess: () => { toast.success("Conexión eliminada con éxito."); refetch(); handleCloseModals(); },
      onError: (err) => handleMutationError(err, "Error al eliminar la conexión."),
    },
  });

  // --- Handlers de Modales y Forms ---
  const handleOpenCreateModal = () => { setIsEditMode(false); setSelectedDbConnection(null); setIsModalOpen(true); };
  const handleOpenEditModal = (conn: DatabaseConnectionResponse) => { setIsEditMode(true); setSelectedDbConnection(conn); setIsModalOpen(true); };
  const handleOpenDeleteModal = (conn: DatabaseConnectionResponse) => { setSelectedDbConnection(conn); setIsDeleteModalOpen(true); };
  const handleCloseModals = () => { if (isMutating) return; setIsModalOpen(false); setIsDeleteModalOpen(false); setSelectedDbConnection(null); };
  
  const handleFormSubmit = (formData: DatabaseConnectionCreate | DatabaseConnectionUpdate) => {
    if (isEditMode && selectedDbConnection) {
      updateMutation.mutate({ connId: selectedDbConnection.id, data: formData as DatabaseConnectionUpdate });
    } else {
      createMutation.mutate({ data: formData as DatabaseConnectionCreate });
    }
  };

  const handleConfirmDelete = () => {
    if (selectedDbConnection) deleteMutation.mutate({ connId: selectedDbConnection.id });
  };
  
  const handleTestConnection = (connId: number) => {
    toast.loading(`Probando conexión ID: ${connId}...`, { id: `test-${connId}` });
    // Aquí irá la lógica de la mutación para probar la conexión
    setTimeout(() => toast.success("¡Conexión exitosa! (Simulado)", {id: `test-${connId}`}), 2000);
  };
  
  const isMutating = createMutation.isPending || updateMutation.isPending || deleteMutation.isPending;
  const dbConnections = dbConnectionsData || [];

  return (
    <div>
      <Toaster position="top-center" />
      <PageHeader title="Conexiones de Base de Datos" subtitle="Configura las conexiones a bases de datos para el chatbot.">
        <Button onClick={handleOpenCreateModal} icon={<PlusIcon className="h-5 w-5" />} disabled={isMutating}>
          Nueva Conexión
        </Button>
      </PageHeader>
      
      {isLoading && <p className="text-center p-4 animate-pulse text-sm text-gray-700 dark:text-gray-300">Cargando conexiones...</p>}
      {error && <p className="text-center p-4 text-red-500 text-sm text-gray-700 dark:text-gray-300">Error al cargar: {error.message}</p>}
      
       {!isLoading && dbConnections.length === 0 && (
        <div className="text-center py-10 bg-white dark:bg-slate-800 shadow rounded-lg">
            <InformationCircleIcon className="mx-auto h-12 w-12 text-gray-400" />
            <h3 className="mt-2 text-sm font-medium text-gray-900 dark:text-white">No hay Conexiones</h3>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">Crea una nueva conexión a base de datos.</p>
            <div className="mt-6">
                <Button onClick={handleOpenCreateModal} disabled={isMutating} icon={<PlusIcon className="h-5 w-5" />}>
                    Crear Conexión
                </Button>
            </div>
        </div>
      )}

      {dbConnections.length > 0 && (
        <div className="shadow-md overflow-hidden border border-gray-200 dark:border-gray-700 rounded-lg">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200 dark:divide-slate-700">
              <thead className="bg-gray-50 dark:bg-slate-900/70">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-gray-500 dark:text-gray-300 uppercase tracking-wider">Nombre</th>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-gray-500 dark:text-gray-300 uppercase tracking-wider">Tipo</th>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-gray-500 dark:text-gray-300 uppercase tracking-wider">Host:Puerto</th>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-gray-500 dark:text-gray-300 uppercase tracking-wider">Usuario</th>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-gray-500 dark:text-gray-300 uppercase tracking-wider">Extra Params</th>
                  <th className="relative px-6 py-3"><span className="sr-only">Acciones</span></th>
                </tr>
              </thead>
              <tbody className="bg-white dark:bg-slate-800 divide-y divide-gray-200 dark:divide-slate-700">
                {dbConnections.map((conn) => (
                  <tr key={conn.id} className="hover:bg-gray-50 dark:hover:bg-slate-700/50">
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900 dark:text-white">{conn.name}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-300">{conn.db_type}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-300 font-mono">{conn.host}:{conn.port}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-300 font-mono">{conn.username}</td>
                    {/* Estilo corregido según tu feedback */}
                    <td className="px-6 py-4 text-xs text-gray-500 dark:text-gray-400 font-mono max-w-xs truncate hover:overflow-visible hover:whitespace-normal" title={conn.extra_params ? JSON.stringify(conn.extra_params, null, 2) : "{}"}>
                        {conn.extra_params && Object.keys(conn.extra_params).length > 0 ? JSON.stringify(conn.extra_params) : <span className="italic opacity-70">Ninguno</span>}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                      <div className="flex items-center justify-end space-x-2">
                        <IconButton icon={<WifiIcon className="h-5 w-5"/>} onClick={() => handleTestConnection(conn.id)} aria-label="Probar Conexión" variant="ghost" className="text-sky-600 hover:text-sky-800 dark:text-sky-400 dark:hover:text-sky-300" />
                        <IconButton icon={<PencilSquareIcon className="h-5 w-5"/>} onClick={() => handleOpenEditModal(conn)} aria-label="Editar" />
                        <IconButton icon={<TrashIcon className="h-5 w-5"/>} onClick={() => handleOpenDeleteModal(conn)} aria-label="Eliminar" variant="danger"/>
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
      <Modal isOpen={isModalOpen} onClose={handleCloseModals} title={isEditMode ? 'Editar Conexión' : 'Nueva Conexión a BD'} size="2xl">
        <DbConnectionForm
          dbConnection={selectedDbConnection}
          onFormSubmit={handleFormSubmit}
          onCancel={handleCloseModals}
          isSubmitting={createMutation.isPending || updateMutation.isPending}
          isEditMode={isEditMode}
        />
      </Modal>

      {selectedDbConnection && (
        <Modal
          isOpen={isDeleteModalOpen}
          onClose={handleCloseModals}
          title="Confirmar Eliminación"
          footerContent={
            <div className="flex justify-end space-x-3">
              <Button variant="secondary" onClick={handleCloseModals} disabled={deleteMutation.isPending}>Cancelar</Button>
              <Button variant="danger" onClick={handleConfirmDelete} isLoading={deleteMutation.isPending}>Eliminar</Button>
            </div>
          }>
          <p className="text-sm text-gray-700 dark:text-gray-300">¿Seguro que quieres eliminar la conexión "<strong>{selectedDbConnection.name}</strong>"?</p>
        </Modal>
      )}
      
    </div>
  );
};

export default AdminDbConnectionsPage;