// src/pages/AdminRolesPage.tsx
import React, { useState } from 'react';
import { 
  useReadAllRolesEndpointApiV1AdminRolesGet,
  useCreateNewRoleEndpointApiV1AdminRolesPost,
  useUpdateExistingRoleEndpointApiV1AdminRolesRoleIdPut,
  useDeleteExistingRoleEndpointApiV1AdminRolesRoleIdDelete,
  useAssignMenuPermissionToRoleApiV1AdminRolesRoleIdMenusPost,
  useRemoveMenuPermissionFromRoleApiV1AdminRolesRoleIdMenusMenuIdDelete,
} from '../services/api/endpoints';
import type { RoleResponse, RoleCreate, RoleUpdate } from '../services/api/schemas'; 
import toast, { Toaster } from 'react-hot-toast';

import Modal from '../components/shared/Modal';
import RoleForm from '../components/admin/roles/RoleForm';
import PageHeader from '../components/ui/PageHeader'; // Importación corregida
import { Button, IconButton } from '../components/shared/Button';
import { PlusIcon, PencilSquareIcon, TrashIcon } from '@heroicons/react/24/outline';

const AdminRolesPage: React.FC = () => {
  // --- Estados ---
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isEditMode, setIsEditMode] = useState(false);
  const [selectedRole, setSelectedRole] = useState<RoleResponse | null>(null);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);

  // --- Hooks de React Query ---
  const { data: rolesResponse, isLoading: isLoadingRoles, refetch: refetchRoles } = useReadAllRolesEndpointApiV1AdminRolesGet({ limit: 100 });
  
  const createRoleMutation = useCreateNewRoleEndpointApiV1AdminRolesPost();
  const updateRoleMutation = useUpdateExistingRoleEndpointApiV1AdminRolesRoleIdPut();
  const deleteRoleMutation = useDeleteExistingRoleEndpointApiV1AdminRolesRoleIdDelete();
  const assignMenuMutation = useAssignMenuPermissionToRoleApiV1AdminRolesRoleIdMenusPost();
  const removeMenuMutation = useRemoveMenuPermissionFromRoleApiV1AdminRolesRoleIdMenusMenuIdDelete();

  // --- Handlers de Modales ---
  const handleOpenCreateModal = () => {
    setIsEditMode(false);
    setSelectedRole(null);
    setIsModalOpen(true);
  };
  
  const handleOpenEditModal = (role: RoleResponse) => {
    setIsEditMode(true);
    setSelectedRole(role);
    setIsModalOpen(true);
  };

  const handleOpenDeleteModal = (role: RoleResponse) => {
    setSelectedRole(role);
    setIsDeleteModalOpen(true);
  };

  const handleCloseModals = () => {
    if (isMutating) return; // No cerrar si una mutación está en curso
    setIsModalOpen(false);
    setIsDeleteModalOpen(false);
    setSelectedRole(null);
  };

  // --- Handlers de Submit ---
  const handleFormSubmit = async (roleData: RoleUpdate, permissions: { added: number[], removed: number[] }) => {
    // Si es modo de creación (pasado desde el modal)
    if (!isEditMode) {
      toast.loading('Creando rol...', { id: 'create-role' });
      const createPayload = { name: roleData.name, description: roleData.description } as RoleCreate
      createRoleMutation.mutate({ data: createPayload }, {
          onSuccess: (newRole) => { toast.success(`Rol "${newRole.name}" creado.`, { id: 'create-role' }); refetchRoles(); handleCloseModals(); },
          onError: (error) => { toast.error((error as any).response?.data?.detail || 'Error al crear.', { id: 'create-role' }); }
      });
      return;
    }
    
    // Lógica para modo de edición
    if (!selectedRole?.id) return;
    const roleId = selectedRole.id;
    const hasRoleInfoChanged = roleData.name !== undefined || roleData.description !== undefined;
    const hasPermissionsChanged = permissions.added.length > 0 || permissions.removed.length > 0;

    if (!hasRoleInfoChanged && !hasPermissionsChanged) {
        toast("No se detectaron cambios.", { icon: 'ℹ️' });
        handleCloseModals();
        return;
    }
    
    toast.loading('Guardando cambios...', { id: 'saving-role' });
    const promises = [];
    if (hasRoleInfoChanged) promises.push(updateRoleMutation.mutateAsync({ roleId, data: roleData }));
    permissions.added.forEach(menuId => promises.push(assignMenuMutation.mutateAsync({ roleId, data: { menu_id: menuId } })));
    permissions.removed.forEach(menuId => promises.push(removeMenuMutation.mutateAsync({ roleId, menuId })));
    
    try {
        await Promise.all(promises);
        toast.success('Rol y permisos actualizados.', { id: 'saving-role' });
        refetchRoles();
    } catch (error) {
        toast.error('Ocurrió un error al guardar.', { id: 'saving-role' });
    } finally {
        handleCloseModals();
    }
  };

  const handleConfirmDelete = () => {
    if (!selectedRole?.id) return;
    deleteRoleMutation.mutate({ roleId: selectedRole.id }, {
      onSuccess: () => { toast.success(`Rol "${selectedRole.name}" eliminado.`); refetchRoles(); },
      onError: (error) => { toast.error((error as any).response?.data?.detail || 'Error al eliminar.'); },
      onSettled: () => handleCloseModals()
    });
  };

  const isMutating = createRoleMutation.isPending || updateRoleMutation.isPending || deleteRoleMutation.isPending;
  const roles: RoleResponse[] = rolesResponse || [];

  return (
    <div>
      <Toaster position="top-center" />
      <PageHeader title="Gestión de Roles" subtitle="Define los roles y sus permisos de acceso en el panel.">
        <Button onClick={handleOpenCreateModal} icon={<PlusIcon className="h-5 w-5" />} disabled={isMutating}>
          Crear Rol
        </Button>
      </PageHeader>
      
      {isLoadingRoles && <p className="text-center p-4">Cargando roles...</p>}

      {!isLoadingRoles && roles.length === 0 && <p className="text-center p-4">No se encontraron roles.</p>}

      {roles.length > 0 && (
        <div className="shadow-md overflow-hidden border border-gray-200 dark:border-gray-700 rounded-lg">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200 dark:divide-slate-700">
              <thead className="bg-gray-50 dark:bg-slate-900/70">
                {/* === CABECERA CON ESTILOS CORREGIDOS === */}
                <tr>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Nombre del Rol</th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Descripción</th>
                  <th scope="col" className="relative px-6 py-3">
                    <span className="sr-only">Acciones</span>
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white dark:bg-slate-800 divide-y divide-gray-200 dark:divide-slate-700">
                {roles.map((role) => (
                  <tr key={role.id} className="hover:bg-gray-50 dark:hover:bg-slate-700/50">
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900 dark:text-white">{role.name}</td>
                    <td className="px-6 py-4 text-sm text-gray-500 dark:text-gray-300">{role.description || <span className="italic opacity-70">Sin descripción</span>}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                      <div className="flex items-center justify-end space-x-2">
                        <IconButton icon={<PencilSquareIcon className="h-5 w-5"/>} onClick={() => handleOpenEditModal(role)} aria-label="Editar" disabled={isMutating}/>
                        <IconButton icon={<TrashIcon className="h-5 w-5"/>} onClick={() => handleOpenDeleteModal(role)} aria-label="Eliminar" disabled={isMutating || role.name === "SuperAdmin"} variant="danger"/>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <Modal isOpen={isModalOpen} onClose={handleCloseModals} title={isEditMode ? 'Editar Rol' : 'Crear Nuevo Rol'} size="2xl">
        <RoleForm
          role={selectedRole}
          onFormSubmit={handleFormSubmit}
          onCancel={handleCloseModals}
          isSubmitting={isMutating}
          isEditMode={isEditMode}
        />
      </Modal>

      {selectedRole && (
        <Modal
          isOpen={isDeleteModalOpen}
          onClose={handleCloseModals}
          title="Confirmar Eliminación"
          footerContent={
            <div className="flex justify-end space-x-3">
              <Button variant="secondary" onClick={handleCloseModals} disabled={deleteRoleMutation.isPending}>Cancelar</Button>
              <Button variant="danger" onClick={handleConfirmDelete} isLoading={deleteRoleMutation.isPending}>Eliminar</Button>
            </div>
          }
        >
          <p>¿Seguro que quieres eliminar el rol "<strong>{selectedRole.name}</strong>"?</p>
        </Modal>
      )}
    </div>
  );
};

export default AdminRolesPage;