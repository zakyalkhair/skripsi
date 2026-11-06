/**
 * Ekspor Peta (PNG) — digambar ulang pada <canvas>, bukan tangkapan layar DOM:
 * - peta dasar: ubin OSM diambil ulang dengan fetch mode CORS. Bila server ubin tidak mengizinkan
 *   (atau jaringan gagal), peta dasar TIDAK disertakan dan hal itu dinyatakan di gambar — keamanan
 *   peramban (kanvas tercemar) tidak pernah diakali;
 * - poligon, garis provinsi, dan seleksi: path SVG Leaflet digambar ulang dengan gaya terhitung;
 * - penanda & klaster: digambar ulang dari data penanda yang sedang tampil (posisi dari DOM);
 * - bingkai: judul, cakupan wilayah, periode, filter jenis, legenda, atribusi, penafian, waktu ekspor.
 * Panel rincian, asisten, dan kontrol tidak ikut digambar.
 */
import { JENIS, LABEL_PENDEK, warna } from "../jenis";
import { KELAS, LEGENDA_PENANDA } from "../map/legend";
import { countLabel, ikonTampil, markerWidth, MK_H } from "../map/marker";
import { drawIcon, type IconName } from "../ui/icons";
import type { MapView } from "../map/map";
import type { Jenis, Titik } from "../types";

export interface PngMeta {
  wilayah: string;
  periode: string;
  jenis: string;
  sorot: string | null;
  lokasi: string | null;
  kabMode: boolean;
  contoh: boolean;
  dataset: string;
  slug: string;
}
export interface Crop { x: number; y: number; w: number; h: number }
export interface PngResult { blob: Blob; filename: string; peta: "lengkap" | "tanpa-peta-dasar" }

const F = '"Plus Jakarta Sans Variable", "Plus Jakarta Sans", system-ui, sans-serif';
const css = (name: string, fb: string) => getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fb;
const font = (w: number, px: number) => `${w} ${px}px ${F}`;

function waitEvent(target: { once(ev: string, fn: () => void): unknown }, ev: string, ms: number): Promise<void> {
  return new Promise((res) => { const t = window.setTimeout(res, ms); target.once(ev, () => { window.clearTimeout(t); res(); }); });
}

/** Tunggu kamera diam dan ubin selesai dimuat (dengan batas waktu agar tidak menggantung). */
async function idle(view: MapView): Promise<void> {
  if (view.isMoving) await waitEvent(view.map, "moveend", 3000);
  const tl = view.tiles as unknown as { isLoading(): boolean };
  if (tl.isLoading()) await waitEvent(view.tiles, "load", 6000);
  await new Promise((r) => requestAnimationFrame(() => r(null)));
}

async function fetchBitmap(src: string, ms = 6000): Promise<ImageBitmap> {
  const ac = new AbortController();
  const t = window.setTimeout(() => ac.abort(), ms);
  try {
    const r = await fetch(src, { mode: "cors", credentials: "omit", signal: ac.signal });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return await createImageBitmap(await r.blob());
  } finally { window.clearTimeout(t); }
}

function wrap(ctx: CanvasRenderingContext2D, text: string, maxW: number): string[] {
  const words = text.split(" "), lines: string[] = [];
  let cur = "";
  for (const w of words) {
    const next = cur ? `${cur} ${w}` : w;
    if (ctx.measureText(next).width > maxW && cur) { lines.push(cur); cur = w; } else cur = next;
  }
  if (cur) lines.push(cur);
  return lines;
}

const dash = (v: string): number[] => (!v || v === "none" ? [] : v.split(/[\s,]+/).map((x) => parseFloat(x)).filter((x) => !Number.isNaN(x)));

