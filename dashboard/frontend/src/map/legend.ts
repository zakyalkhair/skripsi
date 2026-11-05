import { h } from "../dom";
import { JENIS, LABEL_PENDEK } from "../jenis";
import { ico } from "../ui/icons";
import { arcPath, ringSegments } from "./marker";

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
  satu: "Satu penanda = satu lokasi; angka = jumlah laporan yang menyebutnya",
  segmen: "Segmen sama besar = jenis yang dilaporkan",
  gunung: "Gunung",
  luar: "Lokasi rujukan di kab/kota lain (bukan lokasi kejadian)",
};

export interface Legend { el: HTMLElement; update(ctx: string, kabMode: boolean): void; setOpen(open: boolean): void }

/** Contoh penanda mini (SVG) — bentuk sama dengan penanda peta. */
function mini(kind: "ring" | "multi" | "gunung" | "luar"): HTMLElement {
  const el = h("span", { class: "lg-mini", "aria-hidden": "true" });
  const ringOne = '<circle cx="11" cy="11" r="8" fill="#fff"/><circle cx="11" cy="11" r="6.2" fill="none" stroke="var(--ink-2)" stroke-width="3"/>';
  const svg = {
    ring: ringOne,
    multi: '<circle cx="11" cy="11" r="8" fill="#fff"/>' + ringSegments(3).map(([a, b], i) =>
      `<path d="${arcPath(11, 11, 6.2, a, b)}" fill="none" stroke="var(--j-${(["banjir", "longsor", "cuaca"] as const)[i]})" stroke-width="3"/>`).join(""),
    gunung: '<path d="M11 3.5 L19 18 L3 18 Z" fill="var(--ink-2)" stroke="#fff" stroke-width="1.4" stroke-linejoin="round"/>',
    luar: `<circle cx="11" cy="11" r="10" class="pm-luar-ring" style="stroke-width:1.4;stroke-dasharray:2.6 2"/>${ringOne.replace('r="8"', 'r="6.8"').replace('r="6.2"', 'r="5"').replace('stroke-width="3"', 'stroke-width="2.4"')}`,
  }[kind];
  el.innerHTML = `<svg viewBox="0 0 22 22" width="20" height="20">${svg}</svg>`;
  return el;
}

export function buildLegend(onToggle: (open: boolean) => void): Legend {
  const ctx = h("p", { class: "lg-ctx" });
  const jenis = h("div", { class: "lg-jenis", role: "list", "aria-label": "Warna jenis bencana" },
    ...JENIS.map((j) => h("span", { class: "lg-jn", role: "listitem" }, h("i", { style: `background: var(--j-${j})`, "aria-hidden": "true" }), LABEL_PENDEK[j])));
  const markers = h("div", { class: "lg-markers", hidden: true },
    h("p", { class: "lg-sub" }, "Penanda lokasi"),
    h("div", { class: "lg-mk" }, mini("ring"), LEGENDA_PENANDA.satu),
    h("div", { class: "lg-mk" }, mini("multi"), LEGENDA_PENANDA.segmen),
    h("div", { class: "lg-mk" }, mini("gunung"), LEGENDA_PENANDA.gunung),
    h("div", { class: "lg-mk lg-mk--luar" }, mini("luar"), LEGENDA_PENANDA.luar),
    h("p", { class: "lg-sub" }, "Jenis bencana"), jenis);
  const body = h("div", { class: "lg-body", id: "lg-body" },
    h("div", { class: "lg-scale", role: "list", "aria-label": "Kelas jumlah kejadian" },
      ...KELAS.map((c) => h("div", { class: "lg-step", role: "listitem", "aria-label": `${c.label} kejadian` },
        h("span", { class: "lg-sw", "data-k": c.k }), h("span", { class: "lg-n" }, c.label)))),
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
