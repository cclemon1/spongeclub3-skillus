#!/usr/bin/env node
// 집 → 후보지들의 이동 거리·시간을 계산한다. 외부 의존성 없음 (Node 18+).
//
// 사용법:
//   node route.mjs --from "서울 마포구 상암동" --region "서울" \
//     --to "국립어린이과학관" --to "서울대공원" --to "37.4339,127.0113" \
//     --depart 2026-09-19T09:30 [--mode car|transit] [--json]
//
// --region  검색어에 지역명을 붙여 동명이소(예: 부산 연산역 ↔ 충남 연산역) 오매칭을 줄인다.
//           좌표 검색도 출발지 주변을 우선한다.
// --mode    car(기본) | transit(대중교통 — 거리 기반 추정치. 노선·환승은 검색으로 확인해야 함)
//
// 자동차 우선순위:
//   1) KAKAO_REST_API_KEY 가 있으면 카카오 로컬(좌표) + 카카오모빌리티 미래 길찾기(출발 시각 교통 반영)
//   2) 없으면 OpenStreetMap Nominatim(좌표) + OSRM(도로 거리) × 주말 교통 보정
//   3) 도로 경로도 실패하면 직선거리 × 1.4 우회계수 기반 추정
// 결과의 source 필드로 어느 방식인지 표시되므로, 리포트에 "추정"인지 드러낸다.
// suspect=true 인 행은 좌표가 엉뚱한 곳에 잡혔을 가능성이 높다 — 좌표로 다시 돌린다.

const args = process.argv.slice(2);
const opt = { to: [], mode: 'car' };
for (let i = 0; i < args.length; i++) {
  const k = args[i];
  const v = args[i + 1];
  if (k === '--from') { opt.from = v; i++; }
  else if (k === '--to') { opt.to.push(v); i++; }
  else if (k === '--depart') { opt.depart = v; i++; }
  else if (k === '--region') { opt.region = v; i++; }
  else if (k === '--mode') { opt.mode = v === 'transit' ? 'transit' : 'car'; i++; }
  else if (k === '--json') { opt.json = true; }
}
if (!opt.from || opt.to.length === 0) {
  console.error('usage: node route.mjs --from "<주소|lat,lng>" --to "<장소|lat,lng>" [--to ...] [--region 지역] [--depart YYYY-MM-DDTHH:MM] [--mode car|transit] [--json]');
  process.exit(1);
}

const KAKAO = process.env.KAKAO_REST_API_KEY;
const UA = 'gooddaddy-report-skill/1.1 (weekend outing planner)';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function parseLatLng(s) {
  const m = String(s).trim().match(/^(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)$/);
  return m ? { lat: +m[1], lng: +m[2], label: s } : null;
}

function withRegion(q) {
  if (!opt.region) return q;
  return q.includes(opt.region) ? q : `${opt.region} ${q}`;
}

async function geocodeKakao(q, near) {
  const h = { Authorization: `KakaoAK ${KAKAO}` };
  const bias = near ? `&x=${near.lng}&y=${near.lat}` : '';
  for (const ep of ['address', 'keyword']) {
    const r = await fetch(`https://dapi.kakao.com/v2/local/search/${ep}.json?query=${encodeURIComponent(q)}&size=1${ep === 'keyword' ? bias : ''}`, { headers: h });
    if (!r.ok) continue;
    const d = await r.json();
    const doc = d.documents?.[0];
    if (doc) return { lat: +doc.y, lng: +doc.x, label: doc.place_name || doc.address_name || q };
  }
  return null;
}

let lastNominatim = 0;
async function nominatim(q, near) {
  // Nominatim 이용 정책: 초당 1회
  const wait = 1100 - (Date.now() - lastNominatim);
  if (wait > 0) await sleep(wait);
  lastNominatim = Date.now();
  // 출발지 주변 ±0.9°(약 100km) 상자를 우선 (bounded=0 이라 밖의 결과도 허용)
  const vb = near ? `&viewbox=${near.lng - 0.9},${near.lat + 0.9},${near.lng + 0.9},${near.lat - 0.9}&bounded=0` : '';
  const r = await fetch(`https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(q)}&format=json&limit=1&countrycodes=kr&accept-language=ko${vb}`, { headers: { 'User-Agent': UA } });
  if (!r.ok) return null;
  const d = await r.json();
  return d[0] ? { lat: +d[0].lat, lng: +d[0].lon, label: d[0].display_name?.split(',').slice(0, 3).join(',') || q } : null;
}

async function geocode(q, near) {
  const ll = parseLatLng(q);
  if (ll) return ll;
  const qq = near ? withRegion(q) : q;
  try {
    if (KAKAO) { const g = await geocodeKakao(qq, near); if (g) return g; }
    return (await nominatim(qq, near)) || (qq !== q ? await nominatim(q, near) : null);
  } catch { return null; }
}

function haversineKm(a, b) {
  const R = 6371, rad = (x) => (x * Math.PI) / 180;
  const dLat = rad(b.lat - a.lat), dLng = rad(b.lng - a.lng);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}

// 주말 교통 보정 (OSRM은 신호·정체가 없는 자유주행 기준이라 한국 도심에서 크게 짧게 나온다)
function weekendFactor(depart, km) {
  const hour = depart ? new Date(depart).getHours() : 10;
  const day = depart ? new Date(depart).getDay() : 6;
  const weekend = day === 0 || day === 6;
  let f = km < 15 ? 1.6 : km < 50 ? 1.4 : 1.2; // 짧은 도심 구간일수록 신호 영향 큼
  if (weekend) {
    if (hour >= 10 && hour < 13) f *= 1.15;      // 나들이 출발 러시
    else if (hour >= 15 && hour < 20) f *= 1.25; // 귀경 정체
    else if (hour < 9) f *= 0.95;                // 이른 아침
  }
  return f;
}

