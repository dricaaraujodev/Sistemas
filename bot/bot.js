// bot.js
import zmq from "zeromq";

// ============================================================
// NOMES PRÉ-DEFINIDOS DOS BOTS
// ============================================================
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

// ============================================================
// CONFIGURAÇÃO DE ENDEREÇOS ZMQ
// ============================================================
const REQ_ADDR = "tcp://server:5555"; // REQ/REP → server.py
const SUB_ADDR = "tcp://broker:5558"; // XPUB → broker

const req = new zmq.Request();
const sub = new zmq.Subscriber();

await req.connect(REQ_ADDR);
await sub.connect(SUB_ADDR);

// Subscreve nos tópicos necessários
sub.subscribe("geral");
sub.subscribe(BOT_NAME);

console.log(`🤖 ${BOT_NAME} (ID: ${BOT_ID}): conectado, subscrito em 'geral' e '${BOT_NAME}'`);

// ============================================================
// LOGIN
// ============================================================
const ts = new Date().toISOString();
await req.send(JSON.stringify({ service: "login", data: { user: BOT_NAME, timestamp: ts } }));
const [loginReply] = await req.receive();

try {
  const reply = JSON.parse(loginReply.toString());
  const status = reply.data?.status;
  if (status === "OK" || status === "SUCCESS") {
    console.log(`✅ Login de ${BOT_NAME}: SUCESSO!`);
  } else {
    console.log(`❌ Login de ${BOT_NAME}: FALHA → ${loginReply.toString()}`);
  }
} catch (e) {
  console.log(`⚠️ Erro ao processar resposta de login: ${loginReply.toString()}`);
}

// ============================================================
// FUNÇÕES AUXILIARES
// ============================================================

// Helper simples para parse "topic|payload"
function parseTopicPayload(text) {
  const idx = text.indexOf("|");
  if (idx === -1) return { topic: null, payload: text };
  return { topic: text.slice(0, idx), payload: text.slice(idx + 1) };
}

// Envio de mensagem privada
async function sendPrivate(src, dst, message) {
  await req.send(JSON.stringify({ service: "message", data: { src, dst, message } }));
  const [r] = await req.receive();
  try {
    const rep = JSON.parse(r.toString());
    const status = rep.data?.status;

    if (status === "DELIVERED" || status === "SUCCESS" || status === "OK") {
      console.log(`${src} enviou mensagem privada para ${dst}: "${message}" (ENTREGUE)`);
    } else if (status === "OFFLINE") {
      console.log(`❌ ${src} tentou enviar mensagem privada para ${dst}: "${message}" (NÃO ENTREGUE: USUÁRIO OFFLINE)`);
    } else {
      console.log(`🔒 ${src} tentou enviar mensagem privada para ${dst}: "${message}" (RESPOSTA: ${r.toString()})`);
    }
  } catch {
    console.log(`⚠️ Erro ao processar resposta do servidor para mensagem privada`);
  }
}

// Publicar em canal (ordem visual corrigida)
async function publish(user, channel, message) {
  console.log(`${user} publicou no canal ${channel}: 💬 "${message}"`);
  await req.send(JSON.stringify({ service: "publish", data: { user, channel, message } }));
  await req.receive(); // apenas para consumir resposta
}

// ============================================================
// ============================================================
// LOOP DE SUBSCRIÇÃO (CORRIGIDO)
// ============================================================
(async () => {
  for await (const [frame] of sub) {
    const text = frame.toString();
    const { topic, payload } = parseTopicPayload(text);
    if (!topic) continue;

    const pl = payload.trim();
    
    // ANÚNCIO DE ENTRADA [JOIN] (Substitui 🟢)
    if (pl.startsWith("[JOIN]") && pl.includes("entrou no canal geral")) {
      const match = pl.match(/\[JOIN\]\s*(.*?)\s+entrou no canal geral/);
      if (match) {
        const joinedUser = match[1];
        if (joinedUser !== BOT_NAME) {
          console.log(`🟢 ${joinedUser} entrou no canal geral`); // Mantém o emoji no log se preferir
        }
      }
      continue;
    }

    // MENSAGEM PRIVADA [PRV] (Substitui 💌)
    if (topic === BOT_NAME && pl.startsWith("[PRV]")) {
      // Regex espera: [PRV] Bob recebeu mensagem privada de Alice: "Oi Bob..."
      const match = pl.match(/\[PRV\]\s*(.*?)\s+recebeu mensagem privada de\s+(.*?):\s*"(.*)"/);
      if (match) {
        const receiver = match[1];
        const sender = match[2];
        const message = match[3];
        if (receiver === BOT_NAME) {
          console.log(`💌 ${BOT_NAME} recebeu mensagem privada de ${sender}: "${message}"`);
        }
      } else {
        console.log(`💌 ${BOT_NAME} recebeu (privado, não formatado): ${pl}`);
      }
      continue;
    }

    // MENSAGEM PÚBLICA [PUB] (Substitui 💬)
    if (pl.startsWith("[PUB]")) {
      // Regex espera: [PUB] Alice enviou ao canal geral: "Ola, tudo bem com todos no canal?"
      const m = pl.match(/\[PUB\]\s*(.*?)\s+enviou ao canal geral:\s*"(.*)"/);
      if (m) {
        const sender = m[1];
        const message = m[2];
        console.log(`💬 ${BOT_NAME} recebeu de geral (de ${sender}): "${message}"`);
      } else {
        console.log(`📩 ${BOT_NAME} recebeu (PUB não formatada): ${pl}`);
      }
      continue;
    }

    // Qualquer outra coisa
    console.log(`📩 ${BOT_NAME} recebeu: ${pl}`);
  } // <-- fecha o for await
})(); // <-- fecha a função assíncrona

// ============================================================
// AÇÕES DE DEMONSTRAÇÃO
// ============================================================
if (BOT_NAME === "Alice") {
  setTimeout(async () => {
    await publish("Alice", "geral", "Ola, tudo bem com todos no canal?");
  }, 1500);

  setTimeout(async () => {
    await sendPrivate("Alice", "Bob", "Oi Bob, você recebeu minha mensagem pública?");
  }, 3000);
}

if (BOT_NAME === "Carla") {
  setTimeout(async () => {
    await sendPrivate("Carla", "David", "Vamos conversar no privado!");
  }, 4500);
}
