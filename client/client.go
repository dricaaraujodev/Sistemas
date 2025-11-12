package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"
	"strings"
	"sync"
	"time"

	zmq "github.com/pebbe/zmq4"
)

// --- CONFIGURAÇÃO ---
const (
	DATA_DIR      = "data"
	MESSAGES_FILE = "data/messages.json"
)

// --- ESTRUTURAS ---
type MessageEntry struct {
	Type      string `json:"type"`
	User      string `json:"user,omitempty"`
	Src       string `json:"src,omitempty"`
	Dst       string `json:"dst,omitempty"`
	Channel   string `json:"channel,omitempty"`
	Message   string `json:"message"`
	Timestamp string `json:"timestamp"`
	Raw       string `json:"raw,omitempty"`
}

// --- VARIÁVEIS GLOBAIS ---
var (
	mu       sync.Mutex
	messages []MessageEntry
	botID    string
)

// --- FUNÇÕES AUXILIARES ---
func now() string {
	return time.Now().Format(time.RFC3339Nano)
}

func ensureDataDir() error {
	if _, err := os.Stat(DATA_DIR); os.IsNotExist(err) {
		return os.MkdirAll(DATA_DIR, 0755)
	}
	return nil
}

func loadMessages() {
	mu.Lock()
	defer mu.Unlock()
	if _, err := os.Stat(MESSAGES_FILE); os.IsNotExist(err) {
		messages = []MessageEntry{}
		return
	}
	f, err := os.Open(MESSAGES_FILE)
	if err != nil {
		fmt.Println("⚠️ Erro ao abrir messages.json:", err)
		messages = []MessageEntry{}
		return
	}
	defer f.Close()
	if err := json.NewDecoder(f).Decode(&messages); err != nil {
		fmt.Println("⚠️ Arquivo messages.json inválido, criando novo.")
		messages = []MessageEntry{}
	}
}

func saveMessages() {
	mu.Lock()
	defer mu.Unlock()
	tmp := MESSAGES_FILE + ".tmp"
	f, err := os.Create(tmp)
	if err != nil {
		fmt.Println("⚠️ Erro ao criar arquivo temporário:", err)
		return
	}
	json.NewEncoder(f).Encode(messages)
	f.Close()
	os.Rename(tmp, MESSAGES_FILE)
}

func appendMessage(m MessageEntry) {
	mu.Lock()
	messages = append(messages, m)
	mu.Unlock()
	saveMessages()
}

// --- ENVIO REQ/REP ---
func sendReq(socket *zmq.Socket, service string, data map[string]interface{}) (map[string]interface{}, error) {
	msg := map[string]interface{}{
		"service": service,
		"data":    data,
	}
	b, _ := json.Marshal(msg)
	if _, err := socket.SendBytes(b, 0); err != nil {
		return nil, err
	}
	replyBytes, err := socket.RecvBytes(0)
	if err != nil {
		return nil, err
	}
	var rep map[string]interface{}
	if err := json.Unmarshal(replyBytes, &rep); err != nil {
		return nil, err
	}
	return rep, nil
}

// --- RECEBIMENTO (SUB) ---
func parseAndStoreIncoming(topic, payload, self string) {
	ts := now()
	raw := fmt.Sprintf("%s|%s", topic, payload)

	if topic == self {
		// mensagem privada recebida
		idx := strings.Index(payload, "enviou mensagem privada:")
		if idx >= 0 {
			src := strings.TrimSpace(strings.TrimPrefix(payload[:idx], "🔒"))
			msgPart := strings.TrimSpace(payload[idx+len("enviou mensagem privada:"):])
			appendMessage(MessageEntry{"private", "", src, self, "", msgPart, ts, raw})
			fmt.Printf("\n💌 %s recebeu mensagem privada de %s: \"%s\"\n", self, src, msgPart)
			return
		}
		appendMessage(MessageEntry{"private", "", "", self, "", payload, ts, raw})
		fmt.Printf("\n💌 %s recebeu (privado): \"%s\"\n", self, payload)
		return
	}

	// mensagem de canal
	idx := strings.Index(payload, ":")
	if idx >= 0 {
		left := strings.TrimSpace(payload[:idx])
		msgPart := strings.TrimSpace(payload[idx+1:])
		user := strings.Fields(left)[0]
		appendMessage(MessageEntry{"channel", user, "", "", topic, msgPart, ts, raw})
		fmt.Printf("\n💬 [%s] %s: \"%s\"\n", topic, user, msgPart)
	} else {
		appendMessage(MessageEntry{"channel", "", "", "", topic, payload, ts, raw})
		fmt.Printf("\n💬 [%s] %s\n", topic, payload)
	}
}

