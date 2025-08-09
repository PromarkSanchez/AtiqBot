# Usa una imagen base de Python 3.13
FROM python:3.13-slim

WORKDIR /app

# ---- ¡AQUÍ ESTÁ EL CAMBIO! ----
# Añadimos "build-essential" a la lista de paquetes a instalar.
RUN apt-get update && apt-get install -y \
    build-essential \
    tesseract-ocr \
    tesseract-ocr-spa \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Copia el archivo de requerimientos
COPY mi_chatbot_ia/requirements.txt .

# Instala las dependencias de Python
# Esta vez, pip SÍ encontrará los compiladores que necesita.
RUN pip install --no-cache-dir -r requirements.txt

# Copia todo el contenido de la carpeta mi_chatbot_ia al directorio de trabajo actual (/app)
COPY mi_chatbot_ia/ .

# El CMD para iniciar se queda igual
CMD ["gunicorn", "-w", "2", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:$PORT", "app.main:app"]