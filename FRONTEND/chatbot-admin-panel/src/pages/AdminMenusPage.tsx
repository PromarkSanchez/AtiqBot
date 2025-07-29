// src/pages/AdminMenusPage.tsx
import React, { useState, useCallback } from 'react';
import toast, { Toaster } from 'react-hot-toast';
import type { AxiosError } from 'axios';

import {
  useGetAllMenuItemsApiV1AdminMenusGet,
  useCreateNewMenuItemApiV1AdminMenusPost,
  useUpdateMenuItemApiV1AdminMenusMenuIdPut,
  useDeleteMenuItemApiV1AdminMenusMenuIdDelete,
} from '../services/api/endpoints';
import type { AdminPanelMenuResponse, AdminPanelMenuCreate, AdminPanelMenuUpdate, HTTPValidationError } from '../services/api/schemas';

import PageHeader from '../components/ui/PageHeader';
import Modal from '../components/shared/Modal';
import { Button, IconButton } from '../components/shared/Button';
import { PencilSquareIcon, TrashIcon, PlusIcon } from '@heroicons/react/24/outline';
import MenuForm from '../components/admin/menus/MenuForm'; // Nuestro nuevo formulario

const AdminMenusPage: React.FC = () => {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isEditMode, setIsEditMode] = useState(false);
  const [selectedMenu, setSelectedMenu] = useState<AdminPanelMenuResponse | null>(null);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);

  // Hook para obtener todos los menús
  const {
    data: menusData,
    isLoading,
    isError,
    error,
    refetch,
  } = useGetAllMenuItemsApiV1AdminMenusGet({ limit: 1000 }, {
    query: { queryKey: ['allAdminMenus'], staleTime: 60000 }
  });
  const menus = menusData || [];

  // --- Lógica de Mutaciones y Manejo de Errores (similar a tu ApiClientPage) ---

  const handleMutationError = useCallback((err: unknown, defaultMessage: string) => {
    const axiosError = err as AxiosError<HTTPValidationError | { detail?: string }>;
    let message = defaultMessage;
    // ... tu lógica de manejo de errores ...
    toast.error(message, { duration: 5000 });
  }, []);

  const createMenuMutation = useCreateNewMenuItemApiV1AdminMenusPost({
    mutation: {
      onSuccess: () => {
        toast.success("Menú creado con éxito.");
        refetch();
        setIsModalOpen(false);
      },
      onError: (err) => handleMutationError(err, "Error al crear el menú."),
    }
  });

  const updateMenuMutation = useUpdateMenuItemApiV1AdminMenusMenuIdPut({
    mutation: {
      onSuccess: () => {
        toast.success("Menú actualizado con éxito.");
        refetch();
        setIsModalOpen(false);
      },
      onError: (err) => handleMutationError(err, "Error al actualizar el menú."),
    }
  });

  const deleteMenuMutation = useDeleteMenuItemApiV1AdminMenusMenuIdDelete({
    mutation: {
      onSuccess: () => {
        toast.success("Menú eliminado con éxito.");
        refetch();
        setIsDeleteModalOpen(false);
      },
      onError: (err) => handleMutationError(err, "Error al eliminar el menú. Asegúrate de que no tenga menús hijos."),
    }
  });
  
  // --- Handlers para Modales y Formularios ---

  const handleOpenCreateModal = () => {
    setIsEditMode(false);
    setSelectedMenu(null);
    setIsModalOpen(true);
  };

  const handleOpenEditModal = (menu: AdminPanelMenuResponse) => {
    setIsEditMode(true);
    setSelectedMenu(menu);
    setIsModalOpen(true);
  };
  
  const handleOpenDeleteModal = (menu: AdminPanelMenuResponse) => {
    setSelectedMenu(menu);
    setIsDeleteModalOpen(true);
  };

  const handleCloseModal = () => {
    setIsModalOpen(false);
  };
  
  const handleFormSubmit = (data: AdminPanelMenuCreate | AdminPanelMenuUpdate) => {
    if (isEditMode && selectedMenu) {
      updateMenuMutation.mutate({ menuId: selectedMenu.id, data: data as AdminPanelMenuUpdate });
    } else {
      createMenuMutation.mutate({ data: data as AdminPanelMenuCreate });
    }
  };

  const handleConfirmDelete = () => {
    if (selectedMenu) {
      deleteMenuMutation.mutate({ menuId: selectedMenu.id });
    }
  };

  const isSubmitting = createMenuMutation.isPending || updateMenuMutation.isPending;

  return (
    <div>
      <Toaster position="top-center" />
      <PageHeader title="Gestión de Menús del Panel" subtitle="Crea, edita y organiza los menús de navegación del panel." />

      <div className="flex justify-end mb-4">
        <Button onClick={handleOpenCreateModal} icon={<PlusIcon className="h-5 w-5" />}>
          Crear Nuevo Menú
        </Button>
      </div>
      
      <div className="mt-6 shadow-md overflow-hidden border border-gray-200 dark:border-gray-700 rounded-lg">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200 dark:divide-slate-700">
            <thead className="bg-gray-50 dark:bg-slate-900/70">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 dark:text-gray-300 uppercase tracking-wider">Nombre</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 dark:text-gray-300 uppercase tracking-wider">Ruta</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 dark:text-gray-300 uppercase tracking-wider">Orden</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 dark:text-gray-300 uppercase tracking-wider">Acciones</th>
              </tr>
            </thead>
            <tbody className="bg-white dark:bg-slate-800 divide-y divide-gray-200 dark:divide-slate-700">
              {isLoading && <tr><td colSpan={4} className="p-4 text-center">Cargando...</td></tr>}
              {isError && <tr><td colSpan={4} className="p-4 text-center text-red-500">Error: {error?.message}</td></tr>}
              {!isLoading && menus.map((menu) => (
                <tr key={menu.id} className="hover:bg-gray-50 dark:hover:bg-slate-700/50">
                  <td className="px-4 py-3 whitespace-nowrap text-sm font-medium text-gray-900 dark:text-white">
                    {menu.parent_id && <span className="mr-2 text-gray-400">└─</span>}
                    {menu.name}
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500 dark:text-gray-300 font-mono">{menu.frontend_route}</td>
                  <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500 dark:text-gray-300">{menu.display_order}</td>
                  <td className="px-4 py-3 whitespace-nowrap text-right text-sm">
                    <div className="flex items-center justify-end space-x-2">
                      <IconButton icon={<PencilSquareIcon className="h-5 w-5"/>} onClick={() => handleOpenEditModal(menu)} aria-label="Editar" />
                      <IconButton icon={<TrashIcon className="h-5 w-5"/>} onClick={() => handleOpenDeleteModal(menu)} aria-label="Eliminar" variant="danger"/>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      
      {/* Modal para Crear/Editar */}
      <Modal 
        isOpen={isModalOpen} 
        onClose={handleCloseModal} 
        title={isEditMode ? 'Editar Menú' : 'Crear Nuevo Menú'}
        size="2xl"
      >
        <MenuForm 
          onFormSubmit={handleFormSubmit}
          onCancel={handleCloseModal}
          isSubmitting={isSubmitting}
          isEditMode={isEditMode}
          menu={selectedMenu}
        />
      </Modal>

      {/* Modal de Confirmación de Borrado */}
      {selectedMenu && (
        <Modal 
          isOpen={isDeleteModalOpen} 
          onClose={() => setIsDeleteModalOpen(false)}
          title="Confirmar Eliminación"
          footerContent={
            <div className="flex justify-end space-x-3">
              <Button variant="secondary" onClick={() => setIsDeleteModalOpen(false)} disabled={deleteMenuMutation.isPending}>Cancelar</Button>
              <Button variant="danger" onClick={handleConfirmDelete} isLoading={deleteMenuMutation.isPending}>
                {deleteMenuMutation.isPending ? "Eliminando..." : "Eliminar"}
              </Button>
            </div>
          }
        >
          <p>¿Seguro que quieres eliminar el menú "<strong>{selectedMenu.name}</strong>"?</p>
          {menus.some(m => m.parent_id === selectedMenu.id) && (
            <p className="mt-2 text-sm text-yellow-600 dark:text-yellow-400">
              <strong>Atención:</strong> Este menú tiene sub-menús. Eliminarlos puede causar problemas si no se reasignan.
            </p>
          )}
        </Modal>
      )}
    </div>
  );
};

export default AdminMenusPage;