# app/models/document.py
from sqlalchemy import Column, String, Integer, ForeignKey, Text, DateTime # type: ignore
from sqlalchemy.orm import relationship # type: ignore
from sqlalchemy.sql import func # type: ignore # Para timestamps automáticos

# Importar el tipo VECTOR de la librería pgvector
from pgvector.sqlalchemy import VECTOR # type: ignore # <--- ¡IMPORTANTE!

from app.db.session import Base_Vector # NUEVO

class Document(Base_Vector): # <--- CAMBIO AQUÍ

    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False, index=True) # Nombre del archivo o identificador
    source_type = Column(String(50), nullable=True) # Ej: "file_upload", "web_scrape", "db_table_description"
    description = Column(Text, nullable=True) # Descripción opcional del documento
    
    # Metadatos adicionales que podrían ser útiles
    metadata_ = Column(Text, name="metadata", nullable=True) # Usamos 'metadata_' porque 'metadata' es un atributo de SQLAlchemy Base. Lo mapeamos a 'metadata' en la BD.
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relación: Un Documento puede tener muchos DocumentChunks
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Document(id={self.id}, name='{self.name}')>"


class DocumentChunk(Base_Vector):
    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False) # Clave foránea
    
    content = Column(Text, nullable=False) # El trozo de texto en sí
    
    # La columna vectorial para el embedding.
    # Debes especificar la dimensionalidad del vector.
    # Por ejemplo, si usas 'all-MiniLM-L6-v2' de sentence-transformers, la dimensión es 384.
    # Si usas modelos de OpenAI como 'text-embedding-ada-002', la dimensión es 1536.
    # Ajusta DIMENSION según el modelo de embedding que vayas a usar.
    embedding_dimension = 384 # Ejemplo, ajusta esto
    embedding = Column(VECTOR(embedding_dimension), nullable=True) # Permitimos nulo por si la ingesta falla o para futuro
    
    chunk_order = Column(Integer, nullable=True) # Para saber el orden del chunk dentro del documento original
    metadata_ = Column(Text, name="metadata", nullable=True) # Metadatos específicos del chunk (ej. número de página)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relación: Un DocumentChunk pertenece a un Document
    document = relationship("Document", back_populates="chunks")

    def __repr__(self):
        return f"<DocumentChunk(id={self.id}, document_id={self.document_id}, order={self.chunk_order})>"

# Podríamos necesitar crear un índice en la columna `embedding` para búsquedas vectoriales eficientes.
# Esto se hace directamente en SQL después de crear la tabla, o Alembic puede manejarlo.
# Ejemplo de índice HNSW (uno de los recomendados para pgvector):
# CREATE INDEX ON document_chunks USING hnsw (embedding vector_l2_ops);
# O IVFFlat:
# CREATE INDEX ON document_chunks USING ivfflat (embedding vector_l2_ops) WITH (lists = 100);
# Lo manejaremos después de crear las tablas.