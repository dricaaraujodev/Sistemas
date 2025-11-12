package main

import (
    "encoding/json"
    "fmt"
    "time"

    zmq "github.com/pebbe/zmq4"
)

type Message struct {
    Service string      `json:"service"`
    Data    interface{} `json:"data"`
}

func sendRequest(socket *zmq.Socket, msg Message) {
    req, _ := json.Marshal(msg)
    socket.Send(string(req), 0)
    reply, _ := socket.Recv(0)
    fmt.Println("📨 Resposta:", reply)
}

func main() {
    socket, _ := zmq.NewSocket(zmq.REQ)
    defer socket.Close()
    socket.Connect("tcp://server:5555")
    fmt.Println("🔗 Conectado ao servidor.")

    // Login
    sendRequest(socket, Message{
        Service: "login",
        Data: map[string]interface{}{
            "user":      "cliente_go",
            "timestamp": time.Now().Format(time.RFC3339),
        },
    })

    // Listar usuários
    sendRequest(socket, Message{
        Service: "users",
        Data: map[string]interface{}{
            "timestamp": time.Now().Format(time.RFC3339),
        },
    })

    // Criar canal
    sendRequest(socket, Message{
        Service: "channel",
        Data: map[string]interface{}{
            "channel":   "geral",
            "timestamp": time.Now().Format(time.RFC3339),
        },
    })

    // Listar canais
    sendRequest(socket, Message{
        Service: "channels",
        Data: map[string]interface{}{
            "timestamp": time.Now().Format(time.RFC3339),
        },
    })
}
