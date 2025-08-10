# Usa la imagen base de Python que te funcionó localmente (3.13)
FROM python:3.13-slim

# Establece el directorio de trabajo donde vivirá el código
WORKDIR /app

# Instala todas las dependencias del sistema operativo que descubrimos que eran necesarias
RUN apt-get update && apt-get install -y \
    build-essential \
    tesseract-ocr \
    tesseract-ocr-spa \
    poppler-utils \
    libgl1-mesa-glx \
    && rm -rf /var/lib/apt/lists/*

# Copia primero el requirements.txt para aprovechar la caché de Docker
COPY mi_chatbot_ia/requirements.txt ./

# Instala las dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copia el resto del código de tu aplicación al directorio de trabajo
COPY mi_chatbot_ia/ .

# El comando de inicio: "usa el $PORT de Render, o si no existe, usa 10000"
# (Render siempre te dará un $PORT). Incluimos el --preload que mencionaste.
CMD gunicorn --preload -w 2 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:${PORT:-10000} app.main:app