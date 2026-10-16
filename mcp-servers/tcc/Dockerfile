FROM python:3.14-slim
WORKDIR /app
COPY . /app
EXPOSE 8107
CMD ["uvicorn", "ssra_mcp_tcc.server:app", "--host", "0.0.0.0", "--port", "8107", "--no-access-log"]
