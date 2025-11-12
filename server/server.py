import zmq
import json
import os
from datetime import datetime

DATA_DIR = "data"
USERS_FILE = os.path.join(DATA_DIR, "users.json")
CHANNELS_FILE = os.path.join(DATA_DIR, "channels.json")

# Cria diretório de dados se não existir
os.makedirs(DATA_DIR, exist_ok=True)

# Funções auxiliares
def load_json(path):
    """Carrega JSON do arquivo, retorna lista vazia se não existir ou estiver vazio."""
    if not os.path.exists(path) or os.stat(path).st_size == 0:
        return []
    with open(path, "r") as f:
        content = f.read().strip()
        return json.loads(content) if content else []

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def timestamp():
    return datetime.now().isoformat()

# Inicializa persistência
users = load_json(USERS_FILE)
channels = load_json(CHANNELS_FILE)

# Configura ZeroMQ REP socket
context = zmq.Context()
socket = context.socket(zmq.REP)
socket.bind("tcp://*:5555")

print("📡 Servidor ativo em tcp://*:5555")

while True:
    msg = socket.recv_json()
    service = msg.get("service")
    data = msg.get("data", {})
    response = {"service": service, "data": {}}

    if service == "login":
        user = data.get("user")
        if user in users:
            response["data"] = {
                "status": "erro",
                "timestamp": timestamp(),
                "description": "Usuário já logado."
            }
        else:
            users.append(user)
            save_json(USERS_FILE, users)
            response["data"] = {
                "status": "sucesso",
                "timestamp": timestamp()
            }

    elif service == "users":
        response["data"] = {
            "timestamp": timestamp(),
            "users": users
        }

    elif service == "channel":
        channel = data.get("channel")
        if channel in channels:
            response["data"] = {
                "status": "erro",
                "timestamp": timestamp(),
                "description": "Canal já existe."
            }
        else:
            channels.append(channel)
            save_json(CHANNELS_FILE, channels)
            response["data"] = {
                "status": "sucesso",
                "timestamp": timestamp()
            }

    elif service == "channels":
        response["data"] = {
            "timestamp": timestamp(),
            "channels": channels
        }

    else:
        response["data"] = {
            "status": "erro",
            "timestamp": timestamp(),
            "description": "Serviço desconhecido."
        }

    socket.send_json(response)
