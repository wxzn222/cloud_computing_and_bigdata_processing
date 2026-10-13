FROM python:3.12.10-slim
WORKDIR /app
COPY requirements.container.txt /app/requirements.container.txt
RUN pip install --no-cache-dir -r requirements.container.txt
COPY coursekit /app/coursekit
ENV BDP_ROOT=/workspace PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "coursekit.service:app", "--host", "0.0.0.0", "--port", "8000"]
