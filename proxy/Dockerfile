FROM python:3.11-slim
WORKDIR /app
COPY proxy.py .
RUN pip install pyzmq
EXPOSE 5557 5558
CMD ["python", "proxy.py"]
