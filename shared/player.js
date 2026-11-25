/* Shared scroll-sequence player.
 *
 * A product page defines window.SEQUENCE (see products/_template/index.html) and the markup
 * ids below, then loads this script. Everything product-specific (frame count, scroll pacing,
 * callout text) lives in that config; this file only plays it back.
 *
 *   SEQUENCE = {
 *     frameCount: 180,                         // frames in each frame folder
 *     version: 1,                              // bump after re-rendering (cache-busting)
 *     renderSize: [1920, 1080],                // render resolution
 *     frameDirs: { light: "frames_white", dark: "frames" },   // omit a theme you didn't render
 *     defaultTheme: "light",                   // ?theme=dark|light overrides
 *     stops: [[vh, frame], ...],               // scroll pacing
 *     callouts: [{ anchor, frames:[a,b], side, title, sub }, ...],   // optional
 *     calloutsFile: "callouts.json",           // optional: anchors + model mask from tools/callouts.py
 *     headlineFrames: [a, b],                  // optional: frames the #headline block shows
 *   }
 *
 * Required markup: #sequence > #stage > canvas#canvas, svg#leaders, #loader.  Optional: #headline.
 */
(() => {
  const C = window.SEQUENCE;
  const dirs = C.frameDirs || { light: "frames" };
  const asked = new URLSearchParams(location.search).get("theme");
  const THEME = dirs[asked] ? asked : (dirs[C.defaultTheme] ? C.defaultTheme : Object.keys(dirs)[0]);
  document.documentElement.dataset.theme = THEME;
  const FRAME_DIR = dirs[THEME];

  const FRAME_COUNT = C.frameCount;
  const VERSION = C.version ?? 1;
  const [RW, RH] = C.renderSize || [1920, 1080];
  const src = i => `${FRAME_DIR}/frame_${String(i + 1).padStart(3, "0")}.webp?v=${VERSION}`;

  // Scroll pacing: [scroll position in vh, animation frame]. Frames between stops are spread
  // evenly, so a long vh span with few frames = the page lingers there (used for callouts).
  const STOPS = C.stops || [[0, 1], [600, FRAME_COUNT]];
  const CALLOUTS = (C.callouts || []).map(c => ({ ...c }));
  const HEADLINE_FRAMES = C.headlineFrames || null;
  const PAD = 16, CLEAR = 14;                 // screen edge padding; min gap between text and model

  const canvas = document.getElementById("canvas");
  const ctx = canvas.getContext("2d");
  const track = document.getElementById("sequence");
  const stage = document.getElementById("stage");
  const svg = document.getElementById("leaders");
  const headline = HEADLINE_FRAMES && document.getElementById("headline");
  const loader = document.getElementById("loader");
  const NS = "http://www.w3.org/2000/svg";

  const TRACK_VH = STOPS[STOPS.length - 1][0];
  track.style.height = `calc(${TRACK_VH}vh + 100vh)`;

  for (const c of CALLOUTS) {
    c.el = document.createElement("div");
    c.el.className = "label";
    c.el.innerHTML = `<b>${c.title}</b><span>${c.sub || ""}</span>`;
    stage.insertBefore(c.el, loader);
    c.line = document.createElementNS(NS, "polyline");
    c.ring = document.createElementNS(NS, "circle"); c.ring.setAttribute("class", "ring"); c.ring.setAttribute("r", 7);
    c.dot = document.createElementNS(NS, "circle"); c.dot.setAttribute("class", "dot"); c.dot.setAttribute("r", 3);
    c.g = document.createElementNS(NS, "g"); c.g.append(c.line, c.ring, c.dot); c.g.style.opacity = 0;
    svg.append(c.g);
  }

  // ---- data: anchor tracks + per-frame model mask (where the model is on screen)
  let anchors = null, mask = null;
  if (C.calloutsFile && (CALLOUTS.length || headline)) {
    fetch(`${C.calloutsFile}?v=${VERSION}`).then(r => r.json()).then(d => {
      anchors = d.anchors;
      const m = d.mask;
      if (m) mask = { cols: m.cols, rows: m.rows, frames: m.frames.map(b64 => Uint8Array.from(atob(b64), ch => ch.charCodeAt(0))) };
      layoutCache.clear(); update();
    }).catch(() => {});
  }

  // ---- frames
  const frames = new Array(FRAME_COUNT);
  let loaded = 0, current = -1, rect = { x: 0, y: 0, w: 1, h: 1 };
  for (let i = 0; i < FRAME_COUNT; i++) {
    const img = new Image();
    img.decoding = "async";
    img.onload = () => {
      loaded++;
      loader.style.transform = `scaleX(${loaded / FRAME_COUNT})`;
      if (loaded === FRAME_COUNT) loader.style.opacity = 0;
      if (i === 0 || i === Math.round(frameAt() - 1)) draw(true);
    };
    img.src = src(i);
    frames[i] = img;
  }

  function resize() {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = canvas.clientWidth * dpr;
    canvas.height = canvas.clientHeight * dpr;
    rect = fitRect(RW, RH);            // known render size, so layout doesn't wait for images
    layoutCache.clear();
    draw(true); update();
  }

  // scroll -> continuous frame number (1..FRAME_COUNT) via STOPS
  function frameAt() {
    const r = track.getBoundingClientRect();
    const total = r.height - window.innerHeight;
    const p = Math.min(1, Math.max(0, -r.top / total));
    const vh = p * TRACK_VH;
    for (let k = 1; k < STOPS.length; k++) {
      const [v0, f0] = STOPS[k - 1], [v1, f1] = STOPS[k];
      if (vh <= v1) return f0 + (f1 - f0) * (vh - v0) / (v1 - v0);
    }
    return FRAME_COUNT;
  }

  function nearestLoaded(i) {
    for (let d = 0; d < FRAME_COUNT; d++) {
      if (frames[i - d]?.complete && frames[i - d].naturalWidth) return frames[i - d];
      if (frames[i + d]?.complete && frames[i + d].naturalWidth) return frames[i + d];
    }
    return null;
  }

  function draw(force) {
    const i = Math.round(frameAt()) - 1;
    if (i === current && !force) return;
    const img = nearestLoaded(i);
    if (!img) return;
    current = i;
    const cw = canvas.width, ch = canvas.height;
    const r = fitRect(img.naturalWidth, img.naturalHeight), k = cw / canvas.clientWidth;
    ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue("--bg");
    ctx.fillRect(0, 0, cw, ch);
    ctx.drawImage(img, r.x * k, r.y * k, r.w * k, r.h * k);
  }

  // where the frame sits on screen, in CSS px: "contain" on wide screens, gentle "cover" crop
  // on tall/mobile screens
  function fitRect(iw, ih) {
    const cw = canvas.clientWidth, ch = canvas.clientHeight;
    const contain = Math.min(cw / iw, ch / ih), cover = Math.max(cw / iw, ch / ih);
    const s = Math.min(cover, contain * 1.6), w = iw * s, h = ih * s;
    return { x: (cw - w) / 2, y: (ch - h) / 2, w, h };
  }

  // ---- layout: keep every text box clear of the model, other labels and the screen edge
  const overlaps = (a, b) => a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;

  function hitsModel(box, fi) {
    if (!mask) return false;
    const bits = mask.frames[fi - 1]; if (!bits) return false;
    const { cols, rows } = mask;
    const c0 = Math.max(0, Math.floor((box.x - CLEAR - rect.x) / rect.w * cols));
    const c1 = Math.min(cols - 1, Math.floor((box.x + box.w + CLEAR - rect.x) / rect.w * cols));
    const r0 = Math.max(0, Math.floor((box.y - CLEAR - rect.y) / rect.h * rows));
    const r1 = Math.min(rows - 1, Math.floor((box.y + box.h + CLEAR - rect.y) / rect.h * rows));
    for (let r = r0; r <= r1; r++) for (let c = c0; c <= c1; c++) {
      const n = r * cols + c;
      if (bits[n >> 3] & (0x80 >> (n & 7))) return true;
    }
    return false;
  }

  // ---- Fixed placement: each label gets ONE screen position for its whole window (only the
  // leader line follows the part), so text never moves. The spot must be clear of the model in
  // every frame of the window, clear of the labels/headline shown at the same time, and the
  // leaders must not cross other labels or each other. Recomputed on resize / data load.
  const range = ([a, b]) => Array.from({ length: b - a + 1 }, (_, i) => a + i);
  const anchorPx = (c, fi) => {
    const A = anchors?.[c.anchor], pt = A && A.pts[fi - A.from];
    return pt ? { x: rect.x + pt[0] * rect.w, y: rect.y + pt[1] * rect.h, vis: !!pt[2] } : null;
  };
  const boxOf = (p, lw, lh) => ({ x: p.side === "left" ? p.lx - lw : p.lx, y: p.ly - lh / 2, w: lw, h: lh });
  const leaderStart = p => ({ x: p.side === "left" ? p.lx + 10 : p.lx - 10, y: p.ly });

  // does segment p->q pass through box (grown by g)?
  function segHitsBox(p, q, b, g = 6) {
    const x0 = b.x - g, x1 = b.x + b.w + g, y0 = b.y - g, y1 = b.y + b.h + g;
    let t0 = 0, t1 = 1; const dx = q.x - p.x, dy = q.y - p.y;
    for (const [pp, qq] of [[-dx, p.x - x0], [dx, x1 - p.x], [-dy, p.y - y0], [dy, y1 - p.y]]) {
      if (pp === 0) { if (qq < 0) return false; continue; }
      const t = qq / pp;
      if (pp < 0) { if (t > t1) return false; if (t > t0) t0 = t; } else { if (t < t0) return false; if (t < t1) t1 = t; }
    }
    return true;
  }
  const segsCross = (a, b, c, d) => {
    const o = (p, q, r) => Math.sign((q.x - p.x) * (r.y - p.y) - (q.y - p.y) * (r.x - p.x));
    return o(a, b, c) * o(a, b, d) < 0 && o(c, d, a) * o(c, d, b) < 0;
  };
  // leader polyline for a label position and an anchor point
  const leader = (p, a) => { const s = leaderStart(p); const e = { x: s.x + (a.x - s.x) * 0.3, y: s.y }; return [s, e, a]; };

  function placeFixed(c, lw, lh, placed) {
    const W = stage.clientWidth, H = stage.clientHeight;
    const fr = range(c.frames).filter(fi => anchorPx(c, fi));
    if (!fr.length) return null;
    const pts = fr.map(fi => anchorPx(c, fi));
    const ax = pts.reduce((s, p) => s + p.x, 0) / pts.length, ay = pts.reduce((s, p) => s + p.y, 0) / pts.length;
    const samples = [fr[0], fr[fr.length >> 1], fr[fr.length - 1]].map((fi, i) => [fi, pts[[0, pts.length >> 1, pts.length - 1][i]]]);
    const others = placed.filter(o => o.frames[0] <= c.frames[1] && c.frames[0] <= o.frames[1]);
    let best = null;
    for (const side of ["left", "right"]) {
      for (let ly = PAD + lh / 2; ly <= H - PAD - lh / 2; ly += 12) {
        for (let dx = 36; dx < W; dx += 12) {
          const lx = side === "left" ? ax - dx : ax + dx;
          const p = { side, lx, ly };
          const box = boxOf(p, lw, lh);
          if (box.x < PAD || box.x + box.w > W - PAD) break;
          let blocked = false;
          for (const fi of fr) if (hitsModel(box, fi)) { blocked = true; break; }
          if (blocked) continue;
          for (const o of others) if (overlaps(box, { x: o.box.x - 12, y: o.box.y - 8, w: o.box.w + 24, h: o.box.h + 16 })) { blocked = true; break; }
          if (blocked) continue;
          // leaders: ours must not run through other labels; no crossings with their leaders
          let cross = 0;
          for (const o of others) for (const [fi, a] of samples) {
            const L = leader(p, a);
            if (segHitsBox(L[0], L[1], o.box) || segHitsBox(L[1], L[2], o.box)) cross += 3;
            if (o.c) {
              const oa = anchorPx(o.c, fi); if (!oa) continue;
              const M = leader(o.p, oa);
              for (let i = 0; i < 2; i++) for (let j = 0; j < 2; j++) if (segsCross(L[i], L[i + 1], M[j], M[j + 1])) cross++;
            }
            if (o.c && segHitsBox(...leader(o.p, anchorPx(o.c, fi) || a).slice(1), box)) cross += 3;
          }
          const dist = Math.hypot(lx - ax, ly - ay);
          const cost = dist + (side === c.side ? 0 : 160) + cross * 400;
          if (!best || cost < best.cost) best = { p, box, cost };
          break;                                  // nearest clear spot on this row is enough
        }
      }
    }
    if (best) return best;
    // nothing clear for the whole window (very small screens): park on the preferred side
    const p = { side: c.side, lx: c.side === "left" ? Math.max(PAD + lw, ax - 40) : Math.min(W - PAD - lw, ax + 40), ly: ay };
    return { p, box: boxOf(p, lw, lh) };
  }

  function placeHeadlineFixed() {
    const W = stage.clientWidth, H = stage.clientHeight;
    const hw = headline.offsetWidth, hh = headline.offsetHeight, m = Math.max(PAD, W * 0.06);
    const spots = [[m, H * 0.1], [m, H - hh - H * 0.08], [W - hw - m, H * 0.1], [W - hw - m, H - hh - H * 0.08], [(W - hw) / 2, PAD + 8]];
    for (const [x, y] of spots) {
      const box = { x, y, w: hw, h: hh };
      if (range(HEADLINE_FRAMES).every(fi => !hitsModel(box, fi))) return box;
    }
    return { x: spots[0][0], y: spots[0][1], w: hw, h: hh };
  }

  let layout = null;                 // computed once per viewport size / data load
  const layoutCache = { clear() { layout = null; } };
  function computeLayout() {
    const hbox = headline ? placeHeadlineFixed() : null;
    const placed = hbox ? [{ frames: HEADLINE_FRAMES, box: hbox }] : [];
    // place labels sharing a window together, top-to-bottom by anchor height so leaders don't cross
    const order = [...CALLOUTS].sort((a, b) => a.frames[0] - b.frames[0] ||
      ((anchorPx(a, a.frames[0])?.y ?? 0) - (anchorPx(b, b.frames[0])?.y ?? 0)));
    for (const c of order) {
      const r = placeFixed(c, c.el.offsetWidth, c.el.offsetHeight, placed);
      c.fixed = r && r.p;
      if (r) placed.push({ frames: c.frames, box: r.box, c, p: r.p });
    }
    layout = { hbox };
  }
  const ramp = (f, [a, b]) => Math.max(0, Math.min(1, f - a + 1, b + 1 - f));

  function placeCallouts(f) {
    const fi = Math.round(f);
    if (!layout && anchors && mask) computeLayout();
    if (headline) {
      const h = ramp(f, HEADLINE_FRAMES);
      if (h && layout) {
        const box = layout.hbox;
        headline.style.transform = `translate(${box.x}px, ${box.y + (1 - h) * 12}px)`;
      }
      headline.style.opacity = layout ? h : 0;
    }

    for (const c of CALLOUTS) {
      const a = layout && c.fixed && anchorPx(c, fi);
      const o = a && a.vis ? ramp(f, c.frames) : 0;
      c.el.style.opacity = o; c.g.style.opacity = o;
      if (!o) continue;
      const ax = a.x, ay = a.y, p = c.fixed;
      const lw = c.el.offsetWidth, lh = c.el.offsetHeight;
      const box = boxOf(p, lw, lh);
      c.el.classList.toggle("left", p.side === "left");
      c.el.style.transform = `translate(${box.x}px, ${box.y}px)`;
      // leader: from the label's inner edge, short horizontal run, then to the part
      const sx = p.side === "left" ? p.lx + 10 : p.lx - 10;
      const ex = sx + (ax - sx) * 0.3;
      c.line.setAttribute("points", `${sx},${p.ly} ${ex},${p.ly} ${ax},${ay}`);
      c.dot.setAttribute("cx", ax); c.dot.setAttribute("cy", ay);
      c.ring.setAttribute("cx", ax); c.ring.setAttribute("cy", ay);
    }
  }

  function update() {
    const f = frameAt();
    draw(false);
    placeCallouts(f);
  }

  let ticking = false;
  window.addEventListener("scroll", () => {
    if (!ticking) { ticking = true; requestAnimationFrame(() => { update(); ticking = false; }); }
  }, { passive: true });
  window.addEventListener("resize", resize);
  resize(); update();
})();
