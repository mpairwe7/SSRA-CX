FROM python:3.14-slim
WORKDIR /app
COPY . /app
EXPOSE 8103
CMD ["uvicorn", "ssra_mcp_official_channels.server:app", "--host", "0.0.0.0", "--port", "8103", "--no-access-log"]
