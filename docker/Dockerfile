FROM python:3.11

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the FastAPI application and database files
COPY irrigation_api.py .
COPY database.py .
COPY models.py .
COPY irrigation_db_service.py .
COPY irrigation_plans.json .

# Create non-root user for security and set proper ownership
RUN useradd -m -u 1000 irrigation && chown -R irrigation:irrigation /app
USER irrigation

# Make sure JSON file is writable
RUN chmod 666 irrigation_plans.json

# Expose the port that FastAPI will run on
EXPOSE 8000

# Run the FastAPI application
CMD ["python", "irrigation_api.py"]