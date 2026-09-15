FROM python:3.13.14-slim

# Prevents Python from writing pyc files and buffers stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/home/aiops/.local/bin:$PATH"

WORKDIR /app

# Create a non-root user for security
RUN groupadd -r aiops && useradd -r -g aiops aiops \
    && chown -R aiops:aiops /app

# Install runtime dependencies. Note: requirements.txt should be copied from the root context
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Switch to non-root user
USER aiops

# Copy Python source code. Note: context should be the root of the project
COPY --chown=aiops:aiops kubernetes_agent/ ./kubernetes_agent/

# Create data and db directories
RUN mkdir -p data db

EXPOSE 8000

# Start the FastAPI server via Uvicorn
CMD ["uvicorn", "kubernetes_agent.main:app", "--host", "0.0.0.0", "--port", "8000"]
