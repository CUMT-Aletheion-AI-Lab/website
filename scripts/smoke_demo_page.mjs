import { readFileSync, writeFileSync } from "node:fs";
import { pathToFileURL, fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const SITE = join(dirname(fileURLToPath(import.meta.url)), "..");
const html = readFileSync(join(SITE, "flued-demo.html"), "utf-8");
const scripts = [...html.matchAll(/<script type="module">([\s\S]*?)<\/script>/g)];
if (scripts.length !== 1) throw new Error(`expected 1 inline module, got ${scripts.length}`);
const src = scripts[0][1];
writeFileSync(join(SITE, "scripts", "_demo_inline.tmp.mjs"), src);

const fixture = JSON.parse(readFileSync(join(SITE, "public", "flued-demo-sample.json"), "utf-8"));

const handlers = {};
const stubs = new Map();
const makeStub = (sel) => ({
  sel,
  innerHTML: "",
  textContent: "",
  disabled: false,
  hidden: true,
  value: "",
  dataset: {},
  addEventListener: (ev, fn) => { handlers[sel + "::" + ev] = fn; },
  scrollIntoView: () => {},
  focus: () => {},
});
const getStub = (sel) => { if (!stubs.has(sel)) stubs.set(sel, makeStub(sel)); return stubs.get(sel); };

globalThis.document = {
  querySelector: getStub,
  querySelectorAll: () => [],
  getElementById: (id) => getStub("#" + id),
};
globalThis.location = { search: "" };
globalThis.fetch = async (url) => {
  if (String(url).startsWith("http://127.0.0.1:8722")) throw new Error("connect ECONNREFUSED");
  if (String(url) === "/flued-demo-sample.json") return { ok: true, json: async () => fixture };
  throw new Error("unexpected fetch " + url);
};

await import(pathToFileURL(join(SITE, "scripts", "_demo_inline.tmp.mjs")).href);
await new Promise((r) => setTimeout(r, 50));

const assert = (cond, msg) => { if (!cond) throw new Error("ASSERT: " + msg); console.log("ok -", msg); };

assert(getStub("[data-offline-badge]").hidden === false, "offline badge shown after health unreachable");
assert(getStub("[data-run-button]").disabled === false, "run button enabled in offline mode");

getStub("[data-input-text]").value = fixture.input.text;
await handlers["[data-run-button]::click"]();
await new Promise((r) => setTimeout(r, 50));

const seg = getStub("[data-segments]").innerHTML;
assert((seg.match(/demo-model-card/g) || []).length === 5, "5 segment model cards rendered");
assert(seg.includes("13 chunks") && seg.includes("25 chunks") && seg.includes("192 chunks"), "chunk counts rendered (13 / 25 / 192)");
assert(seg.includes("R4 边界优化臂") && seg.includes("自选粒度"), "R4 arm tag + granularity note rendered");
assert((seg.match(/demo-score-chart/g) || []).length === 5, "5 boundary score charts rendered");
assert(seg.includes("demo-seg-mark"), "segment boundary markers present");

const masked = getStub("[data-masked-text]").innerHTML;
assert(masked.includes("demo-mask-char"), "masked positions highlighted");
assert(masked.includes("31 个字节") || masked.includes("31"), "masked count label rendered");

const comp = getStub("[data-completion]").innerHTML;
assert((comp.match(/demo-model-card/g) || []).length === 5, "5 completion model cards rendered");
assert(comp.includes("3.2%") && comp.includes("76.7%"), "masked_acc values rendered (v36 3.2% / AR 76.7%)");
assert(comp.includes("任务一") && comp.includes("任务二"), "v3.6 two-task extra metrics rendered");
assert((comp.match(/任务一/g) || []).length === 2, "two-task metrics shown for both S0 and R4 arms");
assert((comp.match(/demo-pred /g) || []).length > 100, "prediction chips rendered");
assert(comp.includes("is-ok") && comp.includes("is-bad"), "correct/wrong chips colored");

const timing = getStub("[data-timing]").innerHTML;
assert(timing.includes("582.5 ms") && timing.includes("151.0 ms"), "per-model forward timing rendered");
assert(timing.includes("1.59 s"), "e2e total timing rendered in seconds (CPU scale)");
assert(timing.includes("CPU 推理"), "CPU device label rendered");
assert((timing.match(/demo-timing-bar/g) || []).length === 5, "5 timing bars rendered");
assert(timing.includes("5 个模型串行"), "e2e label counts 5 models");

console.log("\nall render smoke assertions passed");
process.exit(0);
