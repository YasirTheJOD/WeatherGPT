#!/usr/bin/env node
/**
 * verify_pwa.mjs — check what the deployed PWA actually renders, in a real browser.
 *
 * Why this exists: Flutter web paints into a canvas, so `curl` proves the API and
 * nothing about the UI. This boots the app in headless Chrome, drives it like a user
 * (real mouse events), and reads the rendered text out of Flutter's accessibility
 * tree — then asserts the screen agrees with the payload it was given. It is the only
 * check that can catch UI/data drift such as a label claiming a window the number
 * does not have.
 *
 * It gates, like `demo_smoke`: every check prints PASS/FAIL and any failure exits
 * non-zero, so it can run after a deploy or in the pre-demo checklist.
 *
 * Requirements: Node 22+ (built-in fetch + WebSocket — no npm install) and Chrome.
 * Override the browser with CHROME_PATH if it is somewhere unusual.
 *
 * Usage:
 *   node scripts/verify_pwa.mjs https://weathergpt-7vnu.onrender.com
 *   node scripts/verify_pwa.mjs http://localhost:8000 --location Mumbai
 *
 * Note: `--location` must be one of the app's quick-pick chips (Kolkata, Mumbai,
 * Delhi, Bengaluru) — those are the deterministic, localized-but-stable entry point.
 */

import { spawn } from 'node:child_process';
import { existsSync, mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { setTimeout as sleep } from 'node:timers/promises';

// ---------------------------------------------------------------- arguments

const argv = process.argv.slice(2);
let baseUrl = 'http://localhost:8000';
let location = 'Kolkata';
for (let i = 0; i < argv.length; i += 1) {
  if (argv[i] === '--location') location = argv[++i];
  else if (argv[i] === '--help' || argv[i] === '-h') {
    console.log('usage: node scripts/verify_pwa.mjs [base-url] [--location Kolkata]');
    process.exit(0);
  } else if (!argv[i].startsWith('--')) baseUrl = argv[i];
}
baseUrl = baseUrl.replace(/\/+$/, '');
const origin = new URL(baseUrl).origin;
const cdpPort = Number(process.env.CDP_PORT || 9333);

const CHROME_CANDIDATES = [
  process.env.CHROME_PATH,
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/usr/bin/google-chrome',
  '/usr/bin/chromium',
  '/usr/bin/chromium-browser',
].filter(Boolean);
const chromePath = CHROME_CANDIDATES.find((candidate) => existsSync(candidate));

if (!chromePath) {
  console.error('No Chrome found. Set CHROME_PATH to the browser binary.');
  process.exit(2);
}

/** The app's labels, mirrored from current_conditions_card.dart — the check is that
 *  the rendered label matches `rainfall_basis`, so a forecast value can never be
 *  shown as an observed 24h total. */
const RAINFALL_LABEL = {
  observed_24h: 'Rain (24h)',
  forecast_24h: 'Rain (next 24h)',
  instant: 'Rain (now)',
};

// ------------------------------------------------------------------- harness

const results = [];
const check = (name, ok, detail = '') => results.push({ ok: Boolean(ok), name, detail });
const warn = (name, detail) => results.push({ ok: true, warn: true, name, detail });

const profile = mkdtempSync(join(tmpdir(), 'weathergpt-pwa-'));
const chrome = spawn(
  chromePath,
  [
    '--headless=new',
    `--remote-debugging-port=${cdpPort}`,
    `--user-data-dir=${profile}`,
    '--no-first-run',
    '--no-default-browser-check',
    '--disable-extensions',
    '--disable-gpu',
    '--no-sandbox',
    'about:blank',
  ],
  { stdio: 'ignore' },
);

let ws = null;
let browserWsUrl = null;

/** Close the *browser*, not just the launcher.
 *
 * `chrome.kill()` only stops the parent process; the renderer/GPU children survive,
 * keep the temp profile locked, and leave a stray chrome.exe behind. `Browser.close`
 * over the browser-level CDP endpoint tears down the whole tree. */
async function shutdownBrowser() {
  if (!browserWsUrl) return;
  try {
    const socket = new WebSocket(browserWsUrl);
    await new Promise((resolve, reject) => {
      socket.addEventListener('open', resolve, { once: true });
      socket.addEventListener('error', reject, { once: true });
      setTimeout(() => reject(new Error('browser socket timeout')), 3000);
    });
    socket.send(JSON.stringify({ id: 1, method: 'Browser.close' }));
    await sleep(800);
    socket.close();
  } catch {
    /* fall back to killing the process below */
  }
}

const cleanup = async () => {
  try { ws?.close(); } catch {}
  await shutdownBrowser();
  try { if (!chrome.killed) chrome.kill(); } catch {}

  // Even after a clean shutdown Chrome can hold the profile for a moment, so retry
  // instead of silently leaking a temp directory on every run.
  for (let i = 0; i < 12; i += 1) {
    try {
      rmSync(profile, { recursive: true, force: true });
      return;
    } catch {
      await sleep(300);
    }
  }
  console.error(`warning: could not remove the browser profile at ${profile}`);
};

async function connect() {
  let targets = null;
  for (let i = 0; i < 80; i += 1) {
    try {
      targets = await (await fetch(`http://127.0.0.1:${cdpPort}/json/list`)).json();
      break;
    } catch {
      await sleep(250);
    }
  }
  if (!targets) throw new Error('Chrome DevTools endpoint never came up');

  // The browser-level endpoint is needed to shut the whole browser down in cleanup.
  try {
    const version = await (await fetch(`http://127.0.0.1:${cdpPort}/json/version`)).json();
    browserWsUrl = version.webSocketDebuggerUrl ?? null;
  } catch {
    browserWsUrl = null;
  }

  const page = targets.find((t) => t.type === 'page');
  ws = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    ws.addEventListener('open', resolve, { once: true });
    ws.addEventListener('error', reject, { once: true });
  });

  let seq = 0;
  const pending = new Map();
  const exceptions = [];
  const requests = new Map();

  ws.addEventListener('message', (event) => {
    const message = JSON.parse(event.data);
    if (message.id && pending.has(message.id)) {
      pending.get(message.id)(message);
      pending.delete(message.id);
      return;
    }
    if (message.method === 'Runtime.exceptionThrown') {
      const d = message.params.exceptionDetails;
      exceptions.push(d?.exception?.description || d?.text || 'unknown exception');
    }
    if (message.method === 'Network.requestWillBeSent') {
      requests.set(message.params.requestId, {
        id: message.params.requestId,
        url: message.params.request.url,
        status: 'pending',
      });
    }
    if (message.method === 'Network.responseReceived') {
      const entry = requests.get(message.params.requestId);
      if (entry) entry.status = message.params.response.status;
    }
    if (message.method === 'Network.loadingFailed') {
      const entry = requests.get(message.params.requestId);
      if (entry) entry.status = `FAILED ${message.params.errorText}`;
    }
  });

  const send = (method, params = {}) =>
    new Promise((resolve) => {
      const id = ++seq;
      pending.set(id, resolve);
      ws.send(JSON.stringify({ id, method, params }));
    });

  const evaluate = async (expression) => {
    const r = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
    return r.result?.exceptionDetails ? undefined : r.result?.result?.value;
  };

  return { send, evaluate, exceptions, requests };
}

