#!/usr/bin/env node
// report.html → 카드 이미지 여러 장 (report-01.png, report-02.png …, 각 1080×1350)
// 카톡에 순서대로 보내기 좋게 파일명과 이미지 안의 "1 / N" 표시가 같은 순서다.
// 설치된 Chrome / Edge / Chromium을 헤드리스로 띄워 DevTools 프로토콜로 슬라이드마다 캡처한다. 외부 의존성 없음 (Node 22+).
// 사용법: node render.mjs <report.html> [출력 접두어]
// 종료 코드: 0 성공 · 3 브라우저 없음(HTML만 전달) · 4 렌더 실패 · 5 성공했지만 넘친 슬라이드 있음(내용 줄이고 다시)

import { spawn } from 'node:child_process';
import { existsSync, mkdtempSync, writeFileSync, rmSync, readdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve, dirname, basename } from 'node:path';
import { pathToFileURL } from 'node:url';

const [, , htmlArg, prefixArg] = process.argv;
if (!htmlArg) { console.error('usage: node render.mjs <report.html> [출력 접두어]'); process.exit(1); }
const htmlPath = resolve(htmlArg);
const prefix = resolve(prefixArg || htmlPath.replace(/\.html?$/i, ''));

const candidates = [
  process.env.CHROME_PATH,
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
  process.env.LOCALAPPDATA && join(process.env.LOCALAPPDATA, 'Google/Chrome/Application/chrome.exe'),
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  'C:/Program Files/Microsoft/Edge/Application/msedge.exe',
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
  '/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser', '/usr/bin/microsoft-edge',
].filter(Boolean);
const browser = candidates.find((p) => existsSync(p));
if (!browser) { console.error('Chrome/Edge를 찾지 못했어. HTML만 전달하거나 CHROME_PATH 환경변수를 지정해줘.'); process.exit(3); }
if (typeof WebSocket === 'undefined') { console.error('Node 22 이상이 필요해 (내장 WebSocket).'); process.exit(3); }

const VIEW_W = 432;  // 슬라이드 폭(CSS px)
const SCALE = 2.5;   // 432 × 2.5 = 1080px
const profile = mkdtempSync(join(tmpdir(), 'gooddaddy-'));
const proc = spawn(browser, [
  '--headless=new', '--disable-gpu', '--hide-scrollbars', '--no-first-run', '--no-default-browser-check',
  `--user-data-dir=${profile}`, '--remote-debugging-port=0', `--window-size=${VIEW_W},900`, 'about:blank',
], { stdio: ['ignore', 'ignore', 'pipe'] });

const cleanup = () => { try { proc.kill(); } catch {} setTimeout(() => { try { rmSync(profile, { recursive: true, force: true }); } catch {} }, 500); };
const fail = (msg) => { console.error(msg); cleanup(); setTimeout(() => process.exit(4), 700); };
setTimeout(() => fail('렌더링 시간 초과(60초)'), 60000).unref();

const wsUrl = await new Promise((res) => {
  let buf = '';
  proc.stderr.on('data', (d) => {
    buf += d.toString();
    const mm = buf.match(/DevTools listening on (ws:\/\/\S+)/);
    if (mm) res(mm[1]);
  });
});

const ws = new WebSocket(wsUrl);
await new Promise((r) => ws.addEventListener('open', r, { once: true }));
let id = 0;
const pending = new Map();
const listeners = [];
ws.addEventListener('message', (ev) => {
  const msg = JSON.parse(ev.data);
  if (msg.id && pending.has(msg.id)) {
    const { res, rej } = pending.get(msg.id); pending.delete(msg.id);
    msg.error ? rej(new Error(msg.error.message)) : res(msg.result);
  } else listeners.forEach((fn) => fn(msg));
});
const send = (method, params = {}, sessionId) => new Promise((res, rej) => {
  const mid = ++id; pending.set(mid, { res, rej });
  ws.send(JSON.stringify({ id: mid, method, params, ...(sessionId && { sessionId }) }));
});
const evaluate = async (expression, sessionId) => (await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true }, sessionId)).result.value;

let exitCode = 0;
try {
  const { targetId } = await send('Target.createTarget', { url: 'about:blank' });
  const { sessionId } = await send('Target.attachToTarget', { targetId, flatten: true });
  await send('Page.enable', {}, sessionId);
  await send('Emulation.setDeviceMetricsOverride', { width: VIEW_W, height: 900, deviceScaleFactor: SCALE, mobile: false }, sessionId);
  const loaded = new Promise((r) => listeners.push((m) => m.method === 'Page.loadEventFired' && m.sessionId === sessionId && r()));
  await send('Page.navigate', { url: pathToFileURL(htmlPath).href }, sessionId);
  await loaded;
  // 페이지 안 스크립트가 폰트 로딩 후 슬라이드 나누기를 끝낼 때까지 대기
  await evaluate(`new Promise((r) => { const t = () => document.body.dataset.ready ? r(true) : setTimeout(t, 50); t(); })`, sessionId);
  await evaluate(`document.getElementById('deck').style.cssText = 'padding:0;gap:0;align-items:flex-start'; document.querySelectorAll('.slide').forEach(s => s.style.borderRadius = '0'); true`, sessionId);
  // 캡처 직전에 한 번 더 넘침 검사 (폰트·이미지 늦게 붙어서 생긴 넘침까지 잡는다)
  await evaluate(`document.querySelectorAll('.slide').forEach((s, i) => { const b = s.querySelector('.slide-body'); if (b.scrollHeight > b.clientHeight + 1 && !window.__deck.overflow.includes(i + 1)) window.__deck.overflow.push(i + 1); }); true`, sessionId);
  const info = await evaluate(`({ deck: window.__deck, h: Math.ceil(document.documentElement.scrollHeight),
    rects: [...document.querySelectorAll('.slide')].map(s => { const r = s.getBoundingClientRect(); return { x: r.left + scrollX, y: r.top + scrollY, w: r.width, h: r.height }; }) })`, sessionId);
  await send('Emulation.setDeviceMetricsOverride', { width: VIEW_W, height: info.h, deviceScaleFactor: SCALE, mobile: false }, sessionId);
  await new Promise((r) => setTimeout(r, 200));

  // 이전 렌더 결과 정리
  const dir = dirname(prefix), base = basename(prefix);
  for (const f of readdirSync(dir)) if (new RegExp(`^${base.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}-\\d{2}\\.png$`).test(f)) rmSync(join(dir, f));

  const n = info.rects.length;
  for (let i = 0; i < n; i++) {
    const r = info.rects[i];
    const shot = await send('Page.captureScreenshot', { format: 'png', clip: { x: r.x, y: r.y, width: r.w, height: r.h, scale: 1 }, captureBeyondViewport: true }, sessionId);
    const file = `${prefix}-${String(i + 1).padStart(2, '0')}.png`;
    writeFileSync(file, Buffer.from(shot.data, 'base64'));
    const over = info.deck.overflow.includes(i + 1);
    console.log(`${file} (${i + 1}/${n}, ${Math.round(r.w * SCALE)}×${Math.round(r.h * SCALE)})${over ? '  ⚠ 넘침 — 이 장의 글을 줄여서 다시 빌드' : ''}`);
  }
  if (info.deck.overflow.length) exitCode = 5;
} catch (e) {
  fail(`렌더링 실패: ${e.message}`);
}
ws.close();
cleanup();
setTimeout(() => process.exit(exitCode), 700);
