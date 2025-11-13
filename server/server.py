import zmq
import json
import os
from datetime import datetime, timedelta

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

REQ_BIND = "tcp://0.0.0.0:5555"
PUB_CONNECT = "tcp://broker:5557"

context = zmq.Context()
rep = context.socket(zmq.REP)
rep.bind(REQ_BIND)

pub = context.socket(zmq.PUB)
pub.connect(PUB_CONNECT)

print("🧠 Servidor iniciado — REQ/REP em 5555, PUB → broker:5557")

# =========================================================
# ESTRUTURAS DE DADOS
# =========================================================
users = {}  # { "Ana": {"online": True, "ts": "..."} }
channels = ["geral"]
offline_messages = {}  # { "Ana": [("Bruno", "Oi", timestamp), ...] }

# =========================================================
# FUNÇÕES AUXILIARES
# =========================================================
def now_iso():
    return datetime.utcnow().isoformat()

def broadcast(channel, message):
    """Envia mensagem pública a todos os inscritos no canal."""
    pub.send_string(f"{channel}|{message}")

def store_offline_message(dst, src, message):
    """Armazena mensagens destinadas a usuários offline."""
    if dst not in offline_messages:
        offline_messages[dst] = []
    offline_messages[dst].append({
        "src": src,
        "message": message,
        "timestamp": now_iso()
    })

def deliver_offline_messages(user):
    """Entrega mensagens armazenadas para o usuário quando ele faz login."""
    msgs = offline_messages.pop(user, [])
    for m in msgs:
        payload = f"[OFFLINE MSG] {user} recebeu (de {m['src']}): \"{m['message']}\""
        pub.send_string(f"{user}|{payload}")
        print(f"📨 Entregue mensagem offline → {user}: \"{m['message']}\"")

# =========================================================
# LOOP PRINCIPAL
# =========================================================
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

        if not user or not user.strip():
            error_msg = "Usuário não informado ou inválido"
            print(f"❌ LOGIN FALHOU: {error_msg}")
            rep.send_json({
                "service": "login",
                "data": {"status": "ERRO", "message": error_msg, "timestamp": ts}
            })
            continue

        users[user] = {"online": True, "ts": ts}
        print(f"✅ LOGIN: {user} entrou às {ts}")

        broadcast("geral", f"[JOIN] {user} entrou no canal geral")

        # Entregar mensagens offline, se existirem
        deliver_offline_messages(user)

        rep.send_json({
            "service": "login",
            "data": {"status": "OK", "message": f"Login de {user} realizado com sucesso!", "timestamp": ts}
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

        payload = f"[PUB] {user}: \"{message}\""
        broadcast(channel, payload)
        print(f"📢 {user} → {channel}: {message}")

        rep.send_json({
            "service": "publish",
            "data": {"status": "OK", "message": "Mensagem pública enviada", "timestamp": ts}
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
            payload = f"[PRV] {src} → {dst}: \"{message}\""
            pub.send_string(f"{dst}|{payload}")
            print(f"🔒 PRIVADA ENTREGUE: {src} → {dst}: {message}")

            rep.send_json({
                "service": "message",
                "data": {"status": "DELIVERED", "message": f"Mensagem enviada a {dst}", "timestamp": ts}
            })
        else:
            print(f"💤 {dst} está offline — armazenando mensagem de {src}")
            store_offline_message(dst, src, message)
            rep.send_json({
                "service": "message",
                "data": {"status": "STORED", "message": f"{dst} offline — mensagem armazenada", "timestamp": ts}
            })
        continue

    # =========================================================
    # LOGOUT
    # =========================================================
    if service == "logout":
        user = data.get("user")
        if user in users:
            users[user]["online"] = False
            print(f"👋 LOGOUT: {user} saiu.")
            broadcast("geral", f"[LEFT] {user} saiu do chat.")
        rep.send_json({
            "service": "logout",
            "data": {"status": "OK", "timestamp": ts}
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