/** Gambar ulang path SVG satu pane Leaflet dengan gaya terhitung (warna, opasitas, garis putus). */
function drawPane(ctx: CanvasRenderingContext2D, pane: HTMLElement | undefined, origin: { x: number; y: number }): void {
  const svg = pane?.querySelector("svg");
  if (!svg) return;
  const r = svg.getBoundingClientRect(), vb = svg.viewBox.baseVal;
  if (!vb || !vb.width || !vb.height) return;
  const sx = r.width / vb.width, sy = r.height / vb.height;
  for (const p of svg.querySelectorAll<SVGPathElement>("path")) {
    const d = p.getAttribute("d");
    if (!d || d === "M0 0") continue;
    const cs = getComputedStyle(p);
    if (cs.display === "none" || cs.visibility === "hidden") continue;
    const op = parseFloat(cs.opacity || "1");
    const path = new Path2D(d);
    ctx.save();
    ctx.translate(r.left - origin.x, r.top - origin.y);
    ctx.scale(sx, sy);
    ctx.translate(-vb.x, -vb.y);
    if (cs.fill && cs.fill !== "none") {
      ctx.globalAlpha = op * parseFloat(cs.fillOpacity || "1");
      ctx.fillStyle = cs.fill;
      ctx.fill(path, cs.fillRule === "nonzero" ? "nonzero" : "evenodd");
    }
    const lw = parseFloat(cs.strokeWidth || "0");
    if (cs.stroke && cs.stroke !== "none" && lw > 0) {
      ctx.globalAlpha = op * parseFloat(cs.strokeOpacity || "1");
      ctx.strokeStyle = cs.stroke;
      ctx.lineWidth = lw;
      ctx.lineJoin = (cs.strokeLinejoin as CanvasLineJoin) || "round";
      ctx.lineCap = (cs.strokeLinecap as CanvasLineCap) || "round";
      ctx.setLineDash(dash(cs.strokeDasharray));
      ctx.stroke(path);
    }
    ctx.restore();
  }
}

function circle(ctx: CanvasRenderingContext2D, x: number, y: number, r: number): void { ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); }

/** Pil penanda pada kanvas (x,y = tengah) — sama dengan markerHtml (marker.ts). */
function drawPil(ctx: CanvasRenderingContext2D, t: Pick<Titik, "jenis" | "jumlah_laporan" | "di_luar_kab">, x: number, y: number,
  o: { sel?: boolean; skala?: number; bayang?: boolean } = {}): void {
  const ink = css("--ink", "#1d1a17");
  const k = o.skala ?? 1, w = markerWidth(t as Titik), hgt = MK_H;
  ctx.save();
  ctx.translate(x, y); ctx.scale(k, k); ctx.translate(-w / 2, -hgt / 2);
  if (o.bayang !== false) { ctx.shadowColor = "rgba(20,14,8,0.25)"; ctx.shadowBlur = 4; ctx.shadowOffsetY = 2; }
  ctx.beginPath(); ctx.roundRect(0.75, 0.75, w - 1.5, hgt - 1.5, hgt / 2);
  ctx.fillStyle = o.sel ? ink : t.di_luar_kab ? "rgba(255,255,255,0.85)" : "#fff"; ctx.fill();
  ctx.shadowColor = "transparent";
  ctx.lineWidth = 1.5; ctx.strokeStyle = ink; ctx.setLineDash(t.di_luar_kab ? [4, 3] : []); ctx.stroke(); ctx.setLineDash([]);
  const { tampil, sisa } = ikonTampil(t.jenis);
  let cx = 4;
  for (const j of tampil) {
    ctx.beginPath(); ctx.arc(cx + 13, hgt / 2, 12.25, 0, Math.PI * 2); ctx.fillStyle = warna(j); ctx.fill();
    ctx.lineWidth = 1.5; ctx.strokeStyle = "#fff"; ctx.stroke();
    drawIcon(ctx, `j_${j}` as IconName, cx + 5.5, hgt / 2 - 7.5, 15, "#fff");
    cx += 18;
  }
  if (sisa) {
    ctx.beginPath(); ctx.roundRect(cx, hgt / 2 - 13, 30, 26, 13); ctx.fillStyle = "#ece7df"; ctx.fill();
    ctx.lineWidth = 1.5; ctx.strokeStyle = "#fff"; ctx.stroke();
    ctx.fillStyle = ink; ctx.font = font(700, 11); ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.fillText(`+${sisa}`, cx + 15, hgt / 2 + 0.5);
    cx += 30;
  } else cx += 8;
  ctx.fillStyle = o.sel ? "#fff" : ink; ctx.font = font(700, 14); ctx.textAlign = "left"; ctx.textBaseline = "middle";
  ctx.fillText(countLabel(t.jumlah_laporan), cx + 6, hgt / 2 + 0.5);
  ctx.restore();
}

function drawMarker(ctx: CanvasRenderingContext2D, t: Titik, x: number, y: number, st: { sel: boolean; sorot: boolean; redup: boolean }): void {
  ctx.save();
  ctx.globalAlpha = st.redup && !st.sel ? 0.3 : 1;
  drawPil(ctx, t, x, y, { sel: st.sel, skala: st.sel || st.sorot ? 1.1 : st.redup ? 0.9 : 1 });
  ctx.restore();
}

