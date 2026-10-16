FROM python:3.14-slim
WORKDIR /app
COPY . /app
EXPOSE 8106
CMD ["uvicorn", "ssra_mcp_payments_info.server:app", "--host", "0.0.0.0", "--port", "8106", "--no-access-log"]
