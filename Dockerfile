# ==============================================================================
# 1. Frontend Build Stage
# ==============================================================================
FROM node:20-alpine AS frontend-builder
WORKDIR /app/dashboard

# Install dependencies
COPY dashboard/package.json dashboard/package-lock.json ./
RUN npm ci

# Copy source and build
COPY dashboard/ ./
RUN npm run build

# ==============================================================================
# 2. Python Backend Stage
# ==============================================================================
FROM python:3.12-slim AS backend

# Prevents Python from writing pyc files and buffers stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # Ensure local python binaries are in path
    PATH="/home/aiops/.local/bin:$PATH"

WORKDIR /app

# Create a non-root user for security
RUN groupadd -r aiops && useradd -r -g aiops aiops \
    && chown -R aiops:aiops /app

# Install runtime dependencies (no dev tools needed)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Switch to non-root user
USER aiops

# Copy Python source code
COPY --chown=aiops:aiops kubernetes_agent/ ./kubernetes_agent/

# Copy compiled frontend assets from the first stage
COPY --from=frontend-builder --chown=aiops:aiops /app/dashboard/dist/ ./dashboard/dist/

# Create data directory for JSON persistence (namespace settings)
RUN mkdir -p data

EXPOSE 8000

# Start the FastAPI server via Uvicorn
CMD ["uvicorn", "kubernetes_agent.main:app", "--host", "0.0.0.0", "--port", "8000"]
