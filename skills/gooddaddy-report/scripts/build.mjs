#!/usr/bin/env node
// plan.json(여정 데이터) → report.html (카드뉴스형 슬라이드 묶음, 4:5 비율)
// 슬라이드 나누기는 페이지 안의 스크립트가 실제 글자 높이를 재서 자동으로 한다.
// 각 슬라이드 오른쪽 위에 "1 / N" 순서 표시가 붙어서 카톡에 순서대로 보내기 좋다.
// 사용법: node build.mjs <plan.json> [out.html]   → 이어서 render.mjs 로 PNG 여러 장
// 데이터 구조는 references/plan-schema.md 참고.

import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const [, , planPath, outArg] = process.argv;
if (!planPath) { console.error('usage: node build.mjs <plan.json> [out.html]'); process.exit(1); }
const plan = JSON.parse(readFileSync(planPath, 'utf8'));
const out = outArg || join(dirname(resolve(planPath)), 'report.html');
const css = readFileSync(join(here, '..', 'assets', 'report.css'), 'utf8');

const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const list = (a) => (Array.isArray(a) ? a : a ? [a] : []);
const when = (cond, html) => (cond ? html : '');

const m = plan.meta || {};
const w = plan.weather || {};
const transit = /transit|대중/.test(m.transport || '');
const MOVE = transit ? '🚇' : '🚗';
const TYPE_ICON = { move: MOVE, walk: '🚶', play: '🎈', meal: '🍚', nap: '😴', snack: '🍼', rest: '🧸', home: '🏠', prep: '🎒' };

const places = list(plan.places).slice().sort((a, b) => (a.rank ?? 99) - (b.rank ?? 99));
const pick = places[0] || {};
const others = places.slice(1);
const travelOf = (p) => p.travelMin ?? p.driveMin;
const travelText = (p) => {
  const t = travelOf(p);
  if (t == null) return '';
  const icon = p.travelMode === 'transit' || (transit && p.travelMode !== 'car') ? '🚇' : p.travelMode === 'walk' ? '🚶' : '🚗';
  return `${icon} ${esc(t)}분${p.distanceKm != null ? ` · ${esc(p.distanceKm)}km` : ''}`;
};

const weatherCells = [
  ['기온', w.tempMin != null ? `${w.tempMin}°~${w.tempMax}°` : w.temp],
  ['강수', w.rainProb != null && w.rainProb !== '' ? (typeof w.rainProb === 'number' ? `${w.rainProb}%` : w.rainProb) : null],
  ['미세먼지', w.dust],
  ['자외선', w.uv],
].filter(([, v]) => v != null && v !== '');

// ── 블록 정의: data-break="before" 는 새 슬라이드에서 시작, data-keep 은 다음 블록과 붙여 둔다,
//    data-cont 는 슬라이드가 넘어갈 때 새 슬라이드 맨 위에 붙일 "(이어서)" 제목
const blocks = [];
const block = (html, attrs = '') => blocks.push(`<section class="block" ${attrs}>${html}</section>`);

// 1. 표지
block(`
  <div class="hero">
    <div class="eyebrow">${esc(m.dateLabel || '')}${when(m.recipient, ` · ${esc(m.recipient)}에게 보고`)}</div>
    <h1>${esc(plan.headline || m.title || '이번 주말 나들이 계획')}</h1>
    ${when(plan.summary, `<p class="summary">${esc(plan.summary)}</p>`)}
    <div class="who">${[m.child && `👶 ${esc(m.child)}`, m.from && `🏠 ${esc(m.from)} 출발`, transit ? '🚇 대중교통' : ''].filter(Boolean).join(' · ')}</div>
  </div>`, 'data-break="before"');
if (Object.keys(w).length) block(`
  <div class="weather">
    <div class="w-icon">${esc(w.icon || '🌤')}</div>
    <div class="w-main">
      <div class="w-sum">${esc(w.summary || '')}</div>
      <div class="w-cells">${weatherCells.map(([k, v]) => `<span><em>${k}</em>${esc(v)}</span>`).join('')}</div>
      ${when(w.advice, `<div class="w-advice">→ ${esc(w.advice)}</div>`)}
    </div>
  </div>`);
if (plan.message) block(`<div class="message">💬 ${esc(plan.message)}</div>`);
if (places.length > 1) block(`
  <div class="glance">
    ${places.map((p) => `<div class="g-row ${p === pick ? 'is-pick' : ''}"><span class="g-rank">${esc(p.rank)}</span><span class="g-name">${esc(p.name)}</span><span class="g-min">${travelText(p).replace(/ · .*$/, '')}</span></div>`).join('')}
  </div>`);

