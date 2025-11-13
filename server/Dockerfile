FROM python:3.11-slim
WORKDIR /app
COPY server.py .
COPY templates ./templates
RUN pip install pyzmq flask
EXPOSE 8080 5555
CMD ["python", "server.py"]
