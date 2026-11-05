import { h, icon } from "../dom";
import { JENIS, LABEL, LABEL_PENDEK } from "../jenis";
import type { Store } from "../store";
import { isDefaultFilter } from "../store";
import type { Wilayah } from "../types";
import { Combobox } from "./combobox";

export function buildFilters(store: Store, onKab: (kode: string | null) => void) {
  const chips = JENIS.map((j) =>
    h("button", { type: "button", class: "chip", "data-jenis": j, "aria-pressed": "true", title: LABEL[j],
      onclick: () => {
        const next = new Set(store.state.jenis);
        next.has(j) ? next.delete(j) : next.add(j);
        store.set({ jenis: next });
      } },
      h("span", { class: "chip-dot", style: `--c: var(--j-${j})`, "aria-hidden": "true" }), LABEL_PENDEK[j]));
  const semua = h("button", { type: "button", class: "chip chip--all", "aria-pressed": "true",
    onclick: () => store.set({ jenis: store.state.jenis.size === JENIS.length ? new Set() : new Set(JENIS) }) }, "Semua jenis");
  const reset = h("button", { type: "button", class: "btn btn--ghost", disabled: true,
    onclick: () => store.set({ jenis: new Set(JENIS), dari: null, sampai: null }) },
    icon("btn-ic", '<path d="M3 8a5 5 0 1 0 1.6-3.7M3 2.5v3h3" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>'), "Atur ulang filter");
  const combo = new Combobox("kab-combo", "Kabupaten/kota", "Cari kab/kota…", onKab);
  const status = h("span", { class: "filter-status", "aria-live": "polite" });

  const el = h("div", { class: "filterbar", role: "region", "aria-label": "Filter data" },
    h("div", { class: "fgroup" },
      h("span", { class: "flabel", id: "lbl-jenis" }, "Jenis bencana"),
      h("div", { class: "chips", role: "group", "aria-labelledby": "lbl-jenis" }, semua, ...chips)),
    h("div", { class: "fgroup fgroup--kab" }, h("label", { class: "flabel", for: "kab-combo-input" }, "Wilayah"), combo.el),
    h("div", { class: "fgroup fgroup--end" }, status, reset));

  function sync(): void {
    const s = store.state;
    chips.forEach((c) => c.setAttribute("aria-pressed", String(s.jenis.has(c.dataset.jenis as never))));
    semua.setAttribute("aria-pressed", String(s.jenis.size === JENIS.length));
    semua.classList.toggle("is-partial", s.jenis.size > 0 && s.jenis.size < JENIS.length);
    reset.disabled = isDefaultFilter(s);
    const n = (s.jenis.size < JENIS.length ? 1 : 0) + (s.dari || s.sampai ? 1 : 0);
    status.textContent = n ? `${n} filter aktif` : "";
    reset.setAttribute("aria-label", n ? `Atur ulang filter (${n} aktif)` : "Atur ulang filter");
    combo.setValue(s.kab);
  }
  return { el, sync, setWilayah: (w: Wilayah) => combo.setOptions(w.kab) };
}
