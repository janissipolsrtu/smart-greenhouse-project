FROM python:3.11

# Set working directory
WORKDIR /app

# Copy requirements from config directory and install dependencies
COPY config/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Set environment to development
ENV PYTHONPATH=/app

# Create non-root user for security
RUN useradd -m -u 1000 irrigation && chown -R irrigation:irrigation /app
USER irrigation

# Expose the port that FastAPI will run on
EXPOSE 8000

# The source code will be mounted as a volume
# Run the FastAPI application
CMD ["python", "irrigation_api.py"]