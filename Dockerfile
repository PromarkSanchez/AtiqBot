# Usa una imagen base de Python 3.13
FROM python:3.13-slim

# Establece el directorio de trabajo donde vivirá todo.
WORKDIR /app

# Instala dependencias del sistema operativo para OCR
RUN apt-get update && apt-get install -y \
    build-essential \
    tesseract-ocr \
    tesseract-ocr-spa \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Copia tu código Python DENTRO de una subcarpeta, para mantener el orden.
# Es una práctica recomendada no mezclar código con archivos de configuración.
COPY mi_chatbot_ia/ /app/

# ------- ¡LA MAGIA ESTÁ AQUÍ! -------
# Le decimos a Python: "Cuando busques módulos, busca en /app".
# De esta forma, cuando Gunicorn pida "app.main:app", Python sabrá que
# debe buscar una carpeta llamada 'app' dentro de '/app'.
ENV PYTHONPATH=/app
# -----------------------------------

# Instala las dependencias de Python (el requirements.txt ya está en /app)
RUN pip install --no-cache-dir -r requirements.txt

# El CMD para iniciar la aplicación. Ahora Python SÍ encontrará 'app.main:app'.
CMD ["gunicorn", "-w", "2", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:$PORT", "app.main:app"]