# Usa una imagen base oficial de Python que coincida con tu entorno local.
# "slim" es una versión más ligera y recomendada para producción.
FROM python:3.13-slim

# Establece el directorio de trabajo dentro del contenedor
WORKDIR /app

# ---- Dependencias del Sistema Operativo ----
# Esto es para instalar Tesseract y Poppler en el entorno Linux del contenedor
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-spa \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# ---- Dependencias de Python ----
# Copia tu archivo de requerimientos (que sabes que funciona con Python 3.13)
COPY requirements.txt .

# Instala las librerías de Python desde tu archivo
RUN pip install --no-cache-dir -r requirements.txt

# Copia todo el código de tu aplicación al contenedor
COPY . .

# Expone el puerto que usará tu aplicación (Render lo gestionará)
EXPOSE 10000

# El comando para iniciar Uvicorn. Render puede sobrescribir esto con el "Start Command".
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "10000"]