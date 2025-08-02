// src/pages/AdminUsersPage.tsx
import React, { useState } from 'react';
import { 
  useReadAllAppUsersEndpointApiV1AdminAppUserManagementGet,
  useUpdateAppUserEndpointApiV1AdminAppUserManagementAppUserIdPut as useUpdateAppUserByAdminIdEndpointApiV1AdminAppUserManagementAppUserIdPut,
  useDeleteAppUserEndpointApiV1AdminAppUserManagementAppUserIdDelete as useDeleteAppUserByAdminEndpointApiV1AdminAppUserManagementAppUserIdDelete, 
  // --> AÑADIMOS EL HOOK PARA CREAR
  useCreateLocalAdminUserEndpointApiV1AdminAppUserManagementPost,
} from '../services/api/endpoints'; 

// --> AÑADIMOS EL TIPO AppUserLocalCreate
import type { AppUserResponse, AppUserUpdateByAdmin, AppUserLocalCreate } from '../services/api/schemas';
import type { AxiosError } from 'axios';
import { useQueryClient } from '@tanstack/react-query'; // Añadimos para invalidar caché
import toast, { Toaster } from 'react-hot-toast'; 

import Modal from '../components/shared/Modal';
import EditUserForm from '../components/admin/users/EditUserForm'; // Se mantiene el nombre del form
import { Button } from '../components/shared/Button'; // Para el nuevo botón
import { PlusIcon } from '@heroicons/react/24/outline'; // Icono para el botón

