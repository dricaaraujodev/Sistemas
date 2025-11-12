import zmq from "zeromq";

const sock = new zmq.Request();

await sock.connect("tcp://server:5555");
console.log("🤖 Bot conectado ao servidor.");

function send(service, data) {
  const msg = {
    service,
    data: { ...data, timestamp: new Date().toISOString() },
  };
  sock.send(JSON.stringify(msg));
}

async function main() {
  send("login", { user: "bot_js" });
  let [reply] = await sock.receive();
  console.log("Login reply:", reply.toString());

  send("users", {});
  [reply] = await sock.receive();
  console.log("Users list:", reply.toString());
}

main();
