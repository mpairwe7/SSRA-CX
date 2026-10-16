FROM python:3.14-slim
WORKDIR /app
COPY . /app
EXPOSE 8110
CMD ["uvicorn", "ssra_mcp_appointments.server:app", "--host", "0.0.0.0", "--port", "8110", "--no-access-log"]
