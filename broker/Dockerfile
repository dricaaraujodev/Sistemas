FROM python:3.10
WORKDIR /app
COPY broker.py .
RUN pip install pyzmq
CMD ["python", "broker.py"]