func subscriberLoop(sub *zmq.Socket, self string) {
	for {
		msgBytes, err := sub.RecvMessageBytes(0)
		if err != nil {
			fmt.Println("⚠️ Erro no SUB:", err)
			time.Sleep(500 * time.Millisecond)
			continue
		}
		var topic, payload string
		if len(msgBytes) == 1 {
			text := string(msgBytes[0])
			idx := strings.Index(text, "|")
			if idx >= 0 {
				topic, payload = text[:idx], text[idx+1:]
			} else {
				continue
			}
		} else if len(msgBytes) >= 2 {
			topic, payload = string(msgBytes[0]), string(msgBytes[1])
		}
		parseAndStoreIncoming(topic, payload, self)
	}
}

// --- MAIN ---
func main() {
	if err := ensureDataDir(); err != nil {
		fmt.Println("❌ Erro criando pasta data:", err)
		return
	}
	loadMessages()

	req, _ := zmq.NewSocket(zmq.REQ)
	defer req.Close()
	req.Connect("tcp://server:5555")

	sub, _ := zmq.NewSocket(zmq.SUB)
	defer sub.Close()
	sub.Connect("tcp://proxy:5558")

	reader := bufio.NewReader(os.Stdin)
	fmt.Print("Digite seu nome: ")
	nameRaw, _ := reader.ReadString('\n')
	username := strings.TrimSpace(nameRaw)
	if username == "" {
		fmt.Println("❌ Nome inválido.")
		return
	}
	botID = username // ID fixo

	fmt.Printf("🟢 %s entrou no sistema.\n", botID)

	// login
	if _, err := sendReq(req, "login", map[string]interface{}{"user": botID, "timestamp": now()}); err != nil {
		fmt.Println("❌ Erro no login:", err)
		return
	}

	// subscrever canais
	sub.SetSubscribe(botID) // privado
	if rep2, err := sendReq(req, "channels", map[string]interface{}{"timestamp": now()}); err == nil {
		if data, ok := rep2["data"].(map[string]interface{}); ok {
			if chs, ok2 := data["channels"].([]interface{}); ok2 {
				for _, c := range chs {
					if cs, ok3 := c.(string); ok3 {
						sub.SetSubscribe(cs)
						fmt.Printf("📡 %s entrou no canal %s\n", botID, cs)
					}
				}
			}
		}
	}

	go subscriberLoop(sub, botID)

	fmt.Println("💬 Use '@dest mensagem' para privado ou 'canal mensagem' para canal.")
	for {
		fmt.Print("> ")
		line, _ := reader.ReadString('\n')
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}

		if strings.HasPrefix(line, "@") {
			// mensagem privada
			parts := strings.Fields(line)
			if len(parts) < 2 {
				fmt.Println("❗ Use: @dest mensagem")
				continue
			}
			dst := strings.TrimPrefix(parts[0], "@")
			msg := strings.Join(parts[1:], " ")
			sendReq(req, "message", map[string]interface{}{
				"src":       botID,
				"dst":       dst,
				"message":   msg,
				"timestamp": now(),
			})
			appendMessage(MessageEntry{"sent_private", "", botID, dst, "", msg, now(), ""})
			fmt.Printf("🔒 %s enviou mensagem privada para %s: \"%s\"\n", botID, dst, msg)
		} else {
			// mensagem em canal
			parts := strings.Fields(line)
			if len(parts) < 2 {
				fmt.Println("❗ Use: canal mensagem")
				continue
			}
			channel := parts[0]
			msg := strings.Join(parts[1:], " ")
			sendReq(req, "publish", map[string]interface{}{
				"user":      botID,
				"channel":   channel,
				"message":   msg,
				"timestamp": now(),
			})
			appendMessage(MessageEntry{"sent_channel", botID, "", "", channel, msg, now(), ""})
			fmt.Printf("💬 %s enviou ao canal %s: \"%s\"\n", botID, channel, msg)
		}
	}
}
