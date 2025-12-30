FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Environment variables will be passed at runtime or loaded from .env
# CMD ["python", "newbot.py"]
CMD ["python", "newbot.py"]