/** Centre of the semantics node carrying this exact aria-label. */
async function semanticsPoint(evaluate, label) {
  return evaluate(
    `(() => {
       const node = [...document.querySelectorAll('flt-semantics')]
         .find(e => (e.getAttribute('aria-label') || '').trim() === ${JSON.stringify(label)});
       if (!node) return null;
       const r = node.getBoundingClientRect();
       return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
     })()`,
  );
}

async function clickLabel(ctx, label) {
  const point = await semanticsPoint(ctx.evaluate, label);
  if (!point) return false;
  await ctx.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: point.x, y: point.y });
  await ctx.send('Input.dispatchMouseEvent', { type: 'mousePressed', x: point.x, y: point.y, button: 'left', clickCount: 1 });
  await ctx.send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: point.x, y: point.y, button: 'left', clickCount: 1 });
  return true;
}

async function renderedText(ctx) {
  await ctx.send('Accessibility.enable');
  const tree = await ctx.send('Accessibility.getFullAXTree');
  return [...new Set(
    (tree.result?.nodes || [])
      .flatMap((node) => [node.name?.value, node.value?.value])
      .map((value) => (value || '').trim())
      .filter(Boolean),
  )];
}

// ---------------------------------------------------------------------- run

try {
  console.error(`Warming ${baseUrl} (a free instance sleeps after 15 min idle)...`);
  for (let i = 0; i < 20; i += 1) {
    try {
      const r = await fetch(`${baseUrl}/api/v1/health`, { signal: AbortSignal.timeout(90_000) });
      if (r.ok) break;
    } catch {
      /* keep warming */
    }
    await sleep(3000);
  }

  const ctx = await connect();
  await ctx.send('Runtime.enable');
  await ctx.send('Page.enable');
  await ctx.send('Network.enable');

  const started = Date.now();
  await ctx.send('Page.navigate', { url: `${baseUrl}/` });

  let mounted = false;
  for (let i = 0; i < 120 && !mounted; i += 1) {
    mounted = await ctx.evaluate(`!!document.querySelector('flutter-view, flt-glass-pane')`);
    if (!mounted) await sleep(500);
  }
  check('Flutter app mounts in a browser', mounted, mounted ? `${Date.now() - started}ms` : 'no flutter-view');

  await sleep(6000);

  // CanvasKit paints to a canvas; the text only becomes readable once Flutter's
  // accessibility tree is switched on via its placeholder button.
  let semantics = false;
  for (let i = 0; i < 10 && !semantics; i += 1) {
    semantics = await ctx.evaluate(
      `(() => { const p = document.querySelector('flt-semantics-placeholder'); if (!p) return false; p.click(); return true; })()`,
    );
    if (!semantics) await sleep(1000);
  }
  check('accessibility tree enabled (so text is readable)', semantics);

  const weatherTab = await clickLabel(ctx, 'Weather');
  await sleep(4000);
  const picked = await clickLabel(ctx, location);
  check(`location quick-pick "${location}" is present on the Weather tab`, picked);
  await sleep(14_000);

  const api = [...ctx.requests.values()].filter((r) => r.url.includes('/api/'));
  const weatherCurrent = api.find((r) => r.url.includes('/api/v1/weather/current'));
  const weatherForecast = api.find((r) => r.url.includes('/api/v1/weather/forecast'));

  check('registry fetched from its own origin', api.some((r) => r.url.includes('/api/v1/sources')));
  check('observation fetched', weatherCurrent?.status === 200, `${weatherCurrent?.status ?? 'not requested'}`);
  check('forecast fetched', weatherForecast?.status === 200, `${weatherForecast?.status ?? 'not requested'}`);

  const crossOrigin = api.filter((r) => new URL(r.url).origin !== origin);
  check('every API call is same-origin (the one-origin design)', crossOrigin.length === 0,
    crossOrigin.map((r) => r.url).join(', '));

  check('no uncaught exceptions in the browser', ctx.exceptions.length === 0,
    ctx.exceptions.map((e) => e.split('\n')[0]).join(' | '));

  const text = await renderedText(ctx);
  const screen = text.join('\n');
  console.log('\n--- what the screen renders ---');
  console.log(screen);
  console.log('--- end ---\n');

  if (weatherCurrent) {
    const body = await ctx.send('Network.getResponseBody', { requestId: weatherCurrent.id });
    let payload = null;
    try {
      payload = JSON.parse(body.result?.body ?? '{}');
    } catch {
      /* reported below */
    }
    const observation = payload?.observation;
    const provenance = observation?.provenance;

    check('observation payload parsed', Boolean(observation));
    check('temperature is rendered', observation?.temperature_c == null
      || screen.includes(`${Math.round(observation.temperature_c)}°C`),
      `${observation?.temperature_c}`);
    check('source card names the provider that produced the data',
      !provenance?.source_name || screen.includes(provenance.source_name),
      provenance?.source_name ?? '(no provenance)');

    // The honesty contract: the label must describe what the number actually is.
    const basis = observation?.rainfall_basis ?? null;
    const expectedLabel = RAINFALL_LABEL[basis] ?? 'Rain';
    const hasRain = observation?.rainfall_24h_mm != null;
    check(`rainfall label matches its basis (${basis ?? 'undeclared'})`,
      !hasRain || screen.includes(expectedLabel),
      hasRain ? `expected "${expectedLabel}"` : 'no rainfall value');

    // An unofficial source must never carry the official badge on this screen.
    check('no official badge on non-authoritative data',
      provenance?.authoritative === true
        ? screen.includes('Official source')
        : !screen.includes('Official source'),
      `authoritative=${provenance?.authoritative}`);
  }

  check('the 7-day forecast strip rendered', screen.includes('7-day forecast'));
} catch (error) {
  check('verification harness ran to completion', false, String(error?.message || error));
} finally {
  await cleanup();
}

// -------------------------------------------------------------------- report

const width = Math.max(...results.map((r) => r.name.length));
console.log('WeatherGPT PWA verification — ' + baseUrl);
console.log('='.repeat(width + 16));
for (const r of results) {
  const tag = r.warn ? 'WARN' : r.ok ? 'PASS' : 'FAIL';
  console.log(`[${tag}] ${r.name.padEnd(width)}  ${r.detail}`);
}
const failures = results.filter((r) => !r.ok);
console.log('='.repeat(width + 16));
console.log(`${results.length - failures.length}/${results.length} checks passed`);
process.exit(failures.length ? 1 : 0);
