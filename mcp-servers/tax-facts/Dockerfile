FROM python:3.14-slim
WORKDIR /app
COPY . /app
EXPOSE 8102
CMD ["uvicorn", "ssra_mcp_tax_facts.server:app", "--host", "0.0.0.0", "--port", "8102", "--no-access-log"]
