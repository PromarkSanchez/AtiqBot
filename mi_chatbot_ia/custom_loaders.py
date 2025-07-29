# Contenido COMPLETO para tu archivo custom_loaders.py

from langchain_community.document_loaders.base import BaseLoader
from langchain_core.documents import Document as LangchainCoreDocument
from typing import Iterator, Dict, Any, Optional, List

class BatchedLineTextLoader(BaseLoader):
    """
    Un cargador personalizado que lee un archivo de texto, agrupa N líneas
    en un solo 'Document' de LangChain y luego lo produce.
    Optimiza la ingesta masiva de logs.
    """
    def __init__(self, file_path: str, batch_size: int = 10, encoding: str = "utf-8", metadata_template: Optional[Dict[str, Any]] = None):
        """
        Args:
            file_path: La ruta al archivo de texto.
            batch_size: Número de líneas a agrupar en cada documento.
            encoding: Codificación del archivo.
            metadata_template: Metadatos base.
        """
        self.file_path = file_path
        self.batch_size = batch_size
        self.encoding = encoding
        self.metadata_template = metadata_template or {}

    def lazy_load(self) -> Iterator[LangchainCoreDocument]:
        """Carga perezosa del archivo en lotes de líneas."""
        batch_lines: List[str] = []
        start_line_number = 1
        
        try:
            with open(self.file_path, "r", encoding=self.encoding) as f:
                for current_line_number, line in enumerate(f, 1):
                    line_content = line.strip()
                    if line_content:
                        batch_lines.append(line_content)
                    
                    if len(batch_lines) >= self.batch_size:
                        final_metadata = self.metadata_template.copy()
                        final_metadata['source_start_line'] = start_line_number
                        final_metadata['source_end_line'] = current_line_number
                        final_metadata.setdefault('source', self.file_path)

                        yield LangchainCoreDocument(
                            page_content="\n".join(batch_lines),
                            metadata=final_metadata
                        )
                        batch_lines = []
                        start_line_number = current_line_number + 1

            # Producir el último lote si queda algo
            if batch_lines:
                final_metadata = self.metadata_template.copy()
                final_metadata['source_start_line'] = start_line_number
                final_metadata['source_end_line'] = "EOF"
                final_metadata.setdefault('source', self.file_path)
                yield LangchainCoreDocument(
                    page_content="\n".join(batch_lines),
                    metadata=final_metadata
                )

        except Exception as e:
            print(f"ERROR en BatchedLineTextLoader procesando '{self.file_path}': {e}")
            return