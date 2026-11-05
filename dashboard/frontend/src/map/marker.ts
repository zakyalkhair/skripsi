import type { Jenis, Titik } from "../types";
import { LABEL_PENDEK } from "../jenis";
import { esc } from "../dom";
import { rentang, plural } from "../format";
import { TINGKAT_LABEL } from "../jenis";

const R = 15; // radius luar (px); ukuran layar konstan pada semua zoom

function arc(cx: number, cy: number, r: number, a0: number, a1: number): string {
  const p = (a: number) => [cx + r * Math.sin(a), cy - r * Math.cos(a)];
  const [x0, y0] = p(a0), [x1, y1] = p(a1);
  return `M${x0.toFixed(2)} ${y0.toFixed(2)}A${r} ${r} 0 ${a1 - a0 > Math.PI ? 1 : 0} 1 ${x1.toFixed(2)} ${y1.toFixed(2)}`;
}

/** Cincin bersegmen SAMA BESAR: hanya mengodekan kehadiran jenis, bukan proporsi. */
function ring(jenis: Jenis[], cx: number, cy: number, r: number, w: number): string {
  if (jenis.length === 1) return `<circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="var(--j-${jenis[0]})" stroke-width="${w}"/>`;
  const gap = 0.16, step = (Math.PI * 2) / jenis.length;
  return jenis.map((j, i) => `<path d="${arc(cx, cy, r, i * step + gap / 2, (i + 1) * step - gap / 2)}" fill="none" stroke="var(--j-${j})" stroke-width="${w}" stroke-linecap="butt"/>`).join("");
}

function triangle(jenis: Jenis[]): string {
  // siluet gunung; bila beberapa jenis, garis-garis vertikal sama lebar
  const id = `g${Math.random().toString(36).slice(2, 8)}`;
  const stops = jenis.map((j, i) => {
    const a = (i / jenis.length) * 100, b = ((i + 1) / jenis.length) * 100;
    return `<stop offset="${a}%" stop-color="var(--j-${j})"/><stop offset="${b}%" stop-color="var(--j-${j})"/>`;
  }).join("");
  return `<defs><linearGradient id="${id}" x1="0" x2="1" y1="0" y2="0">${stops}</linearGradient></defs>
    <path d="M17 4.5 L30 28 Q30.6 29.5 29 29.5 L5 29.5 Q3.4 29.5 4 28 Z" fill="url(#${id})" stroke="var(--surface)" stroke-width="2.2" stroke-linejoin="round"/>
    <path d="M12.6 12.4 L17 9.2 L21.4 12.4" fill="none" stroke="rgba(255,255,255,.75)" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>`;
}

export function markerKey(t: Titik): string {
  return `${t.jenis.join(",")}|${t.jumlah_laporan}|${t.di_luar_kab ? 1 : 0}|${t.tingkat}`;
}

export function markerHtml(t: Titik): string {
  const n = t.jumlah_laporan;
  const label = n > 99 ? "99+" : String(n);
  if (t.tingkat === "gunung") {
    return `<span class="pm-mk pm-mk--gunung${t.di_luar_kab ? " is-luar" : ""}">
      <svg viewBox="0 0 34 34" width="34" height="34" aria-hidden="true">${triangle(t.jenis)}</svg>
      <span class="pm-badge">${label}</span></span>`;
  }
  return `<span class="pm-mk${t.di_luar_kab ? " is-luar" : ""}">
    <svg viewBox="0 0 34 34" width="34" height="34" aria-hidden="true">
      <circle cx="17" cy="17" r="${R + 1}" class="pm-halo"/>
      ${ring(t.jenis, 17, 17, R - 2.5, 5)}
      <circle cx="17" cy="17" r="${R - 5.5}" class="pm-core"/>
      <text x="17" y="17" class="pm-count" text-anchor="middle" dominant-baseline="central">${label}</text>
    </svg></span>`;
}

export function markerAria(t: Titik): string {
  return `${t.nama}, ${TINGKAT_LABEL[t.tingkat] ?? t.tingkat}. ${plural(t.jumlah_laporan, "laporan kejadian")}: ${t.jenis.map((j) => LABEL_PENDEK[j]).join(", ")}.`;
}

export function markerTooltip(t: Titik): string {
  const jenis = t.jenis.map((j) => `<span class="tip-j"><i style="background:var(--j-${j})"></i>${LABEL_PENDEK[j]}</span>`).join("");
  const luar = t.di_luar_kab
    ? `<div class="tip-note">Terletak di ${esc(t.nama_kab_lokasi ?? "kab/kota lain")}; dirujuk oleh laporan dari wilayah ini.</div>` : "";
  return `<div class="tip-title">${esc(t.nama)}</div>
    <div class="tip-sub">${esc(TINGKAT_LABEL[t.tingkat] ?? t.tingkat)}</div>
    <div class="tip-row"><span>Laporan kejadian</span><b>${t.jumlah_laporan}</b></div>
    <div class="tip-jenis">${jenis}</div>
    <div class="tip-meta">${rentang(t.tanggal_awal, t.tanggal_akhir)}</div>${luar}`;
}
