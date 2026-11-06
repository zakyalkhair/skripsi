import { h } from "../dom";
import { JENIS, LABEL_PENDEK } from "../jenis";
import { ico, type IconName } from "../ui/icons";
import { markerHtml } from "./marker";
import { onPreview } from "../ui/preview";
import type { Jenis, Titik } from "../types";

/** Kelas jumlah tetap (bukan kuantil): stabil saat filter berubah, cocok untuk data sangat jarang. */
export const KELAS = [
  { k: 1, label: "1", min: 1, max: 1 },
  { k: 2, label: "2", min: 2, max: 2 },
  { k: 3, label: "3", min: 3, max: 3 },
  { k: 4, label: "4–5", min: 4, max: 5 },
  { k: 5, label: "≥6", min: 6, max: Infinity },
];
export const kelasOf = (n: number): number => (n <= 0 ? 0 : KELAS.find((c) => n >= c.min && n <= c.max)!.k);

/** Teks legenda penanda — dipakai juga oleh ekspor PNG agar keduanya selalu sama. */
export const LEGENDA_PENANDA = {
  satu: "Satu lokasi; angka = jumlah laporan",
  ikon: "Ikon & warna = jenis bencana",
  banyak: "≥4 jenis: 2 ikon + sisanya",
  luar: "Lokasi rujukan di kab/kota lain (bukan lokasi kejadian)",
};

export interface Legend { el: HTMLElement; update(ctx: string, kabMode: boolean): void; setOpen(open: boolean): void }

/** Contoh penanda mini — markup sama dengan penanda peta. */
function mini(jenis: Jenis[], n: number, luar = false): HTMLElement {
  const el = h("span", { class: "lg-mini lg-mini--pil", "aria-hidden": "true" });
  el.innerHTML = markerHtml({ jenis, jumlah_laporan: n, di_luar_kab: luar, tingkat: "desa" } as Titik);
  return el;
}

const withPv = <T extends HTMLElement>(el: T, on: () => void, off: () => void): T => { onPreview(el, on, off); return el; };

export interface LegendPreview { kelas(k: number | null): void; jenis(j: Jenis | null): void }

export function buildLegend(onToggle: (open: boolean) => void, pv?: LegendPreview): Legend {
  const ctx = h("p", { class: "lg-ctx" });
  const jenis = h("div", { class: "lg-jenis", role: "list", "aria-label": "Warna jenis bencana" },
    ...JENIS.map((j) => withPv(h("span", { class: "lg-jn", role: "listitem" }, h("span", { class: "lg-jic", style: `--jc: var(--j-${j})`, "aria-hidden": "true" }, ico(`j_${j}` as IconName, 12)), LABEL_PENDEK[j]), () => pv?.jenis(j), () => pv?.jenis(null))));
  const markers = h("div", { class: "lg-markers", hidden: true },
    h("p", { class: "lg-sub" }, "Penanda lokasi"),
    h("div", { class: "lg-mk" }, mini(["karhutla"], 12), LEGENDA_PENANDA.satu),
    h("div", { class: "lg-mk" }, mini(["karhutla", "banjir"], 9), LEGENDA_PENANDA.ikon),
    h("div", { class: "lg-mk" }, mini(["karhutla", "banjir", "longsor", "gempa"], 31), LEGENDA_PENANDA.banyak),
    h("div", { class: "lg-mk lg-mk--luar" }, mini(["banjir"], 3, true), LEGENDA_PENANDA.luar),
    h("p", { class: "lg-sub" }, "Jenis bencana"), jenis);
  const body = h("div", { class: "lg-body", id: "lg-body" },
    h("div", { class: "lg-scale", role: "list", "aria-label": "Kelas jumlah kejadian" },
      ...KELAS.map((c) => withPv(h("div", { class: "lg-step", role: "listitem", "aria-label": `${c.label} kejadian` },
        h("span", { class: "lg-sw", "data-k": c.k }), h("span", { class: "lg-n" }, c.label)), () => pv?.kelas(c.k), () => pv?.kelas(null)))),
    h("div", { class: "lg-extra" },
      h("span", { class: "lg-item" }, h("span", { class: "lg-sw lg-sw--0" }), "0 sesuai filter"),
      h("span", { class: "lg-item" }, h("span", { class: "lg-sw lg-sw--na" }), "Di luar cakupan data")),
    h("p", { class: "lg-note" }, "Warna menunjukkan banyaknya kejadian, bukan tingkat keparahan."),
    ctx, markers);
  const collapse = h("button", { type: "button", class: "icon-btn lg-min", "aria-label": "Sembunyikan legenda", title: "Sembunyikan legenda",
    "aria-controls": "lg-body", "aria-expanded": "true", onclick: () => onToggle(false) }, ico("chevDown", 16));
  const card = h("section", { class: "legend float-card", "aria-label": "Legenda peta" },
    h("header", { class: "lg-head" },
      h("div", {}, h("h2", { class: "lg-title" }, "Jumlah kejadian bencana"), h("p", { class: "lg-unit" }, "per kab/kota")), collapse),
    body);
  const pill = h("button", { type: "button", class: "pill lg-pill", "aria-label": "Tampilkan legenda", "aria-expanded": "false",
    onclick: () => onToggle(true) }, h("span", { class: "lg-pill-sw", "aria-hidden": "true" }), "Legenda", ico("chevUp", 14));
  const el = h("div", { class: "legend-wrap" }, card, pill);
  return {
    el,
    update(text, kabMode) {
      ctx.textContent = text;
      markers.hidden = !kabMode;
      card.classList.toggle("is-kab", kabMode);
    },
    setOpen(open) {
      el.classList.toggle("is-collapsed", !open);
      card.inert = !open;
      pill.inert = open;
      collapse.setAttribute("aria-expanded", String(open));
    },
  };
}