function drawCluster(ctx: CanvasRenderingContext2D, n: string, x: number, y: number, redup: boolean): void {
  ctx.save();
  ctx.globalAlpha = redup ? 0.35 : 1;
  ctx.shadowColor = "rgba(20,14,8,0.3)"; ctx.shadowBlur = 8; ctx.shadowOffsetY = 3;
  circle(ctx, x, y, 24); ctx.fillStyle = "rgba(255,255,255,0.92)"; ctx.fill();
  ctx.shadowColor = "transparent";
  circle(ctx, x, y, 21); ctx.fillStyle = css("--ink", "#1d1a17"); ctx.fill();
  ctx.fillStyle = "#fff"; ctx.textAlign = "center"; ctx.textBaseline = "middle";
  ctx.font = font(750, 14); ctx.fillText(n, x, y - 3);
  ctx.globalAlpha *= 0.78; ctx.font = font(600, 8.5); ctx.fillText("lokasi", x, y + 9);
  ctx.restore();
}

/** Legenda di pojok kiri bawah area peta; tinggi dihitung dari isinya. */
function drawLegend(ctx: CanvasRenderingContext2D, x0: number, yBottom: number, meta: PngMeta): void {
  const pad = 12, w = 260;
  const rows: { h: number; draw: (y: number) => void }[] = [];
  const ink = css("--ink", "#1d1a17"), ink2 = css("--ink-2", "#47413b"), ink3 = css("--ink-3", "#79716a");
  const chOp = parseFloat(css("--ch-op", "0.55"));
  const text = (t: string, x: number, y: number, w8: number, px: number, color: string) => { ctx.font = font(w8, px); ctx.fillStyle = color; ctx.textAlign = "left"; ctx.textBaseline = "alphabetic"; ctx.fillText(t, x, y); };
  rows.push({ h: 34, draw: (y) => { text("Jumlah kejadian bencana", x0 + pad, y + 15, 700, 12.5, ink); text("per kab/kota", x0 + pad, y + 30, 500, 11, ink3); } });
  rows.push({ h: 34, draw: (y) => {
    const sw = (w - pad * 2 - 4 * 3) / 5;
    KELAS.forEach((c, i) => {
      const sx = x0 + pad + i * (sw + 3);
      ctx.fillStyle = "#ebe8e2"; ctx.fillRect(sx, y + 4, sw, 11);
      ctx.globalAlpha = chOp; ctx.fillStyle = css(`--ch-${c.k}`, "#cd4b35"); ctx.fillRect(sx, y + 4, sw, 11); ctx.globalAlpha = 1;
      text(c.label, sx, y + 29, 600, 11, ink2);
    });
  } });
  rows.push({ h: 22, draw: (y) => {
    ctx.fillStyle = "#ebe8e2"; ctx.fillRect(x0 + pad, y + 5, 16, 10);
    ctx.globalAlpha = 0.32; ctx.fillStyle = css("--ch-0", "#b3a99c"); ctx.fillRect(x0 + pad, y + 5, 16, 10); ctx.globalAlpha = 1;
    text("0 sesuai filter", x0 + pad + 22, y + 14, 500, 11, ink3);
    ctx.strokeStyle = "rgba(70,58,46,0.28)"; ctx.lineWidth = 1; ctx.strokeRect(x0 + pad + 118.5, y + 5.5, 15, 9);
    text("Di luar cakupan data", x0 + pad + 140, y + 14, 500, 11, ink3);
  } });
  if (meta.kabMode) {
    const mk = (label: string, drawIc: (cx: number, cy: number) => void) => {
      ctx.font = font(500, 11);
      const lines = wrap(ctx, label, w - pad * 2 - 76);
      rows.push({ h: 6 + lines.length * 14, draw: (y) => { drawIc(x0 + pad, y + 10); lines.forEach((ln, i) => text(ln, x0 + pad + 76, y + 14 + i * 14, 500, 11, ink2)); } });
    };
    rows.push({ h: 22, draw: (y) => text("Penanda lokasi", x0 + pad, y + 16, 700, 11.5, ink) });
    const pil = (jenis: Jenis[], n: number, luar = false) => (cx: number, cy: number) =>
      drawPil(ctx, { jenis, jumlah_laporan: n, di_luar_kab: luar }, cx + (markerWidth({ jenis, jumlah_laporan: n } as Titik) * 0.62) / 2, cy, { skala: 0.62, bayang: false });
    mk(LEGENDA_PENANDA.satu, pil(["karhutla"], 12));
    mk(LEGENDA_PENANDA.ikon, pil(["karhutla", "banjir"], 9));
    mk(LEGENDA_PENANDA.banyak, pil(["karhutla", "banjir", "longsor", "gempa"], 31));
    mk(LEGENDA_PENANDA.luar, pil(["banjir"], 3, true));
    rows.push({ h: 22, draw: (y) => text("Jenis bencana", x0 + pad, y + 16, 700, 11.5, ink) });
    for (let i = 0; i < JENIS.length; i += 2) {
      const pair = JENIS.slice(i, i + 2);
      rows.push({ h: 19, draw: (y) => pair.forEach((j, k) => {
        const cx = x0 + pad + k * 118;
        circle(ctx, cx + 6, y + 8, 7); ctx.fillStyle = warna(j); ctx.fill(); drawIcon(ctx, `j_${j}` as IconName, cx + 1.5, y + 3.5, 9, "#fff");
        text(LABEL_PENDEK[j], cx + 17, y + 12, 550, 11, ink2);
      }) });
    }
  }
  const total = rows.reduce((a, r) => a + r.h, 0) + pad * 2 - 4;
  const y0 = yBottom - total;
  ctx.save();
  ctx.shadowColor = "rgba(30,22,14,0.18)"; ctx.shadowBlur = 14; ctx.shadowOffsetY = 4;
  ctx.beginPath(); ctx.roundRect(x0, y0, w, total, 10); ctx.fillStyle = "rgba(253,252,250,0.96)"; ctx.fill();
  ctx.restore();
  ctx.save();
  ctx.beginPath(); ctx.rect(x0, y0, w, total); ctx.clip();
  let y = y0 + pad - 4;
  for (const r of rows) { ctx.save(); r.draw(y); ctx.restore(); y += r.h; }
  ctx.restore();
}

