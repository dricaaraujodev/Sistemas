import zmq from "zeromq";

const BOT_NAMES = [
  "Alice",
  "Bob",
  "Carla",
  "David",
  "Eduarda",
  "Felipe",
  "Gabi",
  "Henrique",
];

const BOT_ID = parseInt(process.env.BOT_ID || "0");
const BOT_NAME = BOT_NAMES[BOT_ID % BOT_NAMES.length] || `bot_${BOT_ID}`;

const REQ_ADDR = "tcp://server:5555";
const SUB_ADDR = "tcp://broker:5558";

const req = new zmq.Request();
const sub = new zmq.Subscriber();

await req.connect(REQ_ADDR);
await sub.connect(SUB_ADDR);

sub.subscribe("geral");
sub.subscribe(BOT_NAME);

console.log(`🤖 ${BOT_NAME}: conectado e inscrito em 'geral' e '${BOT_NAME}'`);

// ============================================================
// LOGIN
// ============================================================
try {
  await req.send(JSON.stringify({
    service: "login",
    data: { user: BOT_NAME, timestamp: new Date().toISOString() }
  }));

  const [reply] = await req.receive();
  const response = JSON.parse(reply.toString());
  const { status, message, timestamp } = response.data;

  if (status === "OK") {
    console.log(`✅ Login de ${BOT_NAME}: ${message}`);
    console.log(`🕒 Servidor: ${timestamp}`);
  } else {
    console.log(`❌ Falha no login: ${message}`);
  }
} catch (err) {
  console.error("🚨 Erro no login:", err);
}

// ============================================================
// FUNÇÕES
// ============================================================
function parseTopicPayload(text) {
  const idx = text.indexOf("|");
  if (idx === -1) return { topic: null, payload: text };
  return { topic: text.slice(0, idx), payload: text.slice(idx + 1) };
}

async function sendPrivate(src, dst, message) {
  console.log(`📤 ${src} enviando mensagem privada para ${dst}: "${message}"`);
  await req.send(JSON.stringify({ service: "message", data: { src, dst, message } }));
  const [r] = await req.receive();
  const rep = JSON.parse(r.toString());
  const status = rep.data?.status;

  if (status === "DELIVERED") {
    console.log(`✅ ${src} → ${dst}: mensagem entregue com sucesso.`);
  } else if (status === "OFFLINE") {
    console.log(`❌ ${src} → ${dst}: usuário offline.`);
  } else {
    console.log(`⚠️ Resposta inesperada: ${r.toString()}`);
  }
}

async function publish(user, channel, message) {
  console.log(`💬 ${user} publicou no canal ${channel}: "${message}"`);
  await req.send(JSON.stringify({ service: "publish", data: { user, channel, message } }));
  await req.receive();
}

// ============================================================
// LOOP DE SUBSCRIÇÃO
// ============================================================
(async () => {
  for await (const [frame] of sub) {
    const { topic, payload } = parseTopicPayload(frame.toString());
    if (!topic) continue;

    const msg = payload.trim();

    if (msg.startsWith("[JOIN]")) {
      const m = msg.match(/\[JOIN\]\s*(.*?)\s+entrou no canal geral/);
      if (m && m[1] !== BOT_NAME) console.log(`🟢 ${m[1]} entrou no canal geral`);
      continue;
    }

    if (topic === BOT_NAME && msg.startsWith("[PRV]")) {
      const m = msg.match(/\[PRV\]\s*(.*?)\s+recebeu mensagem privada de\s+(.*?):\s*"(.*)"/);
      if (m) {
        const receiver = m[1];
        const sender = m[2];
        const message = m[3];
        if (receiver === BOT_NAME) {
          console.log(`💌 ${BOT_NAME} recebeu mensagem privada de ${sender}: "${message}"`);
          console.log(`📬 Confirmação: ${BOT_NAME} recebeu a mensagem de ${sender}.`);
        }
      }
      continue;
    }

    if (msg.startsWith("[PUB]")) {
      const m = msg.match(/\[PUB\]\s*(.*?)\s+enviou ao canal geral:\s*"(.*)"/);
      if (m) {
        console.log(`💬 ${BOT_NAME} recebeu no geral de ${m[1]}: "${m[2]}"`);
      }
      continue;
    }
  }
})();

// ============================================================
// AÇÕES DEMONSTRATIVAS
// ============================================================
if (BOT_NAME === "Alice") {
  setTimeout(async () => await publish("Alice", "geral", "Olá, tudo bem com todos?"), 1500);
  setTimeout(async () => await sendPrivate("Alice", "Bob", "Oi Bob, recebeu minha mensagem?"), 3500);
}

if (BOT_NAME === "Carla") {
  setTimeout(async () => await sendPrivate("Carla", "David", "Vamos conversar no privado!"), 4500);
}
