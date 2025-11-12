# broker.py
import zmq

context = zmq.Context()

# XSUB recebe publicações do servidor
frontend = context.socket(zmq.XSUB)
frontend.bind("tcp://*:5557")  # porta que o server PUB conecta

# XPUB envia mensagens para os clientes SUB
backend = context.socket(zmq.XPUB)
backend.bind("tcp://*:5558")  # porta que os clients SUB conectam

print("📡 Broker PUB/SUB ativo: 5557 (server) ↔ 5558 (clients)")

# Proxy simples para rotear mensagens
zmq.proxy(frontend, backend)
