FROM golang:1.22

WORKDIR /app

# Instala dependências necessárias para libzmq
RUN apt-get update && apt-get install -y libzmq3-dev pkg-config

COPY client.go .

RUN go mod init client
RUN go get github.com/pebbe/zmq4
RUN go build -o client

CMD ["./client"]
