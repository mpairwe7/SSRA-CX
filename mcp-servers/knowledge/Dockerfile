FROM python:3.14-slim
WORKDIR /app
COPY . /app
EXPOSE 8101
CMD ["uvicorn", "ssra_mcp_knowledge.server:app", "--host", "0.0.0.0", "--port", "8101", "--no-access-log"]
