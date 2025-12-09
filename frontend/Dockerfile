FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

# Copy pyproject.toml for dependencies
COPY pyproject.toml ./

# Install Python dependencies using uv sync
RUN uv sync --system --no-dev

# Copy frontend source code
COPY frontend/ ./

# Create non-root user
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

# Expose port
EXPOSE 8080

# Run the application
CMD ["python", "app.py"]