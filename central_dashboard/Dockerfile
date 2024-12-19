FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY central_dashboard.py .

CMD ["uvicorn", "central_dashboard:app", "--host", "0.0.0.0", "--port", "8000"]
