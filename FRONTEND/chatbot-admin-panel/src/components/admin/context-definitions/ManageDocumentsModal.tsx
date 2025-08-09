// src/components/admin/context-definitions/ManageDocumentsModal.tsx

import React from 'react';
import { useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';

// Hooks y tipos generados por Orval
import {
  useListManualUploadDocumentsApiV1AdminIngestionListDocumentsContextIdGet as useListDocuments,
  useDeleteIngestedDocumentApiV1AdminIngestionDeleteDocumentDelete as useDeleteDocument,
} from '../../../services/api/endpoints';
// Importamos DeleteDocumentRequest para el .mutate()
import type { DeleteDocumentRequest } from '../../../services/api/schemas'; 

// Componentes UI
import { Button, IconButton } from '../../shared/Button';
import { TrashIcon, ExclamationTriangleIcon } from '@heroicons/react/24/outline';

// --- Interfaz para la respuesta de la API de borrado ---
interface DeleteApiResponse {
  detail: string;
  chunks_deleted: number;
}

interface ManageDocumentsModalProps {
  contextId: number;
  contextName: string;
  onClose: () => void;
}

const ManageDocumentsModal: React.FC<ManageDocumentsModalProps> = ({ contextId, contextName, onClose }) => {
  const queryClient = useQueryClient();

  const { data: filenames = [], isLoading, isError, error } = useListDocuments(
    contextId,
    { query: { queryKey: ['contextDocuments', contextId] } }
  );

  // --- ¡CORRECCIÓN FINAL Y DEFINITIVA! ---
  const deleteMutation = useDeleteDocument({
    mutation: {
      // 1. Respetamos la firma: 'data' es implícitamente de tipo 'unknown'.
      onSuccess: (data) => {
        // 2. DENTRO de la función, hacemos un "type cast".
        // Le decimos a TypeScript que trate 'data' como nuestro tipo `DeleteApiResponse`.
        const response = data as DeleteApiResponse;

        // 3. Ahora podemos acceder a 'response.detail' sin errores.
        toast.success(response.detail || 'Documento eliminado.');
        queryClient.invalidateQueries({ queryKey: ['contextDocuments', contextId] });
      },
      onError: (err: any) => {
        const message = err.response?.data?.detail || "Error al eliminar el documento.";
        toast.error(message);
      },
    }
  });

  const handleDeleteClick = (filename: string) => {
    if (window.confirm(`¿Estás seguro de que quieres eliminar "${filename}"? Esta acción es permanente.`)) {
      const payload: DeleteDocumentRequest = {
        context_id: contextId,
        filename: filename
      };
      deleteMutation.mutate({ data: payload });
    }
  };

  return (
    <div className="space-y-4">
      <p className="text-sm text-gray-600 dark:text-gray-300">
        Gestionando documentos subidos para: <strong className="font-semibold text-indigo-600 dark:text-indigo-400">{contextName}</strong>
      </p>

      {isLoading && <p className="animate-pulse text-gray-500">Cargando lista de documentos...</p>}
      {isError && <p className="text-red-500">Error al cargar: { (error as any).message }</p>}
      
      {!isLoading && !isError && (
        filenames.length > 0 ? (
          <div className="max-h-96 overflow-y-auto border border-gray-200 dark:border-slate-700 rounded-md">
            <ul className="divide-y divide-gray-200 dark:divide-slate-700">
              {filenames.map((name) => (
                <li key={name} className="flex items-center justify-between p-3 hover:bg-gray-50 dark:hover:bg-slate-700/50">
                  <span className="text-sm font-mono text-gray-800 dark:text-gray-200 truncate pr-4">{name}</span>
                  <IconButton
                    title="Eliminar este documento"
                    onClick={() => handleDeleteClick(name)}
                    // Lógica para deshabilitar solo el botón que se está borrando
                    disabled={deleteMutation.isPending && deleteMutation.variables?.data?.filename === name}
                    icon={<TrashIcon className="h-5 w-5" />}
                    variant="ghost"
                    className="text-red-600 hover:text-red-800"
                    aria-label={`Eliminar ${name}`}
                  />
                </li>
              ))}
            </ul>
          </div>
        ) : (
          <div className="text-center p-6 bg-gray-50 dark:bg-slate-700/30 rounded-md">
            <ExclamationTriangleIcon className="h-10 w-10 mx-auto text-gray-400" />
            <p className="mt-2 text-sm text-gray-600 dark:text-gray-300">No hay documentos subidos manualmente en este contexto.</p>
          </div>
        )
      )}
      <div className="pt-4 flex justify-end">
        <Button variant="secondary" onClick={onClose}>Cerrar</Button>
      </div>
    </div>
  );
};

export default ManageDocumentsModal;