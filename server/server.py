import zmq
import json
import os
import threading
from datetime import datetime
from flask import Flask, render_template, jsonify

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

USERS_FILE = os.path.join(DATA_DIR, "users.json")
CHANNELS_FILE = os.path.join(DATA_DIR, "channels.json")
MESSAGES_FILE = os.path.join(DATA_DIR, "messages.json")
OFFLINE_FILE = os.path.join(DATA_DIR, "messages-offline.json")

def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return default
    return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# Banco de dados
users = load_json(USERS_FILE, {})                  # { username: { online: True, last_seen: ... } }
channels = load_json(CHANNELS_FILE, ["geral", "dev", "random", "announcements"])
messages = load_json(MESSAGES_FILE, [])            # todas as mensagens publicadas
offline = load_json(OFFLINE_FILE, [])              # mensagens privadas offline

# ZMQ sockets
ctx = zmq.Context()

rep = ctx.socket(zmq.REQ)
rep = ctx.socket(zmq.REP)
rep.bind("tcp://0.0.0.0:5555")

pub = ctx.socket(zmq.PUB)
pub.connect("tcp://proxy:5557")

def ts():
    return datetime.utcnow().isoformat()

def persist_all():
    save_json(USERS_FILE, users)
    save_json(CHANNELS_FILE, channels)
    save_json(MESSAGES_FILE, messages)
    save_json(OFFLINE_FILE, offline)

# Dashboard
app = Flask(__name__, static_folder=os.path.join(BASE_DIR, "static"), template_folder=os.path.join(BASE_DIR, "templates"))

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/status")
def api_status():
    return jsonify({
        "channels": channels,
        "users_online": [u for u,info in users.items() if info.get("online")],
        "last_messages": messages[-50:],
        "offline": offline
    })

def run_flask():
    app.run(host="0.0.0.0", port=8080, debug=False)

t = threading.Thread(target=run_flask, daemon=True)
t.start()

print("Server ready: REQ/REP 5555 | PUB → proxy:5557 | Dashboard :8080")

# ---------------------------
#  MAIN LOOP - Request / Reply
# ---------------------------
while True:
    try:
        raw = rep.recv_string()
        req = json.loads(raw)
    except:
        rep.send_json({"service": "error", "data": {"message": "invalid request"}})
        continue

    service = req.get("service")
    data = req.get("data", {})

    # --------------------------------------
    # LOGIN
    # --------------------------------------
    if service == "login":
        user = data.get("user")
        if not user:
            rep.send_json({"service":"login","data":{
                "status": "erro",
                "description": "missing user",
                "timestamp": ts()
            }})
            continue

        users.setdefault(user, {})
        users[user]["online"] = True
        users[user]["last_seen"] = ts()
        persist_all()

        rep.send_json({"service":"login","data":{
            "status": "sucesso",
            "timestamp": ts()
        }})

    # --------------------------------------
    # LISTA DE USUÁRIOS
    # --------------------------------------
    elif service == "users":
        rep.send_json({
            "service": "users",
            "data": {
                "timestamp": ts(),
                "users": list(users.keys())
            }
        })

    # --------------------------------------
    # CRIAR CANAL
    # --------------------------------------
    elif service == "channel":
        ch = data.get("channel")
        if not ch:
            rep.send_json({"service":"channel","data":{
                "status": "erro",
                "description": "missing channel",
                "timestamp": ts()
            }})
            continue

        if ch in channels:
            rep.send_json({"service":"channel","data":{
                "status": "erro",
                "description": "canal já existe",
                "timestamp": ts()
            }})
        else:
            channels.append(ch)
            persist_all()
            rep.send_json({"service":"channel","data":{
                "status": "sucesso",
                "timestamp": ts()
            }})

    # --------------------------------------
    # LISTA DE CANAIS
    # --------------------------------------
    elif service == "channels":
        rep.send_json({
            "service": "channels",
            "data": {
                "timestamp": ts(),
                "channels": channels
            }
        })

    # --------------------------------------
    # PUBLICAÇÃO EM CANAL
    # --------------------------------------
    elif service == "publish":
        user = data.get("user")
        channel = data.get("channel")
        msg = data.get("message")

        if channel not in channels:
            rep.send_json({"service":"publish","data":{
                "status": "erro",
                "message":"canal inexistente",
                "timestamp": ts()
            }})
            continue

        payload = {
            "type": "channel_message",
            "user": user,
            "channel": channel,
            "message": msg,
            "timestamp": ts()
        }

        messages.append(payload)
        persist_all()

        pub.send_string(channel, zmq.SNDMORE)
        pub.send_json(payload)

        rep.send_json({"service":"publish","data":{
            "status":"OK",
            "timestamp": ts()
        }})

    # --------------------------------------
    # MENSAGEM PRIVADA
    # --------------------------------------
    elif service == "message":
        src = data.get("src")
        dst = data.get("dst")
        msg = data.get("message")

        payload = {
            "type": "private_message",
            "src": src,
            "dst": dst,
            "message": msg,
            "timestamp": ts()
        }

        messages.append(payload)

        if dst in users and users.get(dst, {}).get("online"):
            persist_all()
            pub.send_string(dst, zmq.SNDMORE)
            pub.send_json(payload)

            rep.send_json({"service":"message","data":{
                "status":"OK",
                "timestamp": ts()
            }})
        else:
            offline.append(payload)
            persist_all()
            rep.send_json({"service":"message","data":{
                "status":"erro",
                "message":"destinatario offline, mensagem armazenada",
                "timestamp": ts()
            }})

    # --------------------------------------
    # FETCH OFFLINE
    # --------------------------------------
    elif service == "fetch_offline":
        user = data.get("user")

        inbox = [m for m in offline if m["dst"] == user]
        offline = [m for m in offline if m["dst"] != user]

        save_json(OFFLINE_FILE, offline)

        rep.send_json({"service":"fetch_offline","data":{
            "messages": inbox,
            "timestamp": ts()
        }})

    else:
        rep.send_json({"service":"error","data":{
            "message":"unknown service",
            "timestamp": ts()
        }})