async function routeKakao(a, b, depart) {
  const h = { Authorization: `KakaoAK ${KAKAO}` };
  let url = `https://apis-navi.kakaomobility.com/v1/directions?origin=${a.lng},${a.lat}&destination=${b.lng},${b.lat}&priority=RECOMMEND`;
  let source = 'kakao';
  if (depart) {
    const d = new Date(depart);
    const p = (n) => String(n).padStart(2, '0');
    const t = `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}${p(d.getHours())}${p(d.getMinutes())}`;
    if (d.getTime() > Date.now()) {
      url = `https://apis-navi.kakaomobility.com/v1/future/directions?origin=${a.lng},${a.lat}&destination=${b.lng},${b.lat}&departure_time=${t}`;
      source = 'kakao-future';
    }
  }
  const r = await fetch(url, { headers: h });
  if (!r.ok) return null;
  const s = (await r.json()).routes?.[0]?.summary;
  if (!s) return null;
  return { km: s.distance / 1000, min: s.duration / 60, source };
}

async function routeOSRM(a, b, depart) {
  const r = await fetch(`https://router.project-osrm.org/route/v1/driving/${a.lng},${a.lat};${b.lng},${b.lat}?overview=false`, { headers: { 'User-Agent': UA } });
  if (!r.ok) return null;
  const route = (await r.json()).routes?.[0];
  if (!route) return null;
  const km = route.distance / 1000;
  return { km, min: (route.duration / 60) * weekendFactor(depart, km), source: 'osrm+주말보정' };
}

function routeEstimate(a, b, depart) {
  const km = haversineKm(a, b) * 1.4;
  const speed = km < 15 ? 22 : km < 50 ? 38 : 60; // km/h
  return { km, min: (km / speed) * 60 * (weekendFactor(depart, km) / 1.4), source: '직선거리추정' };
}

// 대중교통: 집→정류장 도보·대기 약 12분 + 차내(도시철도 평균 표정속도 약 30km/h, 경로 1.3배) + 환승 추정 + 하차 후 도보 8분.
// 유모차 동반이면 엘리베이터 찾는 시간이 붙으므로 결과는 하한에 가깝다.
function routeTransit(a, b) {
  const straight = haversineKm(a, b);
  const km = straight * 1.3;
  const transfers = km < 6 ? 0 : km < 20 ? 1 : 2;
  const min = 12 + (km / 30) * 60 + transfers * 7 + 8;
  return { km, min, source: `대중교통추정(환승~${transfers}회)` };
}

const origin = await geocode(opt.from, null);
if (!origin) { console.error(`출발지 좌표를 찾지 못함: ${opt.from} — "위도,경도"로 직접 넣어줘.`); process.exit(2); }

const rows = [];
for (const dest of opt.to) {
  const g = await geocode(dest, origin);
  if (!g) { rows.push({ to: dest, error: '좌표 못 찾음 — 위도,경도로 다시 시도' }); continue; }
  let res = null;
  if (opt.mode === 'transit') res = routeTransit(origin, g);
  else {
    try { if (KAKAO) res = await routeKakao(origin, g, opt.depart); } catch {}
    if (!res) { try { res = await routeOSRM(origin, g, opt.depart); } catch {} }
    if (!res) res = routeEstimate(origin, g, opt.depart);
  }
  rows.push({
    to: dest,
    matched: g.label,
    lat: +g.lat.toFixed(5), lng: +g.lng.toFixed(5),
    straightKm: +haversineKm(origin, g).toFixed(1),
    roadKm: +res.km.toFixed(1),
    travelMin: Math.round(res.min / 5) * 5 || 5,
    mode: opt.mode,
    source: res.source,
  });
}

// 오매칭 탐지: 다른 후보들보다 터무니없이 멀거나, 당일 나들이로 말이 안 되는 거리
const ok = rows.filter((r) => !r.error && !parseLatLng(r.to));
const dists = ok.map((r) => r.straightKm).sort((x, y) => x - y);
const median = dists.length ? dists[Math.floor(dists.length / 2)] : 0;
for (const r of ok) {
  const far = r.straightKm > 150 || (dists.length >= 3 && r.straightKm > Math.max(median * 3, median + 40));
  if (far) r.suspect = true;
}

if (opt.json) {
  console.log(JSON.stringify({ from: { query: opt.from, ...origin }, depart: opt.depart || null, mode: opt.mode, rows }, null, 2));
} else {
  console.log(`출발: ${opt.from} (${origin.lat.toFixed(4)}, ${origin.lng.toFixed(4)})  수단: ${opt.mode === 'transit' ? '대중교통' : '자동차'}  출발시각: ${opt.depart || '미지정(토 10시 가정)'}`);
  for (const r of rows) {
    if (r.error) console.log(`- ${r.to}: ${r.error}`);
    else console.log(`${r.suspect ? '⚠' : '-'} ${r.to} → [${r.matched}] ${r.roadKm}km / 약 ${r.travelMin}분 (직선 ${r.straightKm}km, ${r.source})${r.suspect ? '  ← 좌표 오매칭 의심! 검색으로 찾은 "위도,경도"로 다시 돌릴 것' : ''}`);
  }
  console.log('\n※ [ ] 안 매칭 이름이 의도한 장소가 맞는지 확인. 틀리면 "위도,경도"로 다시 돌린다.');
  if (opt.mode === 'transit') console.log('※ 대중교통 시간은 거리 기반 추정. 노선·환승·엘리베이터 출구는 검색으로 확인해 리포트에 적는다.');
}
