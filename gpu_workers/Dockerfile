FROM pytorch/pytorch:2.6.0-cuda12.6-cudnn9-runtime

WORKDIR /app

# Install additional packages - removing nvtop as it's not available in the default repos
RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    curl \
    htop \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the worker code
COPY . .

# Run the worker process
CMD ["python", "worker.py"]