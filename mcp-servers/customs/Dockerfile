FROM python:3.14-slim
WORKDIR /app
COPY . /app
EXPOSE 8108
CMD ["uvicorn", "ssra_mcp_customs.server:app", "--host", "0.0.0.0", "--port", "8108", "--no-access-log"]
