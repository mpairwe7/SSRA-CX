FROM python:3.14-slim
WORKDIR /app
COPY . /app
EXPOSE 8111
CMD ["uvicorn", "ssra_mcp_notifications.server:app", "--host", "0.0.0.0", "--port", "8111", "--no-access-log"]
