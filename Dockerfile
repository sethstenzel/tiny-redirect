# TinyRedirect Docker Image
# Build: docker build -t tiny-redirect .
# Run: docker run -d -p 80:80 -v tinyredirect-data:/data --name tinyredirect tiny-redirect

FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install dependencies
# Note: We only install the cross-platform dependencies, not Windows-specific ones
RUN pip install --no-cache-dir \
    bottle>=0.12.21 \
    pillow>=10.0.0 \
    requests>=2.32.5

# Copy application code
COPY src/tiny_redirect /app/tiny_redirect

# Create data directory for database persistence
RUN mkdir -p /data

# Set environment variables
ENV TINYREDIRECT_DB_PATH=/data/redirects.db
ENV TINYREDIRECT_HOST=0.0.0.0
ENV TINYREDIRECT_PORT=80
ENV PYTHONUNBUFFERED=1

# Expose port (default 80, can be overridden)
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:80/')" || exit 1

# Run the application
# Using --startup to suppress browser opening (not available in container)
# Setting hostname to 0.0.0.0 to accept connections from outside container
CMD ["python", "-m", "tiny_redirect", "--startup"]
