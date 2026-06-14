FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
COPY README.md .
COPY src ./src
COPY frontend ./frontend
RUN pip install --no-cache-dir .
ENV PYTHONUNBUFFERED=1
ENV FRONTEND_DIR=/app/frontend
EXPOSE 8000
CMD ["uvicorn", "hunchlog.main:app", "--host", "0.0.0.0", "--port", "8000"]
