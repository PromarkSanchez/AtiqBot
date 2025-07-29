// src/pages/AdminLlmModelsPage.tsx

import React, { useState } from 'react';
import {
  useReadAllLlmModelConfigsApiV1AdminLlmModelsGet as useReadAllModels,
  useCreateNewLlmModelConfigApiV1AdminLlmModelsPost as useCreateModel,
  useUpdateExistingLlmModelConfigApiV1AdminLlmModelsModelIdPut as useUpdateModel,
  useDeleteLlmModelConfigurationApiV1AdminLlmModelsModelIdDelete as useDeleteModel,
} from '../services/api/endpoints';
import type { LLMModelConfigResponse, LLMModelConfigCreate, LLMModelConfigUpdate } from '../services/api/schemas';
import toast, { Toaster } from 'react-hot-toast';

import Modal from '../components/shared/Modal';
import LlmModelForm from '../components/admin/llm-models/LlmModelForm';
import PageHeader from '../components/ui/PageHeader';
import { Button, IconButton } from '../components/shared/Button';
import { PlusIcon, PencilSquareIcon, TrashIcon } from '@heroicons/react/24/outline';

// ### [NUEVO] ### Función para formatear errores de la API de FastAPI
const formatApiError = (error: any): string => {
  if (error.response?.data?.detail) {
    const detail = error.response.data.detail;
    if (Array.isArray(detail)) {
      // Es un error de validación 422
      const firstError = detail[0];
      const field = firstError.loc?.join(' -> ') || 'Campo desconocido';
      return `Error en ${field}: ${firstError.msg}`;
    }
    // Es un error de HTTPException (string)
    return String(detail);
  }
  return 'Ocurrió un error inesperado.';
};

