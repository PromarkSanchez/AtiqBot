// src/components/admin/context-definitions/DocumentUploaderForm.tsx
import React, { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { useUploadAndIngestDocumentsApiV1AdminIngestionUploadDocumentsPost as useUploadDocuments } from '../../../services/api/endpoints';
import { Button } from '../../shared/Button';
import { DocumentArrowUpIcon, XCircleIcon } from '@heroicons/react/24/outline';
import toast from 'react-hot-toast';

interface DocumentUploaderFormProps {
  contextId: number;
  contextName: string;
  onUploadSuccess: () => void;
  onCancel: () => void; // <--- AÑADE ESTA LÍNEA

}

const MAX_FILES = 5;
const ALLOWED_MIME_TYPES = {
  'application/pdf': ['.pdf'],
  'application/msword': ['.doc'],
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
  'text/plain': ['.txt'],
  'text/markdown': ['.md'],
  'application/vnd.ms-excel': ['.xls'],
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
};

const DocumentUploaderForm: React.FC<DocumentUploaderFormProps> = ({ contextId, contextName, onUploadSuccess }) => {
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const uploadMutation = useUploadDocuments({
    mutation: {
      onSuccess: (data) => {
        toast.success(typeof data.detail === 'string' ? data.detail : 'Archivos procesados exitosamente.');
        onUploadSuccess();
      },
      onError: (error: any) => {
        const detail = error.response?.data?.detail || 'Ocurrió un error inesperado durante la carga.';
        toast.error(`Error: ${detail}`, { duration: 6000 });
      },
    },
  });

  const onDrop = useCallback((acceptedFiles: File[], fileRejections: any[]) => {
    setErrorMessage(null);

    if (fileRejections.length > 0) {
      setErrorMessage(`Archivo no válido. Tipos aceptados: PDF, DOCX, TXT, XLSX.`);
      return;
    }

    if (acceptedFiles.length + selectedFiles.length > MAX_FILES) {
      setErrorMessage(`No puedes tener más de ${MAX_FILES} archivos en total.`);
      return;
    }

    // Prevenir duplicados
    const newUniqueFiles = acceptedFiles.filter(
      newFile => !selectedFiles.some(existingFile => existingFile.name === newFile.name && existingFile.size === newFile.size)
    );

    setSelectedFiles(prev => [...prev, ...newUniqueFiles]);
  }, [selectedFiles]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    maxFiles: MAX_FILES,
    accept: ALLOWED_MIME_TYPES,
  });

  const handleRemoveFile = (fileNameToRemove: string) => {
    setSelectedFiles(prev => prev.filter(f => f.name !== fileNameToRemove));
  };

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (selectedFiles.length === 0) {
      setErrorMessage('Por favor, selecciona al menos un archivo para subir.');
      return;
    }
    uploadMutation.mutate({ data: { files: selectedFiles, context_id: contextId } });
  };
  
  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <p className="text-sm text-gray-600 dark:text-gray-300">
        Añadir documentos a: <strong className="font-semibold text-indigo-600 dark:text-indigo-400">{contextName}</strong>
      </p>

      <div {...getRootProps()} className={`mt-2 flex justify-center rounded-lg border border-dashed px-6 py-10
        ${isDragActive ? 'border-indigo-500 bg-indigo-50 dark:bg-slate-700/50' : 'border-gray-900/25 dark:border-gray-400/25'}
        cursor-pointer transition-colors`}>
        <input {...getInputProps()} />
        <div className="text-center">
          <DocumentArrowUpIcon className="mx-auto h-12 w-12 text-gray-300 dark:text-gray-500" aria-hidden="true" />
          <p className="mt-4 text-sm text-gray-600 dark:text-gray-400">
            {isDragActive ? '¡Suelta los archivos aquí!' : 'Arrastra y suelta o haz clic para seleccionar'}
          </p>
          <p className="text-xs leading-5 text-gray-600 dark:text-gray-400">PDF, DOCX, TXT, XLSX. Máximo 5 archivos.</p>
        </div>
      </div>
      
      {errorMessage && <p className="text-sm text-red-600 dark:text-red-400">{errorMessage}</p>}

      {selectedFiles.length > 0 && (
        <div className="space-y-2">
          <ul className="divide-y divide-gray-200 dark:divide-slate-700 border border-gray-200 dark:border-slate-700 rounded-md max-h-48 overflow-y-auto">
            {selectedFiles.map(file => (
              <li key={file.name + file.size} className="flex items-center justify-between p-2 hover:bg-gray-50 dark:hover:bg-slate-700/50">
                <div className='truncate pr-2'>
                    <p className="text-sm font-medium text-gray-800 dark:text-gray-200 truncate">{file.name}</p>
                    <p className="text-xs text-gray-500 dark:text-gray-400">{Math.round(file.size / 1024)} KB</p>
                </div>
                <button type="button" onClick={() => handleRemoveFile(file.name)} title="Quitar archivo">
                  <XCircleIcon className="h-5 w-5 text-red-500 hover:text-red-700"/>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="pt-4 flex justify-end gap-x-3">
        <Button type="button" variant='secondary' onClick={onUploadSuccess}>Cancelar</Button>
        <Button type="submit" isLoading={uploadMutation.isPending} disabled={selectedFiles.length === 0}>
            {uploadMutation.isPending ? 'Procesando...' : `Cargar ${selectedFiles.length} Archivo(s)`}
        </Button>
      </div>
    </form>
  );
};
export default DocumentUploaderForm;