// src/pages/AdminUsersPage.tsx

import React, { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import toast, { Toaster } from 'react-hot-toast';

import {
    useReadAllAppUsersEndpointApiV1AdminAppUserManagementGet as useReadAllUsers,
    useCreateLocalAdminUserEndpointApiV1AdminAppUserManagementPost as useCreateUser,
    useUpdateAppUserEndpointApiV1AdminAppUserManagementAppUserIdPut as useUpdateUser,
    useDeleteAppUserEndpointApiV1AdminAppUserManagementAppUserIdDelete as useDeleteUser,
} from '../services/api/endpoints';
import type { AppUserResponse, AppUserUpdateByAdmin, AppUserLocalCreate } from '../services/api/schemas';
import type { AxiosError } from 'axios';

import Modal from '../components/shared/Modal';
import EditUserForm from '../components/admin/users/EditUserForm';
import { Button, IconButton } from '../components/shared/Button';
import PageHeader from '../components/ui/PageHeader';
import { PlusIcon, PencilSquareIcon, TrashIcon, CheckCircleIcon, XCircleIcon, ShieldCheckIcon } from '@heroicons/react/24/outline';

// --- 1. Definimos una clave única y consistente para la query de usuarios ---
const ADMIN_USERS_QUERY_KEY = ['adminUsersList'];

const AdminUsersPage: React.FC = () => {
    const queryClient = useQueryClient();

    const [isFormModalOpen, setIsFormModalOpen] = useState(false);
    const [isEditMode, setIsEditMode] = useState(false);
    const [selectedUser, setSelectedUser] = useState<AppUserResponse | null>(null);
    const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
    const [userToDelete, setUserToDelete] = useState<AppUserResponse | null>(null);

    // --- 2. Usamos nuestra clave explícita al obtener los datos ---
    const { data: users = [], isLoading: isLoadingUsers } = useReadAllUsers(
        { skip: 0, limit: 200 },
        { query: { queryKey: ADMIN_USERS_QUERY_KEY } }
    );

    const handleMutationError = (error: unknown, action: string) => {
        const axiosError = error as AxiosError<{ detail?: string }>;
        const message = axiosError.response?.data?.detail || `Error al ${action} el usuario.`;
        toast.error(message, { duration: 5000 });
    };

    const handleCloseModal = () => {
        // --- 3. ¡LA SOLUCIÓN! Simplificamos la función para que siempre cierre. ---
        setIsFormModalOpen(false);
        setSelectedUser(null);
    };

    const handleCloseDeleteModal = () => {
        setIsDeleteModalOpen(false);
        setUserToDelete(null);
    };

    // --- 4. Usamos la misma clave para invalidar y refrescar la tabla ---
    const updateUserMutation = useUpdateUser({
        mutation: {
            onSuccess: (updatedUser) => {
                toast.success(`Usuario "${updatedUser?.username_ad}" actualizado.`);
                queryClient.invalidateQueries({ queryKey: ADMIN_USERS_QUERY_KEY });
                handleCloseModal(); // Ahora esto funcionará
            },
            onError: (error) => handleMutationError(error, 'actualizar'),
        },
    });

    const createUserMutation = useCreateUser({
        mutation: {
            onSuccess: (newUser) => {
                toast.success(`Usuario "${newUser.username_ad}" creado exitosamente.`);
                queryClient.invalidateQueries({ queryKey: ADMIN_USERS_QUERY_KEY });
                handleCloseModal(); // Y esto también
            },
            onError: (error) => handleMutationError(error, 'crear'),
        },
    });

    const deleteUserMutation = useDeleteUser({
        mutation: {
            onSuccess: () => {
                toast.success(`Usuario "${userToDelete?.username_ad}" eliminado.`);
                queryClient.invalidateQueries({ queryKey: ADMIN_USERS_QUERY_KEY });
                handleCloseDeleteModal();
            },
            onError: (error) => handleMutationError(error, 'eliminar'),
        },
    });

    const isMutating = updateUserMutation.isPending || createUserMutation.isPending;

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

    const handleFormSubmit = (formData: AppUserUpdateByAdmin | AppUserLocalCreate) => {
        if (isEditMode && selectedUser) {
            updateUserMutation.mutate({ appUserId: selectedUser.id, data: formData as AppUserUpdateByAdmin });
        } else {
            createUserMutation.mutate({ data: formData as AppUserLocalCreate });
        }
    };

    const handleOpenDeleteModal = (user: AppUserResponse) => {
        setUserToDelete(user);
        setIsDeleteModalOpen(true);
    };

    const handleConfirmDelete = () => {
        if (!userToDelete) return;
        deleteUserMutation.mutate({ appUserId: userToDelete.id });
    };

    // ... (El resto del JSX se mantiene igual que la versión que te di antes)
    return (
        <>
            <Toaster position="top-right" />
            <PageHeader title="Usuarios Administradores">
                <Button onClick={handleOpenCreateModal} icon={<PlusIcon className="h-5 w-5" />}>
                    Crear Usuario Local
                </Button>
            </PageHeader>
            
            {isLoadingUsers && <p>Cargando usuarios...</p>}
            
            <div className="overflow-x-auto bg-white dark:bg-slate-800 shadow-md rounded-lg">
                <table className="w-full text-sm text-left text-gray-500 dark:text-gray-400">
                    <thead className="text-xs text-gray-700 uppercase bg-gray-50 dark:bg-slate-700 dark:text-gray-300">
                        <tr>
                            <th scope="col" className="px-6 py-3">ID</th>
                            <th scope="col" className="px-6 py-3">Username / DNI</th>
                            <th scope="col" className="px-6 py-3">Nombre Completo</th>
                            <th scope="col" className="px-6 py-3">Método Auth</th>
                            <th scope="col" className="px-6 py-3 text-center">Activo</th>
                            <th scope="col" className="px-6 py-3 text-center">MFA</th>
                            <th scope="col" className="px-6 py-3">Acciones</th>
                        </tr>
                    </thead>
                    <tbody>
                        {users.map(user => (
                            <tr key={user.id} className="bg-white dark:bg-slate-800 border-b dark:border-slate-700 hover:bg-gray-50 dark:hover:bg-slate-700/50">
                                <td className="px-6 py-4">{user.id}</td>
                                <th scope="row" className="px-6 py-4 font-medium text-gray-900 dark:text-white whitespace-nowrap">{user.username_ad}</th>
                                <td className="px-6 py-4">{user.full_name}</td>
                                <td className="px-6 py-4"><span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${user.auth_method === 'local' ? 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300' : 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300'}`}>{user.auth_method}</span></td>
                                <td className="px-6 py-4 text-center">{user.is_active_local ? <CheckCircleIcon className="h-5 w-5 text-green-500 mx-auto" /> : <XCircleIcon className="h-5 w-5 text-red-500 mx-auto" />}</td>
                                <td className="px-6 py-4 text-center">{user.mfa_enabled ? <ShieldCheckIcon className="h-5 w-5 text-blue-500 mx-auto" /> : <XCircleIcon className="h-5 w-5 text-gray-400 mx-auto" />}</td>
                                <td className="px-6 py-4 flex items-center space-x-2 justify-end">
                                    <IconButton icon={<PencilSquareIcon className="h-5 w-5"/>} onClick={() => handleOpenEditModal(user)} variant="ghost" aria-label="Editar" />
                                    <IconButton icon={<TrashIcon className="h-5 w-5"/>} onClick={() => handleOpenDeleteModal(user)} variant="ghost" className="text-red-500 hover:text-red-700" aria-label="Eliminar" />
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            <Modal isOpen={isFormModalOpen} onClose={handleCloseModal} title={isEditMode ? `Editar Usuario: ${selectedUser?.username_ad}` : "Crear Usuario Local"} size="2xl">
                <EditUserForm isEditMode={isEditMode} user={selectedUser} onFormSubmit={handleFormSubmit} onCancel={handleCloseModal} isSubmitting={isMutating} />
            </Modal>
            
            <Modal isOpen={isDeleteModalOpen} onClose={handleCloseDeleteModal} title="Confirmar Eliminación" footerContent={
                <>
                    <Button variant="secondary" onClick={handleCloseDeleteModal} disabled={deleteUserMutation.isPending}>Cancelar</Button>
                    <Button variant="danger" onClick={handleConfirmDelete} isLoading={deleteUserMutation.isPending}>Sí, Eliminar</Button>
                </>}>
                <p className="text-sm text-gray-700 dark:text-gray-300">¿Estás seguro de que quieres eliminar al usuario <strong className="font-semibold px-1">{userToDelete?.full_name || userToDelete?.username_ad}</strong>?</p>
            </Modal>
        </>
    );
};

export default AdminUsersPage;