const AdminLlmModelsPage: React.FC = () => {
  // --- Estados ---
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isEditMode, setIsEditMode] = useState(false);
  const [selectedModel, setSelectedModel] = useState<LLMModelConfigResponse | null>(null);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);

  // --- Hooks de React Query (con alias para claridad) ---
  const { data: modelsResponse, isLoading, refetch: refetchModels } = useReadAllModels({ limit: 100 });
  const createModelMutation = useCreateModel();
  const updateModelMutation = useUpdateModel();
  const deleteModelMutation = useDeleteModel();
  
  // --- Handlers de Modales ---
  const handleOpenCreateModal = () => {
    setIsEditMode(false);
    setSelectedModel(null);
    setIsModalOpen(true);
  };

  const handleOpenEditModal = (model: LLMModelConfigResponse) => {
    setIsEditMode(true);
    setSelectedModel(model);
    setIsModalOpen(true);
  };

  const handleOpenDeleteModal = (model: LLMModelConfigResponse) => {
    setSelectedModel(model);
    setIsDeleteModalOpen(true);
  };

  const handleCloseModals = () => {
    if (isMutating) return;
    setIsModalOpen(false);
    setIsDeleteModalOpen(false);
    setSelectedModel(null);
  };

  // --- Handlers de Submit ---
  const handleFormSubmit = async (formData: LLMModelConfigCreate | LLMModelConfigUpdate) => {
    const promise = isEditMode
      ? updateModelMutation.mutateAsync({ modelId: selectedModel!.id, data: formData })
      : createModelMutation.mutateAsync({ data: formData as LLMModelConfigCreate });
      
    const actionText = isEditMode ? 'Actualizando' : 'Creando';

    toast.promise(
      promise,
      {
        loading: `${actionText} modelo...`,
        success: (result: LLMModelConfigResponse) => {
          refetchModels();
          handleCloseModals();
          return `Modelo "${result.display_name}" ${actionText.toLowerCase().slice(0, -1)}ado con éxito.`;
        },
        // ### [MEJORA] ### Usamos nuestra nueva función para mostrar errores legibles
        error: (error: any) => formatApiError(error),
      }
    );
  };

  const handleConfirmDelete = () => {
    if (!selectedModel?.id) return;
    toast.promise(
        deleteModelMutation.mutateAsync({ modelId: selectedModel.id }),
        {
            loading: 'Eliminando modelo...',
            success: () => {
                refetchModels();
                handleCloseModals();
                return `Modelo "${selectedModel.display_name}" eliminado.`;
            },
            error: (error: any) => formatApiError(error),
        }
    );
  };
  
  const isMutating = createModelMutation.isPending || updateModelMutation.isPending || deleteModelMutation.isPending;
  const models = modelsResponse || [];

  return (
    // ... el resto del JSX es idéntico ...
    <div>
      <Toaster position="top-center" />
      <PageHeader
        title="Configuración de Modelos LLM"
        subtitle="Gestiona los motores de inteligencia artificial disponibles en la plataforma."
      >
        <Button onClick={handleOpenCreateModal} icon={<PlusIcon className="h-5 w-5" />} disabled={isMutating}>
          Añadir Modelo
        </Button>
      </PageHeader>
      
      {isLoading && <p className="text-center p-4">Cargando modelos...</p>}

      {!isLoading && models.length === 0 && <p className="text-center p-4">No se han configurado modelos LLM.</p>}

      {models.length > 0 && (
        <div className="shadow-md overflow-hidden border border-gray-200 dark:border-gray-700 rounded-lg">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200 dark:divide-slate-700">
              <thead className="bg-gray-50 dark:bg-slate-900/70">
                <tr>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Nombre</th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Proveedor</th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">ID del Modelo (API)</th>
                  <th scope="col" className="px-6 py-3 text-center text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Estado</th>
                  <th scope="col" className="relative px-6 py-3"><span className="sr-only">Acciones</span></th>
                </tr>
              </thead>
              <tbody className="bg-white dark:bg-slate-800 divide-y divide-gray-200 dark:divide-slate-700">
                {models.map((model) => (
                  <tr key={model.id} className="hover:bg-gray-50 dark:hover:bg-slate-700/50">
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900 dark:text-white">{model.display_name}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">{model.provider}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400 font-mono">{model.model_identifier}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-center">
                        <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${ model.is_active ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200' : 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200' }`}>
                            {model.is_active ? 'Activo' : 'Inactivo'}
                        </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                      <div className="flex items-center justify-end space-x-2">
                        <IconButton icon={<PencilSquareIcon className="h-5 w-5"/>} onClick={() => handleOpenEditModal(model)} aria-label="Editar" disabled={isMutating}/>
                        <IconButton icon={<TrashIcon className="h-5 w-5"/>} onClick={() => handleOpenDeleteModal(model)} aria-label="Eliminar" disabled={isMutating} variant="danger"/>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
      <Modal isOpen={isModalOpen} onClose={handleCloseModals} title={isEditMode ? 'Editar Modelo LLM' : 'Añadir Nuevo Modelo LLM'} size="3xl">
        <LlmModelForm
          model={selectedModel}
          onFormSubmit={handleFormSubmit}
          onCancel={handleCloseModals}
          isSubmitting={isMutating}
        />
      </Modal>
      {selectedModel && (
        <Modal isOpen={isDeleteModalOpen} onClose={handleCloseModals} title="Confirmar Eliminación" footerContent={
            <div className="flex justify-end space-x-3">
              <Button variant="secondary" onClick={handleCloseModals} disabled={deleteModelMutation.isPending}>Cancelar</Button>
              <Button variant="danger" onClick={handleConfirmDelete} isLoading={deleteModelMutation.isPending}>Eliminar</Button>
            </div>
          }>
          <p>¿Estás seguro de que quieres eliminar el modelo "<strong>{selectedModel.display_name}</strong>"?</p>
          <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">Esta acción no se puede deshacer.</p>
        </Modal>
      )}
    </div>
  );
};

export default AdminLlmModelsPage;