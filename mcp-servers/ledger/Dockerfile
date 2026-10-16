FROM python:3.14-slim
WORKDIR /app
COPY . /app
EXPOSE 8104
CMD ["uvicorn", "ssra_mcp_ledger.server:app", "--host", "0.0.0.0", "--port", "8104", "--no-access-log"]
