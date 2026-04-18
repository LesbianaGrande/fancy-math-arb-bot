FROM python:3.11-slim

WORKDIR /app

# Install CBC solver (PuLP dependency)
RUN apt-get update && apt-get install -y coinor-cbc

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create templates directory
RUN mkdir -p templates

COPY . .

CMD ["uvicorn", "dashboard:app", "--host", "0.0.0.0", "--port", "8080"]
