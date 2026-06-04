FROM python:3.11-slim

WORKDIR /app

# System deps for GDAL/rasterio/geopandas
RUN apt-get update && apt-get install -y \
    libgdal-dev gdal-bin libspatialindex-dev \
    build-essential python3-dev \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY frontend/ ./frontend/

WORKDIR /app/backend

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
