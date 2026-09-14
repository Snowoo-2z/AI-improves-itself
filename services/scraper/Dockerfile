FROM python:3.11-slim

WORKDIR /app

# Dépendances système requises par Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && playwright install --with-deps chromium

COPY . .

# Render impose son propre port via la variable d'env PORT : le service DOIT
# l'écouter (sinon le health-check échoue → le service marque 502/crash-loop).
# Local (docker run sans PORT) : repli sur 8000.
ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
