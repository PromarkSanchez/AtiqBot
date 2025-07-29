// src/pages/AdminDbConnectionsPage.tsx
import React, { useState, useEffect } from 'react';
import {
  // ### REEMPLAZA CON TUS HOOKS REALES DE ORVAL ###
  useReadAllDbConnectionsApiV1AdminDbConnectionsGet,
  useCreateNewDbConnectionApiV1AdminDbConnectionsPost,
  useUpdateExistingDbConnectionApiV1AdminDbConnectionsConnIdPut,
  useDeleteDbConnectionEntryApiV1AdminDbConnectionsConnIdDelete,
} from '../services/api/endpoints';
import type { 
  DatabaseConnectionResponse, 
  DatabaseConnectionCreate, 
  DatabaseConnectionUpdate} from '../services/api/schemas';
import toast, { Toaster } from 'react-hot-toast';

import Modal from '../components/shared/Modal';
import DbConnectionForm from '../components/admin/db_connections/DbConnectionForm'; // Ajusta la ruta

const AdminDbConnectionsPage: React.FC = () => {
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [selectedDbConnection, setSelectedDbConnection] = useState<DatabaseConnectionResponse | null>(null);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);

  const queryParams = { skip: 0, limit: 100 };
  const {
    data: dbConnectionsResponse,
    isLoading: isLoadingConnections,
    refetch: refetchDbConnections,
    error: listError, // Para el error de listado
    isError: isListError,
  } = useReadAllDbConnectionsApiV1AdminDbConnectionsGet(queryParams, {
    query: { queryKey: ['adminDbConnectionsList', queryParams] }
  });
  
  useEffect(() => { // Para mostrar error de listado
    if (isListError && listError) {
      handleMutationError(listError, "Error al cargar conexiones de BD.");
    }
  }, [isListError, listError]);


  const handleMutationError = (_error: unknown, _defaultMessage: string,_toastId?: string) => { /* ... (misma función que antes) ... */};

  const createDbConnectionMutation = useCreateNewDbConnectionApiV1AdminDbConnectionsPost({
    mutation: {
      onSuccess: (newConn) => {
        toast.success(`Conexión "${newConn.name}" creada.`);
        refetchDbConnections();
        setIsCreateModalOpen(false);
      },
      onError: (err) => handleMutationError(err, "Error al crear conexión."),
    },
  });

  const updateDbConnectionMutation = useUpdateExistingDbConnectionApiV1AdminDbConnectionsConnIdPut({
    mutation: {
      onSuccess: (updatedConn) => {
        toast.success(`Conexión "${updatedConn.name}" actualizada.`);
        refetchDbConnections();
        handleCloseEditModal();
      },
      onError: (err) => handleMutationError(err, "Error al actualizar conexión."),
    },
  });

  const deleteDbConnectionMutation = useDeleteDbConnectionEntryApiV1AdminDbConnectionsConnIdDelete({
    mutation: {
      onSuccess: () => {
        toast.success(`Conexión "${selectedDbConnection?.name}" eliminada.`);
        refetchDbConnections();
        handleCloseDeleteModal();
      },
      onError: (err) => handleMutationError(err, "Error al eliminar conexión."),
    },
  });

  // Handlers para Modales y Forms
  const handleOpenCreateModal = () => setIsCreateModalOpen(true);
  const handleCloseCreateModal = () => {if(!createDbConnectionMutation.isPending) setIsCreateModalOpen(false)};
  const handleCreateSubmit = (formData: DatabaseConnectionCreate | Partial<DatabaseConnectionUpdate>) => {
    createDbConnectionMutation.mutate({ data: formData as DatabaseConnectionCreate });
  };

  const handleOpenEditModal = (conn: DatabaseConnectionResponse) => {setSelectedDbConnection(conn); setIsEditModalOpen(true);};
  const handleCloseEditModal = () => {if(!updateDbConnectionMutation.isPending) setIsEditModalOpen(false); setSelectedDbConnection(null);};
  const handleEditSubmit = (formData: DatabaseConnectionCreate | Partial<DatabaseConnectionUpdate>) => {
    if (!selectedDbConnection) return;
    updateDbConnectionMutation.mutate({ connId: selectedDbConnection.id, data: formData as DatabaseConnectionUpdate });
  };
  
  const handleOpenDeleteModal = (conn: DatabaseConnectionResponse) => {setSelectedDbConnection(conn); setIsDeleteModalOpen(true);};
  const handleCloseDeleteModal = () => {if(!deleteDbConnectionMutation.isPending) setIsDeleteModalOpen(false); setSelectedDbConnection(null);};
  const handleConfirmDelete = () => {
    if (!selectedDbConnection) return;
    deleteDbConnectionMutation.mutate({ connId: selectedDbConnection.id });
  };

  // Botón de "Probar Conexión" (Placeholder)
  const handleTestConnection = (connId: number) => {
    toast.loading(`Probando conexión ID: ${connId}... (Funcionalidad no implementada)`, {id: `test-${connId}`});
    // Aquí llamarías a la mutación para probar conexión si la tuvieras
    // Ejemplo: testConnectionMutation.mutate({ connId });
    // setTimeout(() => toast.success("¡Conexión exitosa!", {id: `test-${connId}`}), 2000); 
    // setTimeout(() => toast.error("Falló la conexión.", {id: `test-${connId}`}), 2000);
  };

  if (isLoadingConnections) return <div className="p-8 text-center text-lg animate-pulse">Cargando conexiones...</div>;
  // No mostramos error de listado aquí porque lo maneja el useEffect con toast

  const dbConnections: DatabaseConnectionResponse[] = dbConnectionsResponse || [];
  
  // Clases de botón (igual que en ApiClientsPage)
  const btnPrimaryClass = "px-4 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-70 disabled:cursor-not-allowed";
  const btnSecondaryClass = "mr-2 px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-slate-700 border border-gray-300 dark:border-slate-600 rounded-md hover:bg-gray-50 dark:hover:bg-slate-600 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-70";
  const btnDangerClass = "px-4 py-2 text-sm font-medium text-white bg-red-600 hover:bg-red-700 border border-transparent rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 disabled:opacity-70 disabled:cursor-not-allowed";
  const actionButtonClass = "disabled:opacity-50 disabled:cursor-not-allowed text-xs px-2 py-1 rounded";

  return (
    <div className="container mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <Toaster position="top-right" containerClassName="text-sm"/>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-bold text-gray-800 dark:text-white">Conexiones de Base de Datos</h1>
        <button onClick={handleOpenCreateModal} disabled={createDbConnectionMutation.isPending} className={btnPrimaryClass}>
          {createDbConnectionMutation.isPending ? "Creando..." : "Nueva Conexión"}
        </button>
      </div>

      {dbConnections.length > 0 ? (
        <div className="shadow-lg overflow-hidden border border-gray-200 dark:border-gray-700 rounded-lg">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
              <thead className="bg-gray-50 dark:bg-gray-800">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">ID</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">Nombre</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">Tipo BD</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">Host:Puerto</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">Usuario</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">Extra Params</th>
                  <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">Acciones</th>
                </tr>
              </thead>
              <tbody className="bg-white dark:bg-slate-800 divide-y divide-gray-200 dark:divide-slate-700">
                {dbConnections.map((conn) => (
                  <tr key={conn.id} className="hover:bg-gray-50 dark:hover:bg-slate-700">
                    <td className="px-4 py-3 text-sm text-gray-600 dark:text-gray-300">{conn.id}</td>
                    <td className="px-4 py-3 text-sm font-medium text-gray-900 dark:text-white">{conn.name}</td>
                    <td className="px-4 py-3 text-sm text-gray-700 dark:text-gray-300">{conn.db_type}</td>
                    <td className="px-4 py-3 text-sm text-gray-700 dark:text-gray-300">{conn.host}:{conn.port}</td>
                    <td className="px-4 py-3 text-sm text-gray-700 dark:text-gray-300">{conn.username}</td>
                    <td className="px-4 py-3 text-xs text-gray-500 dark:text-gray-400 font-mono max-w-xs overflow-hidden hover:overflow-visible hover:whitespace-normal" title={conn.extra_params ? JSON.stringify(conn.extra_params, null, 2) : "{}"}>
                        {conn.extra_params ? JSON.stringify(conn.extra_params) : "{}"}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-center text-sm font-medium space-x-1">
                        <button onClick={() => handleTestConnection(conn.id)} className={`text-sky-500 hover:text-sky-700 dark:text-sky-400 dark:hover:text-sky-300 ${actionButtonClass}`}>Probar</button>
                        <button onClick={() => handleOpenEditModal(conn)} className={`text-indigo-500 hover:text-indigo-700 dark:text-indigo-300 dark:hover:text-indigo-200 ${actionButtonClass}`}>Editar</button>
                        <button onClick={() => handleOpenDeleteModal(conn)} className={`text-red-500 hover:text-red-700 dark:text-red-300 dark:hover:text-red-200 ${actionButtonClass}`}>Eliminar</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : ( <p className="text-center py-10 bg-white dark:bg-slate-800 shadow rounded-lg text-gray-600 dark:text-gray-400">{isLoadingConnections ? 'Cargando...' : 'No hay conexiones de base de datos configuradas.'}</p> )}

      {isCreateModalOpen && (
        <Modal isOpen={isCreateModalOpen} onClose={handleCloseCreateModal} title="Nueva Conexión a Base de Datos">
          <DbConnectionForm onFormSubmit={handleCreateSubmit} onCancel={handleCloseCreateModal} isSubmitting={createDbConnectionMutation.isPending} isEditMode={false} />
        </Modal>
      )}
      {selectedDbConnection && isEditModalOpen && (
        <Modal isOpen={isEditModalOpen} onClose={handleCloseEditModal} title={`Editar Conexión: ${selectedDbConnection.name}`}>
          <DbConnectionForm dbConnection={selectedDbConnection} onFormSubmit={handleEditSubmit} onCancel={handleCloseEditModal} isSubmitting={updateDbConnectionMutation.isPending} isEditMode={true} />
        </Modal>
      )}
      {selectedDbConnection && isDeleteModalOpen && (
        <Modal isOpen={isDeleteModalOpen} onClose={handleCloseDeleteModal} title="Confirmar Eliminación" footerContent={
          <>
            <button type="button" onClick={handleCloseDeleteModal} disabled={deleteDbConnectionMutation.isPending} className={btnSecondaryClass}>Cancelar</button>
            <button onClick={handleConfirmDelete} disabled={deleteDbConnectionMutation.isPending} className={btnDangerClass}>
              {deleteDbConnectionMutation.isPending ? 'Eliminando...' : 'Sí, Eliminar'}
            </button>
          </>
        }>
          <p className="text-sm text-gray-700 dark:text-gray-300">¿Seguro que quieres eliminar la conexión <strong className="px-1">{selectedDbConnection.name}</strong>?</p>
        </Modal>
      )}
    </div>
  );
};

export default AdminDbConnectionsPage;