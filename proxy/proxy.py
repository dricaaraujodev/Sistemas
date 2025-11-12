# Proxy.py
import zmq

context = zmq.Context()

# Recebe mensagens do broker (XSUB)
frontend = context.socket(zmq.XSUB)
frontend.bind("tcp://*:5557")  # porta XSUB

# Envia mensagens para os clientes (XPUB)
backend = context.socket(zmq.XPUB)
backend.bind("tcp://*:5558")   # porta XPUB

print("📡 Proxy PUB/SUB ativo: 5557 (broker) ↔ 5558 (clientes)")

# Roteia mensagens entre frontend e backend
zmq.proxy(frontend, backend)
