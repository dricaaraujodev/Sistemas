import zmq

context = zmq.Context()

rep = context.socket(zmq.REP)
rep.bind("tcp://*:5555")

while True:
    rep.send_string("broker-ok")
