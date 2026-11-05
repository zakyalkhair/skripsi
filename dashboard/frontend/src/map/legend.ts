import { h } from "../dom";

/** Kelas jumlah tetap (bukan kuantil): stabil saat filter berubah, cocok untuk data sangat jarang. */
export const KELAS = [
  { k: 1, label: "1", min: 1, max: 1 },
  { k: 2, label: "2", min: 2, max: 2 },
  { k: 3, label: "3", min: 3, max: 3 },
  { k: 4, label: "4–5", min: 4, max: 5 },
  { k: 5, label: "≥ 6", min: 6, max: Infinity },
];
export const kelasOf = (n: number): number => (n <= 0 ? 0 : KELAS.find((c) => n >= c.min && n <= c.max)!.k);

export function buildLegend(): { el: HTMLElement; update(ctx: string, kabMode: boolean): void } {
  const ctx = h("p", { class: "lg-ctx" });
  const markers = h("div", { class: "lg-markers", hidden: true },
    h("div", { class: "lg-title" }, "Penanda lokasi"),
    h("div", { class: "lg-mk" }, h("span", { class: "lg-ring", "aria-hidden": "true" }), "Satu penanda = satu lokasi; angka = jumlah laporan"),
    h("div", { class: "lg-mk" }, h("span", { class: "lg-ring lg-ring--multi", "aria-hidden": "true" }), "Segmen sama besar = jenis yang dilaporkan (bukan proporsi)"),
    h("div", { class: "lg-mk" }, h("span", { class: "lg-tri", "aria-hidden": "true" }), "Gunung"),
    h("div", { class: "lg-mk" }, h("span", { class: "lg-ring lg-ring--luar", "aria-hidden": "true" }), "Lokasi di kab/kota lain yang dirujuk"),
  );
  const body = h("div", { class: "lg-body", id: "lg-body" });
  const toggle = h("button", { type: "button", class: "lg-toggle", "aria-expanded": "true", "aria-controls": "lg-body",
    onclick: () => { const open = toggle.getAttribute("aria-expanded") !== "true"; toggle.setAttribute("aria-expanded", String(open)); body.hidden = !open; } },
    h("span", { class: "lg-title" }, "Jumlah kejadian bencana", h("span", { class: "lg-unit" }, " per kab/kota")), h("span", { class: "lg-chev", "aria-hidden": "true" }, "▾"));
  const el = h("section", { class: "legend", "aria-label": "Legenda peta" }, toggle, body);
  body.append(
    h("div", { class: "lg-scale", role: "list" },
      ...KELAS.map((c) => h("div", { class: "lg-step", role: "listitem" }, h("span", { class: "lg-sw", "data-k": c.k }), h("span", { class: "lg-n" }, c.label)))),
    h("div", { class: "lg-extra" },
      h("span", { class: "lg-item" }, h("span", { class: "lg-sw", "data-k": 0 }), "0 sesuai filter"),
      h("span", { class: "lg-item" }, h("span", { class: "lg-sw lg-sw--na" }), "Di luar cakupan data")),
    ctx, markers);
  if (window.innerWidth < 600) { toggle.setAttribute("aria-expanded", "false"); body.hidden = true; }
  return {
    el,
    update(text, kabMode) {
      ctx.textContent = text;
      markers.hidden = !kabMode;
      el.classList.toggle("is-kab", kabMode);
    },
  };
}
