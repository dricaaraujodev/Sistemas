# broker/Dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY broker.py .

RUN pip install pyzmq

CMD ["python", "broker.py"]