function stamp(d: Date): string {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}-${p(d.getHours())}${p(d.getMinutes())}`;
}

export async function exportPng(view: MapView, crop: Crop, meta: PngMeta): Promise<PngResult> {
  view.clearHover();
  await idle(view);
  try { await document.fonts.ready; } catch { /* abaikan */ }
  const cont = view.map.getContainer().getBoundingClientRect();
  const W = Math.round(crop.w), MH = Math.round(crop.h);
  const scale = 2;
  // ---- ukur pita atas & bawah
  const probe = document.createElement("canvas").getContext("2d")!;
  probe.font = font(500, 11.5);
  const tilesState: { ok: boolean; bitmaps: { bmp: ImageBitmap; x: number; y: number; w: number; h: number }[] } = { ok: true, bitmaps: [] };
  const tileEls = [...view.tiles.getContainer()!.querySelectorAll<HTMLImageElement>("img.leaflet-tile")].filter((im) => im.complete && im.naturalWidth > 0);
  const vis = tileEls.map((im) => ({ im, r: im.getBoundingClientRect() }))
    .filter(({ r }) => r.right > cont.left + crop.x && r.left < cont.left + crop.x + crop.w && r.bottom > cont.top + crop.y && r.top < cont.top + crop.y + crop.h);
  const results = await Promise.allSettled(vis.map(({ im }) => fetchBitmap(im.currentSrc || im.src)));
  results.forEach((res, i) => {
    if (res.status === "fulfilled") { const r = vis[i].r; tilesState.bitmaps.push({ bmp: res.value, x: r.left - cont.left - crop.x, y: r.top - cont.top - crop.y, w: r.width, h: r.height }); }
    else tilesState.ok = false;
  });
  if (!vis.length) tilesState.ok = false;
  if (!tilesState.ok) { tilesState.bitmaps.forEach((b) => b.bmp.close()); tilesState.bitmaps = []; }

  const disclaimer = "Sumber data: laporan media sosial (X) yang diolah otomatis — bukan data resmi BNPB. Informasi yang tidak dilaporkan tidak berarti nol.";
  const attrib = tilesState.ok
    ? "Peta dasar © OpenStreetMap contributors (openstreetmap.org/copyright) · Batas wilayah: Kemendagri 2020 (disederhanakan)"
    : "Peta dasar OpenStreetMap tidak disertakan: server ubin tidak mengizinkan akses lintas-origin (CORS) atau tidak dapat dijangkau. Batas wilayah: Kemendagri 2020 (disederhanakan)";
  const when = new Date();
  const exported = `Diekspor ${when.toLocaleString("id-ID", { dateStyle: "medium", timeStyle: "short" })} · ${meta.dataset}`;
  const discLines = wrap(probe, disclaimer, W - 32);
  const footLines = [...discLines, ...wrap(probe, attrib, W - 32), ...wrap(probe, exported, W - 32)];
  probe.font = font(500, 12.5);
  const sub = [meta.wilayah, meta.lokasi ? `Lokasi: ${meta.lokasi}` : null, meta.periode, meta.jenis, meta.sorot ? `Disorot: ${meta.sorot}` : null].filter(Boolean).join(" · ");
  const subLines = wrap(probe, sub, W - 32 - (meta.contoh ? 110 : 0));
  const HH = 40 + subLines.length * 17 + 10, FH = 14 + footLines.length * 15 + 10;
  const H = HH + MH + FH;

  const canvas = document.createElement("canvas");
  canvas.width = W * scale; canvas.height = H * scale;
  const ctx = canvas.getContext("2d")!;
  ctx.scale(scale, scale);
  // ---- pita atas
  ctx.fillStyle = "#fdfcfa"; ctx.fillRect(0, 0, W, H);
  ctx.fillStyle = css("--ink", "#1d1a17"); ctx.font = font(750, 18); ctx.textBaseline = "alphabetic"; ctx.textAlign = "left";
  ctx.fillText("Peta Situasi Bencana", 16, 30);
  ctx.fillStyle = css("--ink-2", "#47413b"); ctx.font = font(500, 12.5);
  subLines.forEach((ln, i) => ctx.fillText(ln, 16, 50 + i * 17));
  if (meta.contoh) {
    ctx.font = font(650, 11.5);
    const t = "Data contoh", tw = ctx.measureText(t).width + 18;
    ctx.beginPath(); ctx.roundRect(W - 16 - tw, 14, tw, 22, 11); ctx.fillStyle = "#f5eee2"; ctx.fill();
    ctx.fillStyle = "#5b4726"; ctx.fillText(t, W - 16 - tw + 9, 29);
  }
  // ---- area peta
  ctx.save();
  ctx.translate(0, HH);
  ctx.beginPath(); ctx.rect(0, 0, W, MH); ctx.clip();
  ctx.fillStyle = "#e8e5df"; ctx.fillRect(0, 0, W, MH);
  if (tilesState.bitmaps.length) {
    const cs = getComputedStyle(view.tiles.getContainer()!);
    ctx.save();
    ctx.globalAlpha = parseFloat(cs.opacity || "1");
    if (cs.filter && cs.filter !== "none") ctx.filter = cs.filter;
    for (const b of tilesState.bitmaps) ctx.drawImage(b.bmp, b.x, b.y, b.w, b.h);
    ctx.restore();
    tilesState.bitmaps.forEach((b) => b.bmp.close());
  }
  const origin = { x: cont.left + crop.x, y: cont.top + crop.y };
  for (const name of ["kab", "prov", "kabSel"]) drawPane(ctx, view.map.getPane(name), origin);
  const sel = view.selection;
  for (const el of view.map.getPane("markerPane")!.querySelectorAll<HTMLElement>(".leaflet-marker-icon")) {
    const r = el.getBoundingClientRect();
    const x = r.left + r.width / 2 - origin.x, y = r.top + r.height / 2 - origin.y;
    if (x < -40 || y < -40 || x > W + 40 || y > MH + 40) continue;
    const cl = el.querySelector(".pm-cluster b");
    if (cl) { drawCluster(ctx, cl.textContent ?? "", x, y, el.classList.contains("is-redup")); continue; }
    const gid = el.dataset.gid, t = gid ? view.titikOf(gid) : null;
    if (t) drawMarker(ctx, t, x, y, { sel: gid === sel.titik, sorot: !!sel.sorot?.has(gid!), redup: !!sel.sorot && !sel.sorot.has(gid!) });
  }
  drawLegend(ctx, 12, MH - 12, meta);
  ctx.restore();
  // ---- pita bawah
  ctx.fillStyle = "#fdfcfa"; ctx.fillRect(0, HH + MH, W, FH);
  ctx.fillStyle = "rgba(45,36,28,0.12)"; ctx.fillRect(0, HH + MH, W, 1); ctx.fillRect(0, HH - 1, W, 1);
  ctx.font = font(500, 11.5); ctx.textAlign = "left";
  footLines.forEach((ln, i) => { ctx.fillStyle = i < discLines.length ? css("--ink", "#1d1a17") : css("--ink-3", "#79716a"); ctx.fillText(ln, 16, HH + MH + 22 + i * 15); });

  const blob = await new Promise<Blob>((res, rej) => canvas.toBlob((b) => (b ? res(b) : rej(new Error("Gambar tidak dapat dibuat"))), "image/png"));
  return { blob, filename: `peta-situasi-bencana_${meta.slug}_${stamp(when)}.png`, peta: tilesState.ok ? "lengkap" : "tanpa-peta-dasar" };
}
