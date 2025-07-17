# Start from a slim Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /

# Copy dependencies first (use Docker cache efficiently)
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy rest of the code
COPY . .

ENV PYTHONPATH=/backend


# Expose the port your app runs on
EXPOSE 5000

# Run with Gunicorn (binds to all interfaces, 4 worker processes)
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "backend.app:app"]
