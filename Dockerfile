# ---- Stage 1: build the React page ----
FROM node:26-slim AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: the Python app ----
FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1
WORKDIR /app
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
COPY --from=frontend /frontend/dist ./static
ENV STATIC_DIR=/app/static
ENV PORT=8080
RUN useradd --create-home appuser
USER appuser
CMD ["sh", "-c", "exec uvicorn api:app --host 0.0.0.0 --port ${PORT}"]