// 2. 1순위 하루 여정
const steps = list(plan.itinerary);
if (steps.length) {
  block(`
    <h2 class="slide-title">📍 ${esc(pick.name || '추천 코스')} 하루 여정</h2>
    ${when(plan.itineraryNote, `<p class="note">${esc(plan.itineraryNote)}</p>`)}`, 'data-break="before" data-keep');
  steps.forEach((s, i) => block(`
    <div class="step step-${esc(s.type || 'play')} ${i === 0 ? 'first' : ''} ${i === steps.length - 1 ? 'last' : ''}">
      <div class="t">${esc(s.time)}</div>
      <div class="dot">${TYPE_ICON[s.type] || '•'}</div>
      <div class="body"><b>${esc(s.title)}</b>${when(s.detail, `<p>${esc(s.detail)}</p>`)}</div>
    </div>`, `data-cont="📍 하루 여정 (이어서)"`));
}

// 3. 1순위 상세
if (pick.name) {
  const tags = [
    pick.category && `<span class="tag">${esc(pick.category)}</span>`,
    travelOf(pick) != null && `<span class="tag tag-move">${travelText(pick)}</span>`,
    pick.openRun && `<span class="tag tag-hot">⏰ 오픈런</span>`,
    pick.reservation && `<span class="tag tag-hot">📝 예약 필요</span>`,
  ].filter(Boolean).join('');
  block(`
    <div class="pick-head">
      <div class="rank-badge">1순위</div>
      <div><h2>${esc(pick.name)}</h2>${when(pick.area, `<div class="area">${esc(pick.area)}</div>`)}</div>
    </div>
    <div class="tags">${tags}</div>
    ${when(list(pick.why).length, `<ul class="why">${list(pick.why).map((x) => `<li>${esc(x)}</li>`).join('')}</ul>`)}
    ${when(list(pick.babyInfo).length, `<div class="chips">${list(pick.babyInfo).map((x) => `<span>${esc(x)}</span>`).join('')}</div>`)}`, 'data-break="before" data-keep');
  block(`
    <dl class="facts">
      ${when(pick.transitRoute, `<div><dt>경로</dt><dd>${esc(pick.transitRoute)}</dd></div>`)}
      ${when(pick.hours, `<div><dt>운영</dt><dd>${esc(pick.hours)}</dd></div>`)}
      ${when(pick.fee, `<div><dt>요금</dt><dd>${esc(pick.fee)}</dd></div>`)}
      ${when(pick.caution, `<div class="warn"><dt>주의</dt><dd>${esc(pick.caution)}</dd></div>`)}
    </dl>`, 'data-cont="1순위 (이어서)"');
  const rest = list(pick.restaurants);
  if (rest.length) {
    block(`<div class="rest-label">🍽 근처 아기랑 먹을 곳</div>`, 'data-keep data-cont="🍽 먹을 곳 (이어서)"');
    rest.forEach((r) => block(`
      <div class="rest-item">
        <div class="r-top"><b>${esc(r.name)}</b>${when(r.distance, `<span class="r-dist">${esc(r.distance)}</span>`)}</div>
        ${when(r.menu, `<div class="r-menu">${esc(r.menu)}</div>`)}
        ${when(r.why, `<div class="r-why">${esc(r.why)}</div>`)}
      </div>`, 'data-cont="🍽 먹을 곳 (이어서)"'));
  }
}

// 4. 다른 선택지 (요약 카드)
if (others.length) {
  block(`<h2 class="slide-title">다른 선택지 ${others.length}곳</h2>`, 'data-break="before" data-keep');
  others.forEach((p) => {
    const rest = list(p.restaurants).map((r) => `${esc(r.name)}${r.menu ? ` <i>${esc(r.menu)}</i>` : ''}`).join(' · ');
    const flags = [p.category, p.openRun && '⏰ 오픈런', p.reservation && '📝 예약'].filter(Boolean).map((x) => `<span class="tag ${/오픈런|예약/.test(x) ? 'tag-hot' : ''}">${esc(x)}</span>`).join('');
    block(`
      <div class="mini">
        <div class="mini-top"><span class="mini-rank">${esc(p.rank)}</span><b class="mini-name">${esc(p.name)}</b>${flags}<span class="mini-move">${travelText(p).replace(/ · .*$/, '')}</span></div>
        ${when(list(p.why)[0], `<div class="mini-why">${esc(list(p.why)[0])}</div>`)}
        ${when(p.departHint || p.caution, `<div class="mini-hint">⏰ ${esc([p.departHint, p.caution].filter(Boolean).join(' · '))}</div>`)}
        ${when(rest, `<div class="mini-rest">🍽 ${rest}</div>`)}
      </div>`, `data-cont="다른 선택지 (이어서)"`);
  });
}

