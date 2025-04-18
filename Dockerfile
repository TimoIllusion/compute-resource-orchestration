# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
# Using --no-cache-dir to reduce image size
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container at /app
COPY . .

# Make port 8000 available to the world outside this container (FastAPI default)
EXPOSE 8000

# Define environment variable (optional, can be set in docker-compose)
# ENV NAME World

# Run app.py when the container launches using uvicorn
# Use --host 0.0.0.0 to be accessible externally
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
