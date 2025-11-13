package main

import (
	"encoding/json"
	"fmt"
	"log"
	"math/rand"
	"os"
	"time"

	zmq "github.com/pebbe/zmq4"
)

// util timestamp ISO
func nowISO() string {
	return time.Now().UTC().Format(time.RFC3339)
}

// helper: envia requisição REQ/REP e recebe resposta JSON decodificada em map
func sendRequest(req *zmq.Socket, service string, data map[string]interface{}) (map[string]interface{}, error) {
	body := map[string]interface{}{
		"service": service,
		"data":    data,
	}
	b, err := json.Marshal(body)
	if err != nil {
		return nil, err
	}
	if _, err := req.Send(string(b), 0); err != nil {
		return nil, err
	}
	rep, err := req.Recv(0)
	if err != nil {
		return nil, err
	}

	var resp map[string]interface{}
	if err := json.Unmarshal([]byte(rep), &resp); err != nil {
		return nil, fmt.Errorf("erro ao decodificar resposta: %w (raw: %s)", err, rep)
	}
	return resp, nil
}

// extrai slice de strings de possíveis campos (channels/users) suportando variações
func extractStringListFromData(data map[string]interface{}, keys ...string) []string {
	for _, k := range keys {
		if v, ok := data[k]; ok {
			switch vv := v.(type) {
			case []interface{}:
				out := make([]string, 0, len(vv))
				for _, item := range vv {
					if s, ok := item.(string); ok {
						out = append(out, s)
					}
				}
				return out
			case []string:
				return vv
			}
		}
	}
	return nil
}

