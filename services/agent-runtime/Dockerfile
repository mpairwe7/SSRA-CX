FROM python:3.14-slim
WORKDIR /app
COPY . /app
EXPOSE 8001
CMD ["uvicorn", "ssra_runtime.main:app", "--host", "0.0.0.0", "--port", "8001", "--no-access-log"]
