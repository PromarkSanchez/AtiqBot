# Usar una imagen base de Python 3.13
FROM python:3.13-slim

# Establecer directorio de trabajo
WORKDIR /app

# Instalar dependencias del sistema operativo para OCR
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-spa \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Copiar archivo de requerimientos
COPY mi_chatbot_ia/requirements.txt .

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código de la aplicación
COPY . .

# Comando para iniciar la aplicación (Render usará la variable $PORT)
CMD ["gunicorn", "-w", "2", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:$PORT", "app.main:app"]