func main() {
	rand.Seed(time.Now().UnixNano())

	serverHost := os.Getenv("SERVER_HOST")
	if serverHost == "" {
		serverHost = "server"
	}

	// cria socket REQ
	req, err := zmq.NewSocket(zmq.REQ)
	if err != nil {
		log.Fatalf("erro ao criar socket REQ: %v", err)
	}
	defer req.Close()

	addr := fmt.Sprintf("tcp://%s:5555", serverHost)
	if err := req.Connect(addr); err != nil {
		log.Fatalf("erro ao conectar ao servidor %s: %v", addr, err)
	}
	fmt.Println("Go client connected to server:", serverHost)

	// 1) Tenta login/registro (tenta "register" -> "login")
	user := fmt.Sprintf("go_client_%d", rand.Intn(1_000_000))
	fmt.Printf("Cliente escolhido: %s\n", user)

	// função auxiliar para tratar resposta de login
	handleLoginResponse := func(resp map[string]interface{}) (bool, string) {
		if resp == nil {
			return false, "resposta vazia"
		}
		if d, ok := resp["data"].(map[string]interface{}); ok {
			// status pode ser "sucesso", "OK", "ok"
			if st, ok := d["status"].(string); ok {
				if st == "sucesso" || st == "OK" || st == "ok" {
					return true, ""
				}
				return false, st
			}
			// às vezes servidor usa outro campo — considerar sucesso
			return true, ""
		}
		return false, "campo data ausente"
	}

	// primeiro: try register (alguns servidores usam register)
	if resp, err := sendRequest(req, "register", map[string]interface{}{"user": user, "timestamp": nowISO()}); err == nil {
		ok, msg := handleLoginResponse(resp)
		if ok {
			fmt.Println("Registro realizado com sucesso (register).")
		} else {
			fmt.Printf("Register retornou: %s — tentando login...\n", msg)
			// tenta login em seguida
			if resp2, err2 := sendRequest(req, "login", map[string]interface{}{"user": user, "timestamp": nowISO()}); err2 == nil {
				if ok2, msg2 := handleLoginResponse(resp2); ok2 {
					fmt.Println("Login realizado com sucesso (login).")
				} else {
					log.Fatalf("login/register falharam: %s", msg2)
				}
			} else {
				log.Fatalf("erro ao tentar login: %v", err2)
			}
		}
	} else {
		// register deu erro — tenta login direto
		fmt.Printf("register erro: %v — tentando login...\n", err)
		if resp2, err2 := sendRequest(req, "login", map[string]interface{}{"user": user, "timestamp": nowISO()}); err2 == nil {
			if ok2, msg2 := handleLoginResponse(resp2); ok2 {
				fmt.Println("Login realizado com sucesso (login).")
			} else {
				// Se login tbm falhar, abortamos com log
				log.Fatalf("login falhou: %s", msg2)
			}
		} else {
			log.Fatalf("erro ao tentar login: %v", err2)
		}
	}

	// 2) solicita lista de canais — usa EXPLICITAMENTE "channels" e data.channels
	var channels []string
	{
		resp, err := sendRequest(req, "channels", map[string]interface{}{"timestamp": nowISO()})
		if err != nil {
			fmt.Println("Erro ao solicitar canais:", err)
		} else {
			if d, ok := resp["data"].(map[string]interface{}); ok {
				// preferimos data.channels (correto conforme servidor ajustado)
				if chs := extractStringListFromData(d, "channels"); len(chs) > 0 {
					channels = chs
					fmt.Println("Canais obtidos (channels):", channels)
				} else if chs := extractStringListFromData(d, "users"); len(chs) > 0 {
					// compatibilidade adicional caso servidor retorne 'users' por engano
					channels = chs
					fmt.Println("Canais obtidos (users):", channels)
				}
			}
		}
	}

	// se ainda vazio, usa fallback sensato que existe no servidor por padrão
	if len(channels) == 0 {
		channels = []string{"geral", "dev", "random", "announcements"}
		fmt.Println("Nenhum canal retornado pelo servidor — usando fallback:", channels)
	}

	// 3) solicita lista de usuários (opcional, útil para PM)
	if resp, err := sendRequest(req, "users", map[string]interface{}{"timestamp": nowISO()}); err == nil {
		if d, ok := resp["data"].(map[string]interface{}); ok {
			users := extractStringListFromData(d, "users")
			if len(users) > 0 {
				fmt.Println("Usuários cadastrados:", users)
			}
		}
	} else {
		fmt.Println("Solicitação de users falhou (não crítica):", err)
	}

	// 4) fetch offline (se suportado pelo servidor)
	if resp, err := sendRequest(req, "fetch_offline", map[string]interface{}{"user": user}); err == nil {
		if d, ok := resp["data"].(map[string]interface{}); ok {
			if msgsAny, ok := d["messages"].([]interface{}); ok && len(msgsAny) > 0 {
				fmt.Printf("Recebeu %d mensagens offline:\n", len(msgsAny))
				for _, mi := range msgsAny {
					if m, ok := mi.(map[string]interface{}); ok {
						fmt.Printf("  de=%v msg=%v ts=%v\n", m["src"], m["message"], m["timestamp"])
					}
				}
			}
		}
	} else {
		// não é fatal se servidor não implementar
		fmt.Println("fetch_offline não disponível ou falhou (não crítico):", err)
	}

	// 5) Loop principal: escolher canal aleatório e enviar 10 mensagens
	fmt.Println("Entrando no loop de envio: escolher canal aleatório -> enviar 10 msgs -> repetir")

	for {
		ch := channels[rand.Intn(len(channels))]
		for i := 1; i <= 10; i++ {
			msgText := fmt.Sprintf("mensagem %d do %s para canal %s", i, user, ch)
			resp, err := sendRequest(req, "publish", map[string]interface{}{
				"user":      user,
				"channel":   ch,
				"message":   msgText,
				"timestamp": nowISO(),
			})
			if err != nil {
				fmt.Printf("[publish] erro: %v\n", err)
			} else {
				// tenta extrair status amigável
				status := "unknown"
				if d, ok := resp["data"].(map[string]interface{}); ok {
					if s, ok := d["status"].(string); ok {
						status = s
					} else if s, ok := d["status"].(interface{}); ok {
						// caso servidor use booleano ou outro formato
						status = fmt.Sprintf("%v", s)
					}
					if m, ok := d["description"].(string); ok && status != "OK" {
						fmt.Printf("[publish] canal=%s user=%s resp_status=%s desc=%s\n", ch, user, status, m)
					}
				}
				if status == "OK" || status == "sucesso" || status == "ok" {
					fmt.Printf("📢 [%s] %s: \"%s\"\n", ch, user, msgText)
				} else {
					fmt.Printf("⚠️ publish canal=%s retornou status=%s\n", ch, status)
				}
			}
			time.Sleep(300 * time.Millisecond)
		}

		// opcional: envia uma private message para usuário aleatório
		if resp, err := sendRequest(req, "users", map[string]interface{}{"timestamp": nowISO()}); err == nil {
			if d, ok := resp["data"].(map[string]interface{}); ok {
				users := extractStringListFromData(d, "users")
				if len(users) > 1 {
					// escolhe destinatário diferente de si mesmo
					var dst string
					for {
						cand := users[rand.Intn(len(users))]
						if cand != user {
							dst = cand
							break
						}
					}
					pmText := fmt.Sprintf("oi %s, sou %s — teste pm", dst, user)
					if resp2, err2 := sendRequest(req, "message", map[string]interface{}{
						"src":       user,
						"dst":       dst,
						"message":   pmText,
						"timestamp": nowISO(),
					}); err2 == nil {
						st := "unknown"
						if d2, ok := resp2["data"].(map[string]interface{}); ok {
							if s, ok := d2["status"].(string); ok {
								st = s
							}
						}
						fmt.Printf("🔐 PV %s -> %s resposta=%s\n", user, dst, st)
					} else {
						fmt.Println("erro ao enviar PM (não crítico):", err2)
					}
				}
			}
		}

		time.Sleep(2 * time.Second)
	}
}
