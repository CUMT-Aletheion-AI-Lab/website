// CDP screenshot helper: drives headless Edge via the DevTools protocol.
// Usage: node scripts/cdp_shot.mjs <url> <out.png> [scrollSelector] [width] [height] [settleMs] [evalJs]
// Requires no extra deps (Node >= 22 built-in WebSocket + fetch).

import { spawn } from "node:child_process";
import { writeFileSync } from "node:fs";

const [url, out, selector = "", width = "1600", height = "1200", settleMs = "2500", evalJs = ""] = process.argv.slice(2);
if (!url || !out) {
  console.error("usage: node scripts/cdp_shot.mjs <url> <out.png> [scrollSelector] [width] [height] [settleMs]");
  process.exit(1);
}

const EDGE = "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe";
const PORT = 9333;

const edge = spawn(EDGE, [
  "--headless=new",
  "--disable-gpu",
  "--hide-scrollbars",
  "--force-prefers-reduced-motion",
  `--remote-debugging-port=${PORT}`,
  `--window-size=${width},${height}`,
  "--user-data-dir=" + process.env.TEMP + "\\edge-cdp-shot",
  "about:blank",
], { stdio: "ignore" });

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function getTarget() {
  for (let i = 0; i < 40; i++) {
    try {
      const res = await fetch(`http://127.0.0.1:${PORT}/json`);
      const list = await res.json();
      const page = list.find((t) => t.type === "page");
      if (page) return page;
    } catch {}
    await sleep(250);
  }
  throw new Error("edge devtools endpoint not reachable");
}

let id = 0;
const pending = new Map();
let ws;

function send(method, params = {}) {
  return new Promise((resolve, reject) => {
    const msgId = ++id;
    pending.set(msgId, { resolve, reject });
    ws.send(JSON.stringify({ id: msgId, method, params }));
  });
}

async function main() {
  const target = await getTarget();
  ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((r) => (ws.onopen = r));
  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    if (msg.id && pending.has(msg.id)) {
      const { resolve, reject } = pending.get(msg.id);
      pending.delete(msg.id);
      msg.error ? reject(new Error(msg.error.message)) : resolve(msg.result);
    }
  };

  await send("Page.enable");
  await send("Emulation.setDeviceMetricsOverride", {
    width: Number(width), height: Number(height), deviceScaleFactor: 1, mobile: false,
  });
  await send("Page.navigate", { url });
  await sleep(Number(settleMs));

  if (evalJs) {
    await send("Runtime.evaluate", { expression: evalJs });
    await sleep(900);
  }

  if (selector) {
    await send("Runtime.evaluate", {
      expression: `document.querySelector(${JSON.stringify(selector)})?.scrollIntoView({block:"start",behavior:"auto"})`,
    });
    await sleep(700);
  }

  const shot = await send("Page.captureScreenshot", { format: "png" });
  writeFileSync(out, Buffer.from(shot.data, "base64"));
  console.log("written:", out);
}

main()
  .catch((err) => { console.error(err.message); process.exitCode = 1; })
  .finally(() => { try { ws?.close(); } catch {} edge.kill(); });
