FROM python:3.14-slim
WORKDIR /app
COPY . /app
EXPOSE 8002
CMD ["uvicorn", "ssra_channel_gateway.main:app", "--host", "0.0.0.0", "--port", "8002", "--no-access-log"]
