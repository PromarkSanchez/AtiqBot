// src/pages/AdminContextDefinitionsPage.tsx
import React, { useState } from 'react'; // Añadido useEffect si lo usas
import {
  useReadAllContextDefinitionsEndpointApiV1AdminContextDefinitionsGet,
  useCreateNewContextDefinitionEndpointApiV1AdminContextDefinitionsPost,
  useUpdateExistingContextDefinitionEndpointApiV1AdminContextDefinitionsContextIdPut,
  useDeleteContextDefinitionEndpointApiV1AdminContextDefinitionsContextIdDelete,
  // Si tuvieras el hook para leer un solo contexto para edición (mejor que usar el de la lista):
  // useReadContextDefinitionByIdEndpointApiV1AdminContextDefinitionsContextIdGet,
} from '../services/api/endpoints'; // Asume que endpoints.ts está ahí
import type {
  ContextDefinitionResponse, // Este es el tipo de la API
  ContextDefinitionCreate,
  ContextDefinitionUpdate,
  HTTPValidationError,
} from '../services/api/schemas';
import type { AxiosError } from 'axios';
import Modal from '../components/shared/Modal'; // Tu componente Modal
import ContextDefinitionForm from '../components/admin/context-definitions/ContextDefinitionForm'; // Tu formulario
import toast, { Toaster } from 'react-hot-toast';
// Importa iconos si los usas aquí (ej. para un botón de loading global en la página)

