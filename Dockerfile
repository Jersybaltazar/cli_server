FROM python:3.12-slim

WORKDIR /app

# Dependencias del sistema:
#   gcc, libpq-dev   → compilar psycopg/asyncpg
#   libpango/cairo/… → WeasyPrint (renderizado de PDFs)
#   shared-mime-info → detección de tipos MIME por WeasyPrint
#   fonts-dejavu     → fuentes por defecto para los PDFs
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libharfbuzz0b \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    fonts-dejavu \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements e instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copiar código fuente
COPY . .

# Exponer puerto (Render inyecta $PORT en runtime)
EXPOSE 8000

# Comando de inicio — usa $PORT que Render asigna automáticamente
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
