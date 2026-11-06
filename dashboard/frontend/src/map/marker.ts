import type { Jenis, Titik } from "../types";
import { LABEL_PENDEK, TINGKAT_LABEL } from "../jenis";
import { esc } from "../dom";
import { rentang, plural } from "../format";

import { iconSvg, type IconName } from "../ui/icons";

/** Penanda lokasi berbentuk pil (desain Figma "opsi ikon + warna"): lingkar ikon jenis berwarna + angka laporan.
 *  ≤3 jenis: semua ikon tampil; ≥4 jenis: 2 ikon pertama + chip "+N". */
export const IC = 22, OVERLAP = 7, PAD = 3, GAP = 5, PAD_R = 8, PLUS_W = 26;
export const MK_H = 30;

export function ikonTampil(jenis: Jenis[]): { tampil: Jenis[]; sisa: number } {
  return jenis.length <= 3 ? { tampil: jenis, sisa: 0 } : { tampil: jenis.slice(0, 2), sisa: jenis.length - 2 };
}

export const countLabel = (n: number): string => (n > 99 ? "99+" : String(n));

/** Lebar pil (px) — dipakai Leaflet (iconSize) & ekspor PNG agar sama dengan tampilan. */
export function markerWidth(t: Titik): number {
  const { tampil, sisa } = ikonTampil(t.jenis.length ? t.jenis : ["banjir"]);
  const n = tampil.length + (sisa ? 1 : 0);
  const icons = IC * n - OVERLAP * (n - 1) + (sisa ? PLUS_W - IC : 0);
  return PAD + icons + GAP + countLabel(t.jumlah_laporan).length * 7.8 + PAD_R;
}

export function markerKey(t: Titik): string {
  return `${t.jenis.join(",")}|${t.jumlah_laporan}|${t.di_luar_kab ? 1 : 0}|${t.tingkat}`;
}

export function markerHtml(t: Titik): string {
  const { tampil, sisa } = ikonTampil(t.jenis);
  const ics = tampil.map((j) => `<span class="pm-ic" style="--jc:var(--j-${j})">${iconSvg(`j_${j}` as IconName, 13)}</span>`).join("")
    + (sisa ? `<span class="pm-ic pm-ic--plus">+${sisa}</span>` : "");
  const cls = `pm-mk${t.tingkat === "gunung" ? " pm-mk--gunung" : ""}${t.di_luar_kab ? " is-luar" : ""}`;
  return `<span class="${cls}"><span class="pm-ics">${ics}</span><span class="pm-count">${countLabel(t.jumlah_laporan)}</span></span>`;
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
    <div class="tt-sub">${esc(TINGKAT_LABEL[t.tingkat] ?? t.tingkat)} | ${rentang(t.tanggal_awal, t.tanggal_akhir)}</div>
    <div class="tt-lead"><b>${t.jumlah_laporan}</b> Unggahan X yang dilaporkan</div>
    <div class="tt-jenis">${jenis}</div>${luar}<div class="tt-hint">Klik untuk melihat rincian</div>`;
}
