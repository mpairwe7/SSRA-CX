FROM python:3.14-slim
WORKDIR /app
COPY . /app
EXPOSE 8109
CMD ["uvicorn", "ssra_mcp_cases.server:app", "--host", "0.0.0.0", "--port", "8109", "--no-access-log"]
