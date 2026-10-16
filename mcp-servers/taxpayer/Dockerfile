FROM python:3.14-slim
WORKDIR /app
COPY . /app
EXPOSE 8105
CMD ["uvicorn", "ssra_mcp_taxpayer.server:app", "--host", "0.0.0.0", "--port", "8105", "--no-access-log"]
