FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml .
COPY src ./src
RUN pip install --no-cache-dir .
RUN addgroup --system safehaven && adduser --system --ingroup safehaven safehaven && chown -R safehaven:safehaven /app

ENV PYTHONUNBUFFERED=1
EXPOSE 9108
EXPOSE 9109

USER safehaven
CMD ["safehaven-core"]
