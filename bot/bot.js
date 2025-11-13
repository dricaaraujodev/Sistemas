// bot/bot.js
const zmq = require("zeromq");
const os = require("os");
const chalk = require("chalk");

const PROXY_HOST = process.env.PROXY_HOST || "proxy";
const SERVER_HOST = process.env.SERVER_HOST || "server";

const NAMES = [
  "Alice", "Bruno", "Carlos", "Diana", "Eduardo",
  "Fernanda", "Gabriel", "Helena", "Igor", "Júlia",
  "Kleber", "Larissa", "Marcos", "Natália", "Otávio",
  "Paula", "Ricardo", "Sara", "Tiago", "Vitória"
];

const SAMPLE_MESSAGES = [
  "ola, tudo bem?",
  "bom dia a todos!",
  "alguem free para testar?",
  "bom trabalho pessoal",
  "vou fechar o deploy agora",
  "boa ideia!",
  "posso ajudar com isso?",
  "rs rs interessante",
  "agendamos reunião?",
  "ok, entendido"
];

function now() {
  return new Date().toISOString().replace("T", " ").substring(0, 19);
}

function getBotName() {
  const host = os.hostname();
  const match = host.match(/(\d+)$/);
  let id = match ? parseInt(match[1]) - 1 : 0;
  return NAMES[id % NAMES.length];
}

function logInfo(text) {
  console.log(chalk.gray(now() + " – ") + text);
}
function logPublic(channel, user, message) {
  console.log(chalk.blue(`📢 [${String(channel).toUpperCase()}] ${user}: `) + chalk.white(`"${message}"`));
}
function logPrivate(src, dst, message) {
  console.log(chalk.magenta(`🔐 [Privado] ${src} → ${dst}: `) + chalk.white(`"${message}"`));
}
function logEvent(text) {
  console.log(chalk.green(text));
}
function safeChannelListFromResponse(rj) {
  // Accept many shapes to be tolerant with server implementations:
  // - rj.data.channels (array)
  // - rj.data.users (array used by some server versions)
  // - rj.channels or rj.users (top-level)
  // - rj.data.channels as object -> take keys
  if (!rj || typeof rj !== "object") return null;

  if (rj.data) {
    if (Array.isArray(rj.data.channels)) return rj.data.channels;
    if (Array.isArray(rj.data.users)) return rj.data.users;
    if (rj.data.channels && typeof rj.data.channels === "object") return Object.keys(rj.data.channels);
    if (rj.data.users && typeof rj.data.users === "object") return Object.keys(rj.data.users);
  }

  if (Array.isArray(rj.channels)) return rj.channels;
  if (Array.isArray(rj.users)) return rj.users;
  if (rj.channels && typeof rj.channels === "object") return Object.keys(rj.channels);
  if (rj.users && typeof rj.users === "object") return Object.keys(rj.users);

  return null;
}

