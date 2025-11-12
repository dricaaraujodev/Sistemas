import zmq
import json
import os
from datetime import datetime
import time

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

# --- Endereços de comunicação ---
REQ_BIND = "tcp://0.0.0.0:5555"   # REQ/REP dos bots
PUB_CONNECT = "tcp://broker:5557" # PUB -> XSUB do broker

context = zmq.Context()
rep = context.socket(zmq.REP)
rep.bind(REQ_BIND)

pub = context.socket(zmq.PUB)
pub.connect(PUB_CONNECT)

print("🧠 Servidor iniciado — REQ/REP em 5555, PUB → broker:5557")

# Estado de usuários e canais
users = {}       # users[name] = {"online": True/False, "ts": "2025-11-12T14:00:00Z"}
channels = ["geral"]


def now_iso():
    return datetime.utcnow().isoformat()


def broadcast(channel, message):
    """Envia uma mensagem pública via PUB socket."""
    pub.send_string(f"{channel}|{message}")


while True:
    try:
        req_msg = rep.recv_json()
    except Exception as e:
        print(f"❌ Erro ao receber JSON: {e}")
        continue

    service = req_msg.get("service")
    data = req_msg.get("data", {})
    ts = now_iso()

    # =========================================================
    # LOGIN
    # =========================================================
    if service == "login":
        user = data.get("user")
        if not user:
            rep.send_json({
                "service": "login",
                "data": {"status": "ERRO", "message": "Usuário não informado", "timestamp": ts}
            })
            continue

        # Marca o usuário como online
        users[user] = {"online": True, "ts": ts}
        print(f"✅ LOGIN: {user}")

        # Envia broadcast de entrada usando prefixo [JOIN]
        broadcast("geral", f"[JOIN] {user} entrou no canal geral")

        rep.send_json({
            "service": "login",
            "data": {
                "status": "OK",
                "message": f"Login de {user} realizado com sucesso!",
                "timestamp": ts
            }
        })
        continue

    # =========================================================
    # LISTAR CANAIS
    # =========================================================
    if service == "channels":
        rep.send_json({
            "service": "channels",
            "data": {"channels": channels, "timestamp": ts}
        })
        continue

    # =========================================================
    # LISTAR USUÁRIOS
    # =========================================================
    if service == "users":
        rep.send_json({
            "service": "users",
            "data": {"users": list(users.keys()), "timestamp": ts}
        })
        continue

    # =========================================================
    # MENSAGEM PÚBLICA
    # =========================================================
    if service == "publish":
        user = data.get("user")
        channel = data.get("channel", "geral")
        message = data.get("message")

        if channel not in channels:
            rep.send_json({
                "service": "publish",
                "data": {"status": "ERRO", "message": f"Canal {channel} não existe", "timestamp": ts}
            })
            continue

        # Usa prefixo [PUB]
        payload = f"[PUB] {user} enviou ao canal {channel}: \"{message}\""
        print(f"📢 BROADCAST: {payload}")
        broadcast(channel, payload)

        rep.send_json({
            "service": "publish",
            "data": {"status": "OK", "timestamp": ts}
        })
        continue

    # =========================================================
    # MENSAGEM PRIVADA
    # =========================================================
    if service == "message":
        src = data.get("src")
        dst = data.get("dst")
        message = data.get("message")

        if not dst:
            rep.send_json({
                "service": "message",
                "data": {"status": "ERRO", "message": "Destinatário não informado", "timestamp": ts}
            })
            continue

        if users.get(dst, {}).get("online"):
            # Cria o payload no formato esperado pelo bot.js
            payload_privada = f"[PRV] {dst} recebeu mensagem privada de {src}: \"{message}\""

            # Confirma entrega ao remetente
            rep.send_json({
                "service": "message",
                "data": {"status": "DELIVERED", "timestamp": ts}
            })

            # Publica no tópico do destinatário
            pub.send_string(f"{dst}|{payload_privada}")
            print(f"🔒 ENTREGUE: {src} -> {dst}: \"{message}\"")
        else:
            print(f"❌ NÃO ENTREGUE (offline): {src} → {dst}: \"{message}\"")
            rep.send_json({
                "service": "message",
                "data": {
                    "status": "OFFLINE",
                    "message": f"{dst} está offline.",
                    "timestamp": ts
                }
            })
        continue

    # =========================================================
    # SERVIÇO DESCONHECIDO
    # =========================================================
    print(f"⚠️ Serviço desconhecido: {service}")
    rep.send_json({
        "service": "error",
        "data": {"status": "UNKNOWN_SERVICE", "timestamp": ts}
    })
