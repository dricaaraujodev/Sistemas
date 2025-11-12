FROM golang:1.24.5

WORKDIR /app

# dependências do sistema para zmq4
RUN apt-get update && apt-get install -y \
    pkg-config \
    libzmq3-dev \
 && rm -rf /var/lib/apt/lists/*

COPY go.mod go.sum ./
RUN go mod download

COPY . .

RUN go build -o client

# cria diretório para persistência
RUN mkdir -p /app/data

CMD ["./client"]
