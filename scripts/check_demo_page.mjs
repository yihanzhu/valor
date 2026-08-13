/* Drive website/demo.html's script in a fake DOM and assert the chat actually
 * answers. Run: node scripts/check_demo_page.mjs   (from the repo root)
 *
 * This exists because the page shipped broken once: a top-level
 * `function scrollTo(...)` in a classic script overwrote window.scrollTo, so the
 * call recursed and threw before any reply was rendered — user messages appeared,
 * replies never did. A renderer unit check missed it (wrapping the script in a
 * function removes the global shadowing), so this harness evaluates the script the
 * way a browser does and asserts a reply reaches the DOM.
 */
import { readFileSync } from "node:fs";
import vm from "node:vm";

const PAGE = process.argv[2] || "website/demo.html";
const TRANSCRIPTS = "website/demo/transcripts.json";

let failures = 0;
const fail = (msg) => { console.log("  FAIL " + msg); failures += 1; };
const ok = (msg) => console.log("  ok   " + msg);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const html = readFileSync(PAGE, "utf8");
const scriptMatch = html.match(/<script>([\s\S]*?)<\/script>/);
if (!scriptMatch) { console.log("no <script> found in " + PAGE); process.exit(1); }
const source = scriptMatch[1];

/* The script must not leak anything to the global object. */
if (!/^\s*\/\*[\s\S]*?\*\/\s*\(function\s*\(/.test(source) && !/^\s*\(function\s*\(/.test(source)) {
  fail("the page script is not wrapped in an IIFE — top-level declarations would " +
       "land on window and can shadow built-ins like scrollTo");
} else {
  ok("page script is scoped in an IIFE");
}

/* ---- minimal DOM ---- */
function makeEl(tag = "div") {
  const el = {
    tagName: String(tag).toUpperCase(),
    children: [],
    handlers: {},
    style: {},
    dataset: {},
    className: "",
    _html: "",
    _text: "",
    disabled: false,
    value: "",
    placeholder: "",
    title: "",
    type: "",
    classList: { add() {}, remove() {} },
    get innerHTML() { return el._html; },
    set innerHTML(v) { el._html = String(v); el.children = []; },
    get textContent() { return el._text; },
    set textContent(v) { el._text = String(v); },
    appendChild(child) { el.children.push(child); return child; },
    append(child) { el.children.push(child); return child; },
    addEventListener(type, fn) { (el.handlers[type] = el.handlers[type] || []).push(fn); },
    removeEventListener() {},
    setAttribute() {},
    focus() {},
    remove() {},
    scrollIntoView() {},
    getBoundingClientRect() { return { top: 0, bottom: 0, left: 0, right: 0 }; },
    querySelector(sel) {
      const want = String(sel).replace(/^\./, "").toUpperCase();
      return el.children.find((c) =>
        c.tagName === want || (c.className || "").split(/\s+/).includes(String(sel).replace(/^\./, ""))
      ) || makeEl("button");
    },
    querySelectorAll() { return []; },
    /* A handler that throws is the failure mode this harness exists to catch —
       report it rather than crashing the run. */
    fire(type) {
      (el.handlers[type] || []).forEach((fn) => {
        try {
          fn({ preventDefault() {} });
        } catch (err) {
          fail(`a ${type} handler threw: ${err.message}`);
        }
      });
    },
    /* Serialize enough structure for assertions: the element's own tag and class
       plus its markup and children. */
    dump() {
      const tag = el.tagName.toLowerCase();
      const cls = el.className ? ` class="${el.className}"` : "";
      const inner = el._html + el.children.map((c) => c.dump()).join("");
      return `<${tag}${cls}>${inner}</${tag}>`;
    },
    texts() {
      const own = el._html.replace(/<[^>]+>/g, " ");
      return (own + " " + el.children.map((c) => c.texts()).join(" ")).replace(/\s+/g, " ");
    },
  };
  return el;
}

const ids = {};
for (const id of ["year", "thread", "chips", "form", "input", "restart"]) ids[id] = makeEl();

/* In a browser `window === globalThis`, so a top-level `function scrollTo(...)`
   in a classic script *replaces* window.scrollTo. Model that faithfully: one
   object serving as both the global and `window`. */
const sandbox = {
  console,
  document: {
    getElementById: (id) => ids[id] || makeEl(),
    createElement: (tag) => makeEl(tag),
    querySelector: () => makeEl(),
    querySelectorAll: () => [],
  },
  navigator: { clipboard: { writeText: () => Promise.resolve() } },
  matchMedia: () => ({ matches: false }),
  setTimeout, clearTimeout, Promise, Error, JSON, Math, Date, String, Number, Array, Object, RegExp,
  scrollY: 0,
  scrollTo(...args) { sandbox.__scrolledWith = args; },
  fetch: () => Promise.resolve({
    ok: true,
    json: () => Promise.resolve(JSON.parse(readFileSync(TRANSCRIPTS, "utf8"))),
  }),
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
const baseline = {};
for (const name of ["scrollTo", "fetch", "matchMedia", "setTimeout", "clearTimeout", "document"]) {
  baseline[name] = sandbox[name];
}

vm.createContext(sandbox);
try {
  vm.runInContext(source, sandbox, { filename: "demo.html<script>" });
} catch (err) {
  fail("the script threw while loading: " + err.message);
}

/* Anything the script declared at top level landed on the global, i.e. on window. */
for (const name of Object.keys(baseline)) {
  if (sandbox[name] !== baseline[name]) {
    fail(`the script replaced window.${name} — a top-level declaration is shadowing a built-in`);
  }
}

const thread = ids.thread;
const chips = ids.chips;
const input = ids.input;

await sleep(20); // let the fetch promise chain settle

if (!thread.texts().includes("Recorded session")) fail("no opening note rendered");
else ok("opening note rendered");

if (!chips.children.length) fail("no suggestion chips rendered");
else ok(`${chips.children.length} suggestion chips offered`);

async function clickChip(index) {
  const chip = chips.children[index];
  if (!chip) { fail(`no chip at index ${index}`); return null; }
  const phrase = chip.textContent;
  chip.fire("click");
  await sleep(300);          // past the "working…" delay
  thread.fire("click");      // finish the stream immediately
  await sleep(20);
  return phrase;
}

/* Turn 1 — a suggestion. */
const first = await clickChip(0);
if (first) {
  const rendered = thread.dump();
  if (!rendered.includes(">You<")) fail("the user message did not render");
  if (!/chat-out/.test(rendered)) fail("no agent message container rendered");
  const agentText = thread.texts();
  if (agentText.includes("working…")) fail("the reply never replaced the working indicator");
  if (agentText.length < 400) fail(`the reply looks empty (${agentText.length} chars of text)`);
  else ok(`replied to "${first}" (${agentText.length} chars rendered)`);
  if (!/<p|<ul|<pre|<h4/.test(rendered)) fail("the reply rendered no formatted blocks");
  else ok("reply contains formatted blocks");
}

/* Turn 2 — a follow-up suggestion, which must differ from turn 1. */
const beforeSecond = thread.texts().length;
const second = await clickChip(0);
if (second) {
  const grew = thread.texts().length - beforeSecond;
  if (grew < 300) fail(`the second reply added almost nothing (${grew} chars)`);
  else ok(`follow-up "${second}" replied and the thread accumulated (+${grew} chars)`);
}

/* Turn 3 — typed input that matches. */
input.value = "wrap up";
ids.form.fire("submit");
await sleep(300);
thread.fire("click");
await sleep(20);
if (!thread.texts().includes("Wrap-up")) fail("typing 'wrap up' did not reach the wrap-up transcript");
else ok("typed input matched a transcript");

/* Turn 4 — typed input with no recording. */
input.value = "what is the airspeed velocity of an unladen swallow";
ids.form.fire("submit");
await sleep(60);
if (!thread.texts().includes("only have the replies that were captured")) {
  fail("unrecorded input did not get the honest fallback");
} else {
  ok("unrecorded input answered honestly");
}

/* Restart clears the thread back to the opening state. */
ids.restart.fire("click");
await sleep(20);
if (thread.children.length > 1 || thread.texts().includes("Wrap-up")) fail("restart did not clear the thread");
else ok("restart clears the session");

console.log(failures ? `\n${failures} FAILURE(S) in ${PAGE}` : `\n${PAGE}: chat answers correctly`);
process.exit(failures ? 1 : 0);