(async () => {
  const name = getBotName();

  const sub = new zmq.Subscriber();
  const req = new zmq.Request();

  await sub.connect(`tcp://${PROXY_HOST}:5558`);
  await req.connect(`tcp://${SERVER_HOST}:5555`);

  // Subscribe to our private topic (our username) early so we don't miss messages
  sub.subscribe(name);

  // login (conforme enunciado: service = "login")
  await req.send(JSON.stringify({ service: "login", data: { user: name, timestamp: now() } }));
  let repBuf = await req.receive();
  let repJson;
  try {
    repJson = JSON.parse(repBuf.toString());
  } catch (e) {
    console.error(chalk.red("Resposta inválida do servidor ao logar:"), repBuf.toString());
    process.exit(1);
  }

  const loginStatus = repJson && repJson.data && repJson.data.status;
  if (!(loginStatus === "sucesso" || loginStatus === "OK" || loginStatus === "ok")) {
    console.error(chalk.red(`Falha no login: ${JSON.stringify(repJson)}`));
    process.exit(1);
  }
  logEvent(`${name} login realizado com sucesso – assinatura privada criada para: ${name}`);

  // request list of channels (service = "channels")
  await req.send(JSON.stringify({ service: "channels", data: { timestamp: now() } }));
  repBuf = await req.receive();
  let rj;
  try {
    rj = JSON.parse(repBuf.toString());
  } catch (e) {
    console.warn(chalk.red("Resposta inválida ao pedir canais, usando fallback."), repBuf.toString());
    rj = null;
  }

  let channels = safeChannelListFromResponse(rj);
  if (!channels || !channels.length) {
    console.warn(chalk.red("⚠️ WARNING: Server retornou formato inesperado para channels:"), rj);
    channels = ["geral", "dev", "random", "announcements"];
  }

  // deterministic channel selection
  let idx = NAMES.indexOf(name);
  let channel = channels[idx % channels.length];

  if (typeof channel !== "string") {
    console.error(chalk.red("❌ ERRO: canal inválido recebido do servidor:"), channels);
    process.exit(1);
  }

  sub.subscribe(channel);
  logEvent(`${name} entrou no canal ${channel}`);

  // attempt to fetch offline messages if server supports it (robust)
  try {
    await req.send(JSON.stringify({ service: "fetch_offline", data: { user: name, timestamp: now() } }));
    repBuf = await req.receive();
    let offlineResp;
    try {
      offlineResp = JSON.parse(repBuf.toString());
    } catch (e) {
      offlineResp = null;
    }
    const msgs = offlineResp && offlineResp.data && Array.isArray(offlineResp.data.messages) ? offlineResp.data.messages : [];
    if (msgs.length) {
      logInfo(`${name} recebeu ${msgs.length} mensagens offline`);
      msgs.forEach(m => logPrivate(m.src, name, m.message));
    }
  } catch (e) {
    // server may not implement fetch_offline — it's fine
    logInfo("fetch_offline não suportado ou falhou (ignorado).");
  }

  // listen for incoming messages (channel or private)
  (async () => {
    for await (const [topicBuf, msgBuf] of sub) {
      const topic = topicBuf.toString();
      let data;
      try { data = JSON.parse(msgBuf.toString()); } catch (e) { continue; }

      if (data.type === "channel_message" && topic === channel) {
        logPublic(channel, data.user, data.message);
        logInfo(`${name} recebeu mensagem pública de ${data.user}: "${data.message}"`);
      } else if (data.type === "private_message" && topic === name) {
        logPrivate(data.src, name, data.message);
      }
    }
  })();

  // public message interval: publish
  setInterval(async () => {
    const msg = SAMPLE_MESSAGES[Math.floor(Math.random() * SAMPLE_MESSAGES.length)];
    const body = {
      service: "publish",
      data: { user: name, channel: channel, message: msg, timestamp: now() }
    };
    try {
      await req.send(JSON.stringify(body));
      const rep = await req.receive();
      const r = JSON.parse(rep.toString());
      // server may reply with status "OK" or "erro"
      const ok = r && r.data && (r.data.status === "OK" || r.data.status === "sucesso" || r.data.status === "ok");
      if (!ok) {
        console.warn(chalk.yellow(`Publish respondeu com erro: ${JSON.stringify(r)}`));
      }
      logPublic(channel, name, msg);
    } catch (e) {
      logInfo(`Erro ao publicar: ${e.message}`);
    }
  }, 6000 + Math.floor(Math.random() * 6000));

  // private message interval
  setInterval(async () => {
    let other;
    do {
      other = NAMES[Math.floor(Math.random() * NAMES.length)];
    } while (other === name);

    const pm = SAMPLE_MESSAGES[Math.floor(Math.random() * SAMPLE_MESSAGES.length)];
    const body = {
      service: "message",
      data: { src: name, dst: other, message: pm, timestamp: now() }
    };
    try {
      await req.send(JSON.stringify(body));
      const response = await req.receive();
      const r = JSON.parse(response.toString());
      const ok = r && r.data && (r.data.status === "OK" || r.data.status === "sucesso" || r.data.status === "ok");
      if (ok) {
        logPrivate(name, other, pm);
      } else {
        // server returns description for errors per spec
        const desc = r && r.data && (r.data.description || r.data.message) ? (r.data.description || r.data.message) : "erro/desconhecido";
        logInfo(`${name} enviou mensagem privada para ${other}: "${pm}" — ${desc}`);
      }
    } catch (e) {
      logInfo(`Erro ao enviar mensagem privada: ${e.message}`);
    }
  }, 10000 + Math.floor(Math.random() * 15000));
})();
