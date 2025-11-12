FROM golang:1.24

WORKDIR /app
COPY go.mod go.sum ./

# Instala bibliotecas do sistema necessárias para zmq4
RUN apt-get update && apt-get install -y \
    pkg-config \
    libzmq3-dev \
 && rm -rf /var/lib/apt/lists/*

# Baixa dependências
RUN go mod download

# Copia o restante do código. 
# ESTA LINHA É CRUCIAL, POIS COPIA O main.go PARA /app
COPY . . 

# Compila o client. 
# AGORA O main.go está em /app, e o build deve funcionar.
RUN go build -o client

CMD ["./client"]