const AdminUsersPage: React.FC = () => {
  const queryClient = useQueryClient();

  // --> UNIFICAMOS Y CLARIFICAMOS LOS ESTADOS
  const [isFormModalOpen, setIsFormModalOpen] = useState(false);  // Modal para crear o editar
  const [isEditMode, setIsEditMode] = useState(false);              // Para saber en qué modo está el form
  const [selectedUser, setSelectedUser] = useState<AppUserResponse | null>(null);

  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [userToDelete, setUserToDelete] = useState<AppUserResponse | null>(null);

  const {
    data: apiResponse,
    isLoading: isLoadingUsers,
    isError: isUsersError,
  } = useReadAllAppUsersEndpointApiV1AdminAppUserManagementGet({ skip: 0, limit: 200 });

  // --- LAS 3 MUTACIONES ---
  const updateUserMutation = useUpdateAppUserByAdminIdEndpointApiV1AdminAppUserManagementAppUserIdPut({ 
    mutation: {
      onSuccess: (updatedUser) => {
        toast.success(`Usuario "${updatedUser?.username_ad}" actualizado.`);
        queryClient.invalidateQueries({ queryKey: ['readAllAppUsersEndpointApiV1AdminAppUserManagementGet'] });
        handleCloseModal();
      },
      onError: () => { /* Tu manejo de error existente */ },
    },
  });
  
  const deleteUserMutation = useDeleteAppUserByAdminEndpointApiV1AdminAppUserManagementAppUserIdDelete({
    mutation: {
      onSuccess: () => {
        toast.success(`Usuario "${userToDelete?.username_ad}" eliminado.`);
        queryClient.invalidateQueries({ queryKey: ['readAllAppUsersEndpointApiV1AdminAppUserManagementGet'] });
        handleCloseDeleteModal();
      },
      onError: () => { /* Tu manejo de error existente */ },
    }
  });

  const createUserMutation = useCreateLocalAdminUserEndpointApiV1AdminAppUserManagementPost({
    mutation: {
      onSuccess: (newUser) => {
        toast.success(`Usuario "${newUser.username_ad}" creado exitosamente.`);
        queryClient.invalidateQueries({ queryKey: ['readAllAppUsersEndpointApiV1AdminAppUserManagementGet'] });
        handleCloseModal();
      },
      onError: (error) => { /* Adaptamos tu manejo de error para 'create' */ 
        const axiosError = error as AxiosError<{ detail?: string }>;
        const message = axiosError.response?.data?.detail || "Error al crear el usuario.";
        toast.error(message, { duration: 5000 });
      },
    },
  });

  const isMutating = updateUserMutation.isPending || deleteUserMutation.isPending || createUserMutation.isPending;

  // --- HANDLERS UNIFICADOS ---
  const handleOpenEditModal = (user: AppUserResponse) => {
    setIsEditMode(true);
    setSelectedUser(user);
    setIsFormModalOpen(true);
  };
  
  const handleOpenCreateModal = () => {
    setIsEditMode(false);
    setSelectedUser(null);
    setIsFormModalOpen(true);
  };

  const handleCloseModal = () => {
    if (isMutating) return;
    setIsFormModalOpen(false);
    setSelectedUser(null);
  };
  
  // --> HANDLER DE SUBMIT DUAL <--
  const handleFormSubmit = (formData: AppUserUpdateByAdmin | AppUserLocalCreate) => {
    if (isEditMode && selectedUser) {
      if (!selectedUser.id) return toast.error("Usuario inválido para actualizar.");
      updateUserMutation.mutate({ appUserId: selectedUser.id, data: formData as AppUserUpdateByAdmin });
    } else {
      createUserMutation.mutate({ data: formData as AppUserLocalCreate });
    }
  };

  const handleOpenDeleteModal = (user: AppUserResponse) => {
    setUserToDelete(user);
    setIsDeleteModalOpen(true);
  };

  const handleCloseDeleteModal = () => {
    if (deleteUserMutation.isPending) return;
    setIsDeleteModalOpen(false);
    setUserToDelete(null);
  };

  const handleConfirmDelete = () => {
    if (!userToDelete) return toast.error("Usuario no válido para eliminar.");
    deleteUserMutation.mutate({ appUserId: userToDelete.id });
  };
  
  if (isLoadingUsers) { return <div>Cargando...</div>; }
  if (isUsersError) { return <div>Error al cargar usuarios.</div>; }

  const users: AppUserResponse[] = apiResponse || [];

  return (
    <div className="container mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <Toaster position="top-right" />
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-bold text-gray-800 dark:text-white">
          Usuarios Administradores
        </h1>
        {/* --> EL NUEVO BOTÓN <-- */}
        <Button onClick={handleOpenCreateModal} disabled={isMutating}>
            <PlusIcon className="h-5 w-5 mr-2" />
            Crear Usuario Local
        </Button>
      </div>

      {users.length > 0 ? (
        <div className="shadow-lg overflow-hidden border border-gray-200 dark:border-gray-700 rounded-lg">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700"> 
              <thead className="bg-gray-50 dark:bg-gray-800">
              <tr>

                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">ID</th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Usuario AD</th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Nombre</th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Email</th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">MFA</th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Activo (Local)</th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Roles</th>
                  <th scope="col" className="px-6 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider whitespace-nowrap">Acciones</th>
              </tr>
            </thead>
              <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
              {users.map((user) => (
                  
                    <tr key={user.id} className={`${!user.is_active_local ? 'opacity-60 bg-gray-100 dark:bg-slate-900' : ''} 
                      hover:bg-gray-50 dark:hover:bg-slate-700 transition-colors duration-150`}>

                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600 dark:text-gray-300">{user.id}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900 dark:text-white">{user.username_ad}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-700 dark:text-gray-300">{user.full_name || 'N/A'}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-700 dark:text-gray-300">{user.email || 'N/A'}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm">
                      <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${ user.mfa_enabled ? 'bg-green-100 text-green-800 dark:bg-green-600 dark:text-green-100' : 'bg-red-100 text-red-800 dark:bg-red-600 dark:text-red-100' }`}> {user.mfa_enabled ? 'Sí' : 'No'} </span>
                  </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm">
                    <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${ user.is_active_local ? 'bg-green-100 text-green-800 dark:bg-green-600 dark:text-green-100' : 'bg-yellow-100 text-yellow-800 dark:bg-yellow-600 dark:text-yellow-100' }`}> {user.is_active_local ? 'Sí' : 'No'} </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-700 dark:text-gray-300"> {user.roles && user.roles.length > 0 ? user.roles.map(role => role.name).join(', ') : 'Sin roles'} </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                      <button 
                        onClick={() => handleOpenEditModal(user)}
                        className="text-indigo-600 hover:text-indigo-800 dark:text-indigo-400 dark:hover:text-indigo-300 mr-3"
                      >
                        Editar
                      </button>
              
                      {user.is_active_local ? (
                        <button 
                          onClick={() => handleOpenDeleteModal(user)}
                          disabled={deleteUserMutation.isPending || updateUserMutation.isPending}
                          className="text-red-600 hover:text-red-800 dark:text-red-400 dark:hover:text-red-300 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          Eliminar
                        </button>
                      ) : (
                        <span className="text-xs text-gray-400 dark:text-gray-500 italic">Inactivo</span>
                        
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        </div>
      ) : (
        <div className="text-center py-10">
          <p className="text-lg text-gray-600 dark:text-gray-400">
            {isLoadingUsers ? 'Cargando...' : 'No se encontraron usuarios administradores.'}
          </p>
        </div>
      )}

      {/* --> MODAL UNIFICADO PARA CREAR Y EDITAR <-- */}
      <Modal
        isOpen={isFormModalOpen}
        onClose={handleCloseModal}
        title={isEditMode ? `Editar Usuario: ${selectedUser?.username_ad}` : "Crear Nuevo Usuario Local"}
      >
        <EditUserForm
          user={selectedUser}
          onFormSubmit={handleFormSubmit}
          onCancel={handleCloseModal}
          isSubmitting={isMutating}
          isEditMode={isEditMode}
        />
      </Modal>
      
      {/* Tu modal de delete, solo con la variable correcta */}
      <Modal
        isOpen={isDeleteModalOpen}
        onClose={handleCloseDeleteModal}
        title="Confirmar Eliminación"
        footerContent={
          <>
            <button
              type="button"
              onClick={handleCloseDeleteModal}
              disabled={deleteUserMutation.isPending} // Usa el estado isPending de deleteUserMutation
              className="mr-2 px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-slate-700 border border-gray-300 dark:border-slate-600 rounded-md hover:bg-gray-50 dark:hover:bg-slate-600 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-70"
            >
              Cancelar
            </button>
            <button
              onClick={handleConfirmDelete}
              disabled={deleteUserMutation.isPending} // Usa el estado isPending de deleteUserMutation
              className="px-4 py-2 text-sm font-medium text-white bg-red-600 hover:bg-red-700 border border-transparent rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 disabled:opacity-70 disabled:cursor-not-allowed"
            >
              {deleteUserMutation.isPending ? 'Eliminando...' : 'Sí, Eliminar'}
            </button>
          </>
        }      >
        
        <p className="text-sm text-gray-700 dark:text-gray-300">
          ¿Estás seguro de que quieres eliminar al usuario 
          <strong className="font-semibold px-1">{userToDelete?.full_name || userToDelete?.username_ad}</strong>?
          Esta acción no se puede deshacer. {/* O ajusta el mensaje si es eliminación lógica */}
        </p>
      </Modal>
    </div>
  );
};

export default AdminUsersPage;