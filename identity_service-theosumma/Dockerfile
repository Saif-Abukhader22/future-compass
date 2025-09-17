# identity-service docker image
FROM python:3.11-slim-bullseye

# Create an application directory
ENV APP_HOME=/app
WORKDIR $APP_HOME

# Install system dependencies required for building Python packages and libmagic
RUN apt-get update && apt-get install -y \
    libpq-dev \
    build-essential \
    file \
    curl \
    nano \
    && rm -rf /var/lib/apt/lists/*

# Copy the 'identity_service' folder into the container
COPY identity_service/ ./identity_service
COPY shared/ ./shared


# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r ./identity_service/requirements.txt
RUN pip install --no-cache-dir -r ./shared/requirements.txt

# Remove build tools to keep the image light (optional but recommended)
RUN apt-get remove -y build-essential

# Expose FastAPI port
EXPOSE 8000

# By default, run the main FastAPI service
CMD ["uvicorn", "identity_service.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
