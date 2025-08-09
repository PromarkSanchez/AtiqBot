# Usa una imagen base de Python 3.13
FROM python:3.13-slim

# Establece /app como el directorio de trabajo inicial
WORKDIR /app

# Instala dependencias del sistema operativo para OCR
RUN apt-get update && apt-get install -y \
    build-essential \
    tesseract-ocr \
    tesseract-ocr-spa \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Copia solo el archivo de requerimientos primero, para aprovechar la caché de Docker
COPY mi_chatbot_ia/requirements.txt ./

# Instala las dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Ahora copia todo el código de tu aplicación al directorio de trabajo actual (/app)
COPY mi_chatbot_ia/ .

# El comando para iniciar la aplicación.
# Como el 'WORKDIR' es '/app' y dentro de él está la carpeta 'app' y el 'main.py',
# Gunicorn lo encontrará correctamente.
CMD ["gunicorn", "-w", "2", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:$PORT", "app.main:app"]