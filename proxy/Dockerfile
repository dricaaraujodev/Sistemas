# Proxy/Dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY Proxy.py .

RUN pip install pyzmq

CMD ["python", "Proxy.py"]
