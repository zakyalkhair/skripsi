import { h } from "../dom";
import { ico } from "../ui/icons";

/** Kelas jumlah tetap (bukan kuantil): stabil saat filter berubah, cocok untuk data sangat jarang. */
export const KELAS = [
  { k: 1, label: "1", min: 1, max: 1 },
  { k: 2, label: "2", min: 2, max: 2 },
  { k: 3, label: "3", min: 3, max: 3 },
  { k: 4, label: "4–5", min: 4, max: 5 },
  { k: 5, label: "≥6", min: 6, max: Infinity },
];
export const kelasOf = (n: number): number => (n <= 0 ? 0 : KELAS.find((c) => n >= c.min && n <= c.max)!.k);

export interface Legend { el: HTMLElement; update(ctx: string, kabMode: boolean): void; setOpen(open: boolean): void }

export function buildLegend(onToggle: (open: boolean) => void): Legend {
  const ctx = h("p", { class: "lg-ctx" });
  const markers = h("div", { class: "lg-markers", hidden: true },
    h("p", { class: "lg-sub" }, "Penanda lokasi"),
    h("div", { class: "lg-mk" }, h("span", { class: "lg-ring", "aria-hidden": "true" }), "Satu penanda = satu lokasi; angka = jumlah laporan"),
    h("div", { class: "lg-mk" }, h("span", { class: "lg-ring lg-ring--multi", "aria-hidden": "true" }), "Segmen sama besar = jenis yang dilaporkan"),
    h("div", { class: "lg-mk" }, h("span", { class: "lg-tri", "aria-hidden": "true" }), "Gunung"),
    h("div", { class: "lg-mk" }, h("span", { class: "lg-ring lg-ring--luar", "aria-hidden": "true" }), "Lokasi di kab/kota lain yang dirujuk"));
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
