import type { Jenis, Titik } from "../types";
import { LABEL_PENDEK, TINGKAT_LABEL } from "../jenis";
import { esc } from "../dom";
import { rentang, plural } from "../format";

const R = 15; // radius luar (px); ukuran layar konstan pada semua zoom
/** Cincin putus-putus lokasi rujukan (lokasi di luar kab/kota terpilih). Dipakai juga oleh legenda & ekspor PNG. */
export const LUAR_R = 19.5;
export const MK_SIZE = 34;

export function arcPath(cx: number, cy: number, r: number, a0: number, a1: number): string {
  const p = (a: number) => [cx + r * Math.sin(a), cy - r * Math.cos(a)];
  const [x0, y0] = p(a0), [x1, y1] = p(a1);
  return `M${x0.toFixed(2)} ${y0.toFixed(2)}A${r} ${r} 0 ${a1 - a0 > Math.PI ? 1 : 0} 1 ${x1.toFixed(2)} ${y1.toFixed(2)}`;
}

/** Sudut segmen cincin SAMA BESAR (hanya mengodekan kehadiran jenis, bukan proporsi). */
export function ringSegments(n: number): [number, number][] {
  if (n <= 1) return [[0, Math.PI * 2]];
  const gap = 0.16, step = (Math.PI * 2) / n;
  return Array.from({ length: n }, (_, i) => [i * step + gap / 2, (i + 1) * step - gap / 2] as [number, number]);
}

function ring(jenis: Jenis[], cx: number, cy: number, r: number, w: number): string {
  if (jenis.length === 1) return `<circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="var(--j-${jenis[0]})" stroke-width="${w}"/>`;
  return ringSegments(jenis.length).map(([a, b], i) =>
    `<path d="${arcPath(cx, cy, r, a, b)}" fill="none" stroke="var(--j-${jenis[i]})" stroke-width="${w}" stroke-linecap="butt"/>`).join("");
}

/** Siluet gunung (segitiga); bila beberapa jenis: garis vertikal sama lebar. */
export const GUNUNG_PATH = "M17 4.5 L30 28 Q30.6 29.5 29 29.5 L5 29.5 Q3.4 29.5 4 28 Z";
function triangle(jenis: Jenis[]): string {
  const id = `g${Math.random().toString(36).slice(2, 8)}`;
  const stops = jenis.map((j, i) => {
    const a = (i / jenis.length) * 100, b = ((i + 1) / jenis.length) * 100;
    return `<stop offset="${a}%" stop-color="var(--j-${j})"/><stop offset="${b}%" stop-color="var(--j-${j})"/>`;
  }).join("");
  return `<defs><linearGradient id="${id}" x1="0" x2="1" y1="0" y2="0">${stops}</linearGradient></defs>
    <path d="${GUNUNG_PATH}" fill="url(#${id})" stroke="var(--surface)" stroke-width="2.2" stroke-linejoin="round"/>
    <path d="M12.6 12.4 L17 9.2 L21.4 12.4" fill="none" stroke="rgba(255,255,255,.75)" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>`;
}

/** Cincin rujukan: lingkaran putus-putus di LUAR bentuk asli (bentuk & warna jenis tetap). */
const luarRing = () => `<circle cx="17" cy="17" r="${LUAR_R}" class="pm-luar-ring"/>`;

export function markerKey(t: Titik): string {
  return `${t.jenis.join(",")}|${t.jumlah_laporan}|${t.di_luar_kab ? 1 : 0}|${t.tingkat}`;
}

export const countLabel = (n: number): string => (n > 99 ? "99+" : String(n));

export function markerHtml(t: Titik): string {
  const label = countLabel(t.jumlah_laporan);
  const luar = t.di_luar_kab;
  if (t.tingkat === "gunung") {
    return `<span class="pm-mk pm-mk--gunung${luar ? " is-luar" : ""}">
      <svg viewBox="0 0 34 34" width="34" height="34" aria-hidden="true">${luar ? luarRing() : ""}${triangle(t.jenis)}</svg>
      <span class="pm-badge">${label}</span></span>`;
  }
  return `<span class="pm-mk${luar ? " is-luar" : ""}">
    <svg viewBox="0 0 34 34" width="34" height="34" aria-hidden="true">${luar ? luarRing() : ""}
      <circle cx="17" cy="17" r="${R + 1}" class="pm-halo"/>
      ${ring(t.jenis, 17, 17, R - 2.5, 5)}
      <circle cx="17" cy="17" r="${R - 5.5}" class="pm-core"/>
      <text x="17" y="17" class="pm-count" text-anchor="middle" dominant-baseline="central">${label}</text>
    </svg></span>`;
}

/** Kalimat baku lokasi rujukan (tooltip, panel, label aksesibel). */
export function kalimatRujukan(kabLokasi: string | null, kabTerpilih: string | null): string {
  return `Lokasi berada di ${kabLokasi ?? "kab/kota lain"}, tetapi dirujuk dalam laporan terkait ${kabTerpilih ?? "wilayah terpilih"}.`;
}

export function markerAria(t: Titik, kabTerpilih: string | null): string {
  const jenis = t.jenis.map((j) => LABEL_PENDEK[j]).join(", ");
  const dasar = `${t.nama}, ${TINGKAT_LABEL[t.tingkat] ?? t.tingkat}. ${plural(t.jumlah_laporan, "laporan")} menyebut lokasi ini: ${jenis}.`;
  return t.di_luar_kab ? `${dasar} Lokasi rujukan. ${kalimatRujukan(t.nama_kab_lokasi, kabTerpilih)}` : dasar;
}

export function markerTooltip(t: Titik, kabTerpilih: string | null): string {
  const jenis = t.jenis.map((j) => `<span class="tt-j"><i style="background:var(--j-${j})"></i>${LABEL_PENDEK[j]}</span>`).join("");
  const luar = t.di_luar_kab
    ? `<div class="tt-note"><span class="tt-tag">Lokasi rujukan</span>${esc(kalimatRujukan(t.nama_kab_lokasi, kabTerpilih))}</div>` : "";
  return `<div class="tt-title">${esc(t.nama)}</div>
    <div class="tt-sub">${esc(TINGKAT_LABEL[t.tingkat] ?? t.tingkat)} · ${rentang(t.tanggal_awal, t.tanggal_akhir)}</div>
    <div class="tt-row"><span>Laporan yang menyebut lokasi ini</span><b>${t.jumlah_laporan}</b></div>
    <div class="tt-jenis">${jenis}</div>${luar}<div class="tt-hint">Klik untuk melihat rincian</div>`;
}
