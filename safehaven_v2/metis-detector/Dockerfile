FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
RUN addgroup --system metis && adduser --system --ingroup metis metis && chown -R metis:metis /app

ENV PYTHONUNBUFFERED=1
EXPOSE 8090

USER metis
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8090"]
