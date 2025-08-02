// src/pages/AdminVirtualAgentsPage.tsx

import React, { useState } from 'react';
import {
  useCreateNewVirtualAgentProfileApiV1AdminVirtualAgentProfilesPost as useCreateAgent,
  useReadAllVirtualAgentProfilesApiV1AdminVirtualAgentProfilesGet as useReadAllAgents,
  useUpdateExistingVirtualAgentProfileApiV1AdminVirtualAgentProfilesProfileIdPut as useUpdateAgent,
  useDeleteVirtualAgentProfileEntryApiV1AdminVirtualAgentProfilesProfileIdDelete as useDeleteAgent,
} from '../services/api/endpoints';
import type { VirtualAgentProfileResponse, VirtualAgentProfileCreate, VirtualAgentProfileUpdate } from '../services/api/schemas';
import toast, { Toaster } from 'react-hot-toast';

import Modal from '../components/shared/Modal';
import VirtualAgentForm from '../components/admin/virtual-agents/VirtualAgentForm'; // El formulario que creamos
import PageHeader from '../components/ui/PageHeader';
import { Button, IconButton } from '../components/shared/Button';
import { PlusIcon, PencilSquareIcon, TrashIcon } from '@heroicons/react/24/outline';

const AdminVirtualAgentsPage: React.FC = () => {
  // --- Estados ---
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isEditMode, setIsEditMode] = useState(false);
  const [selectedAgent, setSelectedAgent] = useState<VirtualAgentProfileResponse | null>(null);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);

  // --- Hooks de React Query ---
  const { data: agentsResponse, isLoading, refetch: refetchAgents } = useReadAllAgents({ limit: 100 });
  const createAgentMutation = useCreateAgent();
  const updateAgentMutation = useUpdateAgent();
  const deleteAgentMutation = useDeleteAgent();
  
  // --- Handlers de Modales ---
  const handleOpenCreateModal = () => {
    setIsEditMode(false);
    setSelectedAgent(null);
    setIsModalOpen(true);
  };

  const handleOpenEditModal = (agent: VirtualAgentProfileResponse) => {
    setIsEditMode(true);
    setSelectedAgent(agent);
    setIsModalOpen(true);
  };

  const handleOpenDeleteModal = (agent: VirtualAgentProfileResponse) => {
    setSelectedAgent(agent);
    setIsDeleteModalOpen(true);
  };

  const handleCloseModals = () => {
    if (isMutating) return;
    setIsModalOpen(false);
    setIsDeleteModalOpen(false);
    setSelectedAgent(null);
  };

  // --- Handlers de Submit ---
  const handleFormSubmit = async (formData: VirtualAgentProfileCreate | VirtualAgentProfileUpdate) => {
    if (!isEditMode) {
      toast.promise(
        createAgentMutation.mutateAsync({ data: formData as VirtualAgentProfileCreate }),
        {
          loading: 'Creando agente...',
          success: (newAgent) => {
            refetchAgents();
            handleCloseModals();
            return `Agente "${newAgent.name}" creado.`;
          },
          error: (err: any) => err.response?.data?.detail || 'Error al crear.',
        }
      );
    } else {
      if (!selectedAgent?.id) return;
      toast.promise(
        updateAgentMutation.mutateAsync({ profileId: selectedAgent.id, data: formData }),
        {
          loading: 'Actualizando agente...',
          success: (updatedAgent) => {
            refetchAgents();
            handleCloseModals();
            return `Agente "${updatedAgent.name}" actualizado.`;
          },
          error: (err: any) => err.response?.data?.detail || 'Error al actualizar.',
        }
      );
    }
  };

  const handleConfirmDelete = () => {
    if (!selectedAgent?.id) return;
    toast.promise(
      deleteAgentMutation.mutateAsync({ profileId: selectedAgent.id }),
      {
        loading: 'Eliminando agente...',
        success: () => {
          refetchAgents();
          handleCloseModals();
          return `Agente "${selectedAgent.name}" eliminado.`;
        },
        error: (err: any) => err.response?.data?.detail || 'Error al eliminar.',
      }
    );
  };
  
  const isMutating = createAgentMutation.isPending || updateAgentMutation.isPending || deleteAgentMutation.isPending;
  const agents = agentsResponse || [];

  return (
    <div>
      <Toaster position="top-center" />
      <PageHeader
        title="Agentes Virtuales"
        subtitle="Define las personalidades, instrucciones y capacidades de tus chatbots."
      >
        <Button onClick={handleOpenCreateModal} icon={<PlusIcon className="h-5 w-5" />} disabled={isMutating}>
          Crear Agente
        </Button>
      </PageHeader>
      
      {isLoading && <p className="text-center p-4">Cargando agentes...</p>}

      {!isLoading && agents.length === 0 && <p className="text-center p-4">No se han creado agentes virtuales.</p>}

      {agents.length > 0 && (
        <div className="shadow-md overflow-hidden border border-gray-200 dark:border-gray-700 rounded-lg">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200 dark:divide-slate-700">
              <thead className="bg-gray-50 dark:bg-slate-900/70">
                <tr>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Nombre del Agente</th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Modelo LLM Asociado</th>
                  <th scope="col" className="px-6 py-3 text-center text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Estado</th>
                  <th scope="col" className="relative px-6 py-3"><span className="sr-only">Acciones</span></th>
                </tr>
              </thead>
              <tbody className="bg-white dark:bg-slate-800 divide-y divide-gray-200 dark:divide-slate-700">
                {agents.map((agent) => (
                  <tr key={agent.id} className="hover:bg-gray-50 dark:hover:bg-slate-700/50">
                    <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm font-medium text-gray-900 dark:text-white">{agent.name}</div>
                        <div className="text-xs text-gray-500 dark:text-gray-400">{agent.description}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                      {agent.llm_model_config?.display_name || 'No especificado'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-center">
                        <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${
                            agent.is_active 
                                ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200' 
                                : 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
                        }`}>
                            {agent.is_active ? 'Activo' : 'Inactivo'}
                        </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                      <div className="flex items-center justify-end space-x-2">
                        <IconButton icon={<PencilSquareIcon className="h-5 w-5" />} onClick={() => handleOpenEditModal(agent)} disabled={isMutating} aria-label={''}/>
                        <IconButton icon={<TrashIcon className="h-5 w-5" />} onClick={() => handleOpenDeleteModal(agent)} disabled={isMutating} variant="danger" aria-label={''}/>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Modal para Crear y Editar Agente */}
      <Modal isOpen={isModalOpen} onClose={handleCloseModals} title={isEditMode ? 'Editar Agente Virtual' : 'Crear Nuevo Agente Virtual'} size="4xl">
        <VirtualAgentForm
          agent={selectedAgent}
          onFormSubmit={handleFormSubmit}
          onCancel={handleCloseModals}
          isSubmitting={isMutating}
        />
      </Modal>

      {/* Modal para Confirmar Eliminación */}
      {selectedAgent && (
        <Modal
          isOpen={isDeleteModalOpen}
          onClose={handleCloseModals}
          title="Confirmar Eliminación"
          footerContent={
            <div className="flex justify-end space-x-3">
              <Button variant="secondary" onClick={handleCloseModals} disabled={deleteAgentMutation.isPending}>Cancelar</Button>
              <Button variant="danger" onClick={handleConfirmDelete} isLoading={deleteAgentMutation.isPending}>Eliminar</Button>
            </div>
          }
        >
          <p>¿Estás seguro de que quieres eliminar el agente "<strong>{selectedAgent.name}</strong>"?</p>
        </Modal>
      )}
    </div>
  );
};

export default AdminVirtualAgentsPage;