const AdminContextDefinitionsPage: React.FC = () => {
  const [isFormModalOpen, setIsFormModalOpen] = useState(false);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  // `contextToEdit` almacenará el objeto completo ContextDefinitionResponse de la API
  const [contextToEdit, setContextToEdit] = useState<ContextDefinitionResponse | null>(null);
  const [contextToDelete, setContextToDelete] = useState<ContextDefinitionResponse | null>(null);

  // Para la paginación de la lista (puedes hacerlo más avanzado después)
  const [currentPage] = useState(0); // skip
  const [pageSize] = useState(100); // limit

  const listContextsQuery = useReadAllContextDefinitionsEndpointApiV1AdminContextDefinitionsGet(
    { skip: currentPage * pageSize, limit: pageSize }, 
    { query: { 
        queryKey: ['adminContextDefinitionsList', currentPage, pageSize], 
        staleTime: 5 * 60 * 1000, // 5 minutos
        // refetchOnWindowFocus: false, // Opcional: deshabilitar refetch al enfocar ventana
      } 
    }
  );
  const queryParams = { skip: 0, limit: 100 }; // Ajusta según necesites
  const {
    isLoading: isLoadingContexts,
  } = useReadAllContextDefinitionsEndpointApiV1AdminContextDefinitionsGet(queryParams, {
    query: { queryKey: ['adminContextDefinitionsList', queryParams], staleTime: 1000 * 60 }, // 1 min stale time
  });

  const deepCopy = <T,>(obj: T): T => {
  if (obj === null || typeof obj !== 'object') {
    return obj;
  }
  // Manejar fechas correctamente
  if (obj instanceof Date) {
    return new Date(obj.getTime()) as any;
  }
  // Manejar arrays
  if (Array.isArray(obj)) {
    return obj.map(item => deepCopy(item)) as any;
  }
  // Manejar objetos
  const copiedObject = {} as { [P in keyof T]: T[P] };
  for (const key in obj) {
    if (Object.prototype.hasOwnProperty.call(obj, key)) {
      copiedObject[key] = deepCopy(obj[key]);
    }
  }
  return copiedObject;
};
  // Nota: Si el GET para un solo contexto para edición fuera lento,
  // podrías usar `useReadContextDefinitionByIdEndpointApiV1AdminContextDefinitionsContextIdGet`
  // en lugar de depender solo de los datos de la lista. Por ahora, `contextToEdit` tomará el objeto de la lista.

  const createMutation = useCreateNewContextDefinitionEndpointApiV1AdminContextDefinitionsPost({
    mutation: {
      onSuccess: (newContext) => {
        toast.success(`Definición "${newContext.name}" creada!`);
        listContextsQuery.refetch(); // Re-obtener la lista
        handleCloseFormModal();
      },
      onError: (error) => {
        const axiosError = error as AxiosError<HTTPValidationError | { detail?: string }>;
        const message = axiosError.response?.data?.detail || (axiosError.response?.data as any)?.error?.message || axiosError.message || "Error al crear.";
        toast.error(typeof message === 'string' ? message : JSON.stringify(message), { duration: 7000 });
      },
    },
  });

  const updateMutation = useUpdateExistingContextDefinitionEndpointApiV1AdminContextDefinitionsContextIdPut({
    mutation: {
      onSuccess: (updatedContext) => {
        toast.success(`Definición "${updatedContext.name}" actualizada!`);
        listContextsQuery.refetch();
        handleCloseFormModal();
      },
      onError: (error) => {
        const axiosError = error as AxiosError<HTTPValidationError | { detail?: string }>;
        const message = axiosError.response?.data?.detail || (axiosError.response?.data as any)?.error?.message || axiosError.message || "Error al actualizar.";
        toast.error(typeof message === 'string' ? message : JSON.stringify(message), { duration: 7000 });
      },
    },
  });

  const deleteMutation = useDeleteContextDefinitionEndpointApiV1AdminContextDefinitionsContextIdDelete({
    mutation: {
      onSuccess: () => {
        toast.success(`Definición "${contextToDelete?.name}" eliminada.`);
        listContextsQuery.refetch();
        handleCloseDeleteModal();
      },
      onError: (error) => {
        const axiosError = error as AxiosError<HTTPValidationError | { detail?: string }>;
        const message = axiosError.response?.data?.detail || (axiosError.response?.data as any)?.error?.message || axiosError.message || "Error al eliminar.";
        toast.error(typeof message === 'string' ? message : JSON.stringify(message), { duration: 7000 });
        handleCloseDeleteModal(); // Cerrar igual en error para evitar que quede abierto
      },
    }
  });

  const handleOpenCreateModal = () => {
    setContextToEdit(null); // Limpiar para modo creación
    setIsFormModalOpen(true);
  };

  const handleOpenEditModal = (contextDef: ContextDefinitionResponse) => {
    console.log("ADMIN_PAGE: Abriendo modal para editar:", contextDef); // <-- DEBUGGING
    // Aquí, contextDef es el objeto ContextDefinitionResponse tal como vino de la API
    // y se listó en la tabla. Este objeto YA TIENE los campos procesados
    // como `processing_config_database_query` con `column_access_rules` transformado.
    setContextToEdit(deepCopy(contextDef)); // Usar deepCopy para evitar mutaciones accidentales
    setIsFormModalOpen(true);
  };

  
  const handleCloseFormModal = () => {
    setIsFormModalOpen(false);
    setContextToEdit(null);
  };

  const handleOpenDeleteModal = (contextDef: ContextDefinitionResponse) => {
    setContextToDelete(contextDef);
    setIsDeleteModalOpen(true);
  };

  const handleCloseDeleteModal = () => {
    setIsDeleteModalOpen(false);
    setContextToDelete(null);
  };
  
  const handleConfirmDelete = async () => {
    if (contextToDelete && contextToDelete.id) {
      try {
        await deleteMutation.mutateAsync({ contextId: contextToDelete.id });
      } catch (e) { /* El onError del hook ya maneja el toast */ }
    }
  };

  const handleFormSubmit = async (formData: ContextDefinitionCreate | ContextDefinitionUpdate) => {
    console.log("ADMIN_PAGE: Formulario enviado. ¿Es edición?", !!contextToEdit, "Datos:", formData);
    try {
        if (contextToEdit && contextToEdit.id) { // Modo Edición
          const updateData = formData as ContextDefinitionUpdate; // Ya debería tener el formato correcto
          await updateMutation.mutateAsync({ contextId: contextToEdit.id, data: updateData });
        } else { // Modo Creación
          const createData = formData as ContextDefinitionCreate;
          await createMutation.mutateAsync({ data: createData });
        }
    } catch (e) { /* El onError de los hooks ya maneja el toast */ }
  };

  if (listContextsQuery.isLoading) {
    return <div className="p-6 text-center text-lg animate-pulse">Cargando definiciones...</div>;
  }

  if (listContextsQuery.isError) {
    const axiosError = listContextsQuery.error as AxiosError<HTTPValidationError | { detail?: string }>;
    const message = axiosError.response?.data?.detail || axiosError.message || "Error cargando lista.";
    return <div className="p-6 text-red-600 text-center">Error: {typeof message === 'string' ? message : JSON.stringify(message)}</div>;
  }

  const contextDefinitions = listContextsQuery.data || [];

  return (
    <div className="container mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <Toaster position="top-right" />
          <div className="flex justify-between items-center mb-6">
            <h1 className="text-3xl font-bold text-gray-800 dark:text-white">
              Definiciones de Contexto
            </h1>
            <button
              onClick={handleOpenCreateModal}
              disabled={createMutation.isPending || updateMutation.isPending}
              className="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 disabled:opacity-70"
            >
              Crear Nueva
            </button>
          </div>

      {/* Tu tabla para mostrar contextDefinitions. Asegúrate que los datos que muestras sean los correctos,
          por ejemplo, contextDef.db_connection_config?.name para mostrar el nombre de la conexión de BD.
          La he simplificado aquí. */}
      {contextDefinitions.length > 0 ? (
        <div className="shadow-lg overflow-hidden border border-gray-200 dark:border-gray-700 rounded-lg">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
              <thead className="bg-gray-50 dark:bg-slate-800">
                <tr>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Nombre</th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Tipo</th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Activo</th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Visibilidad</th> {/* <--- AÑADE ESTO */}
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider max-w-xs truncate">Fuentes Doc.</th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider max-w-xs truncate">Conex. BD</th>
                  <th scope="col" className="px-6 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Acciones</th>
                </tr>
              </thead>
              <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                {contextDefinitions.map((contextDef) => (
                  <tr key={contextDef.id} className={`${!contextDef.is_active ? 'opacity-60 bg-gray-100 dark:bg-slate-900' : ''} hover:bg-gray-50 dark:hover:bg-slate-700 transition-colors duration-150`}>
                    <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm font-medium text-gray-900 dark:text-white">{contextDef.name}</div>
                        <div className="text-xs text-gray-500 dark:text-gray-400 max-w-xs truncate" title={contextDef.description || ''}>{contextDef.description || '-'}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-700 dark:text-gray-300">{contextDef.main_type}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm">
                      <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${contextDef.is_active ? 'bg-green-100 text-green-800 dark:bg-green-700 dark:text-green-100' : 'bg-red-100 text-red-800 dark:bg-red-700 dark:text-red-100'}`}>
                        {contextDef.is_active ? 'Sí' : 'No'}
                      </span>
                    </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm">
                        <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${contextDef.is_public ? 'bg-blue-100 text-blue-800 dark:bg-blue-700 dark:text-blue-100' : 'bg-yellow-100 text-yellow-800 dark:bg-yellow-700 dark:text-yellow-100'}`}>
                          {contextDef.is_public ? 'Público' : 'Privado'}
                        </span>
                      </td>                    
                      
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-700 dark:text-gray-300 max-w-xs truncate" title={contextDef.document_sources?.map(ds => ds.name).join(', ') || ''}>
                      {contextDef.document_sources && contextDef.document_sources.length > 0 ? contextDef.document_sources.map(ds => ds.name).join(', ') : 'N/A'}
                    </td>
                    
                     <td>
                      
                     </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                      <button
                        onClick={() => handleOpenEditModal(contextDef)}
                        disabled={createMutation.isPending || updateMutation.isPending || deleteMutation.isPending}
                        className="text-indigo-600 hover:text-indigo-800 dark:text-indigo-400 dark:hover:text-indigo-300 mr-3 disabled:opacity-50"
                      >
                        Editar
                      </button>
                      <button
                        onClick={() => handleOpenDeleteModal(contextDef)}
                        disabled={createMutation.isPending || updateMutation.isPending || deleteMutation.isPending || !contextDef.is_active} // Ejemplo: No permitir borrar si está inactivo o hay otra op. en curso
                        className="text-red-600 hover:text-red-800 dark:text-red-400 dark:hover:text-red-300 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        Eliminar
                      </button>
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
            {isLoadingContexts ? 'Cargando...' : 'No se encontraron definiciones de contexto.'}
          </p>
        </div>
      )}

      {isFormModalOpen && (
        <Modal
          isOpen={isFormModalOpen}
          onClose={handleCloseFormModal}
          title={contextToEdit ? `Editar: ${contextToEdit.name}` : 'Crear Nueva Definición de Contexto'}
          size="4xl" // Puede que necesites un modal grande para este formulario
        >
          <ContextDefinitionForm
            initialData={contextToEdit} // Pasa el contexto completo para edición (o null para creación)
            onSubmit={handleFormSubmit}
            onCancel={handleCloseFormModal}
            isSubmittingGlobal={createMutation.isPending || updateMutation.isPending}
            isEditMode={!!contextToEdit} // Determina el modo basado en si hay contextToEdit
          />
        </Modal>
      )}

      {isDeleteModalOpen && contextToDelete && ( // Asegurarse de que selectedContext exista para el modal
         <Modal
            isOpen={isDeleteModalOpen}
            onClose={handleCloseDeleteModal}
            title="Confirmar Eliminación"
            footerContent={
            <>
                <button
                type="button"
                onClick={handleCloseDeleteModal}
                disabled={deleteMutation.isPending}
                className="mr-2 px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-slate-700 border border-gray-300 dark:border-slate-600 rounded-md hover:bg-gray-50 dark:hover:bg-slate-600 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-70"
                >
                Cancelar
                </button>
                <button
                onClick={handleConfirmDelete}
                disabled={deleteMutation.isPending}
                className="px-4 py-2 text-sm font-medium text-white bg-red-600 hover:bg-red-700 border border-transparent rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 disabled:opacity-70 disabled:cursor-not-allowed"
                >
                {deleteMutation.isPending ? 'Eliminando...' : 'Sí, Eliminar'}
                </button>
            </>
            }
        >
            <p className="text-sm text-gray-700 dark:text-gray-300">
            ¿Estás seguro de que quieres eliminar la definición de contexto
            <strong className="font-semibold px-1">{contextToDelete?.name}</strong>?
            Esta acción no se puede deshacer.
            </p>
        </Modal>
      )}
    </div>
  );
};

export default AdminContextDefinitionsPage;