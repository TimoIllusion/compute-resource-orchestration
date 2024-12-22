# Dockerfile
FROM python:3.10-slim

# Install OS-level dependencies if needed. For example (uncomment if needed):
# RUN apt-get update && apt-get install -y \
#     build-essential \
#     && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy in requirements and install them
COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Copy the rest of the code (db.py, cluster.py, main.py, etc.)
COPY . .

# By default, Streamlit runs on port 8501.
EXPOSE 8501

# Run the streamlit app
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