// 5. 플랜 B · 챙길 것 · 메모
if (plan.planB) block(`<h2 class="slide-title">☔ 플랜 B</h2><p class="planb">${esc(plan.planB)}</p>`, 'data-break="before"');
if (list(plan.checklist).length) block(`<h2 class="slide-title">🎒 챙길 것</h2><ul class="check">${list(plan.checklist).map((x) => `<li>${esc(x)}</li>`).join('')}</ul>`, plan.planB ? '' : 'data-break="before"');
block(`
  <div class="notes">
    ${when(m.author, `<div>작성 ${esc(m.author)}${when(m.createdAt, ` · ${esc(m.createdAt)}`)}</div>`)}
    ${list(plan.notes).map((n) => `<div>※ ${esc(n)}</div>`).join('')}
  </div>`);

const html = `<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${esc(m.title || '주말 나들이 보고서')}</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css">
<style>${css}</style>
</head>
<body>
<div id="deck"></div>
<div id="pool" aria-hidden="true">${blocks.join('\n')}</div>
<template id="slide-tpl">
  <article class="slide">
    <header class="slide-top"><span class="brand">${esc(m.shortLabel || ['주말 나들이 보고서', m.dateLabel].filter(Boolean).join(' · '))}</span><span class="count"></span></header>
    <div class="slide-body"></div>
    <footer class="slide-foot"></footer>
  </article>
</template>
<script>
(async () => {
  if (document.readyState !== 'complete') await new Promise((r) => addEventListener('load', r, { once: true }));
  // 슬라이드를 재기 전에 실제로 쓰는 웹폰트 굵기를 전부 불러온다 (안 그러면 대체 폰트로 재고 나중에 글자가 넘친다)
  try { await Promise.all(['400', '600', '700', '800'].map((wt) => document.fonts.load(wt + ' 14px Pretendard', '가A1'))); } catch (e) {}
  try { await document.fonts.ready; } catch (e) {}
  await new Promise((r) => setTimeout(r, 50));
  const deck = document.getElementById('deck');
  const pool = [...document.querySelectorAll('#pool > .block')];
  const tpl = document.getElementById('slide-tpl');
  const slides = [];
  const overflow = [];
  const newSlide = () => {
    const s = tpl.content.firstElementChild.cloneNode(true);
    deck.appendChild(s); slides.push(s);
    return s.querySelector('.slide-body');
  };
  const fits = (body) => body.scrollHeight <= body.clientHeight + 1;
  const contHead = (text) => {
    const el = document.createElement('section');
    el.className = 'block cont'; el.innerHTML = '<h2 class="slide-title">' + text + '</h2>';
    return el;
  };
  let body = newSlide();
  for (let i = 0; i < pool.length; i++) {
    const b = pool[i];
    if (b.dataset.break === 'before' && body.children.length) body = newSlide();
    // data-keep: 제목 블록은 다음 블록과 함께 들어갈 때만 이 슬라이드에 둔다
    const group = [b];
    let j = i;
    while (pool[j].hasAttribute('data-keep') && pool[j + 1] && pool[j + 1].dataset.break !== 'before') group.push(pool[++j]);
    group.forEach((g) => body.appendChild(g));
    if (!fits(body) && body.children.length > group.length) {
      group.forEach((g) => g.remove());
      body = newSlide();
      if (b.dataset.cont) body.appendChild(contHead(b.dataset.cont));
      group.forEach((g) => body.appendChild(g));
    }
    if (!fits(body)) overflow.push(slides.length);
    i = j;
  }
  const n = slides.length;
  slides.forEach((s, k) => {
    s.querySelector('.count').textContent = (k + 1) + ' / ' + n;
    s.querySelector('.slide-foot').textContent = k + 1 < n ? '다음 장에 계속 →' : '끝 · 좋은 주말 보내요 🙌';
    if (overflow.includes(k + 1)) s.classList.add('is-overflow');
  });
  window.__deck = { slides: n, overflow: [...new Set(overflow)] };
  document.body.dataset.ready = 'true';
})();
</script>
</body>
</html>`;

writeFileSync(out, html, 'utf8');
console.log(out);
