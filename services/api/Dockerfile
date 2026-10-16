FROM python:3.14-slim
WORKDIR /app
COPY . /app
EXPOSE 8000
CMD ["uvicorn", "ssra_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
