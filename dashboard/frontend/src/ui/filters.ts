import { h } from "../dom";
import { JENIS, LABEL, LABEL_PENDEK } from "../jenis";
import type { Store } from "../store";
import { isDefaultFilter } from "../store";
import type { Jenis, Wilayah } from "../types";
import { Combobox } from "./combobox";
import { DateRange } from "./daterange";
import { ico } from "./icons";

const SINGKAT: Record<Jenis, string> = { banjir: "Banjir", longsor: "Longsor", cuaca: "Cuaca", karhutla: "Karhutla", gempa: "Gempa", erupsi: "Erupsi" };

/** Bilah filter mengambang: jenis bencana · wilayah · periode · atur ulang. */
export function buildToolbar(store: Store, onKab: (kode: string | null) => void) {
  // Chip teks saja: warna jenis (token --j-*) hanya muncul pada chip terpilih. data-text dipakai CSS untuk
  // mencadangkan lebar huruf tebal sehingga memilih/melepas tidak menggeser tata letak.
  const label = (cls: string, t: string, hidden = false) => h("span", { class: cls, "data-text": t, "aria-hidden": hidden ? "true" : null }, t);
  const chips = JENIS.map((j) =>
    h("button", { type: "button", class: "chip", "data-jenis": j, "aria-pressed": "true", title: LABEL[j], "aria-label": LABEL[j],
      style: `--c: var(--j-${j})`,
      onclick: () => {
        const next = new Set(store.state.jenis);
        next.has(j) ? next.delete(j) : next.add(j);
        store.set({ jenis: next });
      } }, label("chip-l", LABEL_PENDEK[j]), label("chip-s", SINGKAT[j], true)));
  // "Semua": bila belum semua aktif → pilih semua; bila sudah semua aktif → lepas semua (pilihan kosong).
  const semua = h("button", { type: "button", class: "chip chip--all", "aria-pressed": "true", "aria-label": "Semua jenis bencana",
    title: "Pilih / lepas semua jenis bencana", onclick: () => store.set({ jenis: store.state.jenis.size === JENIS.length ? new Set() : new Set(JENIS) }) },
    label("chip-a", "Semua"));
  const combo = new Combobox("kab-combo", "Kabupaten/kota", "Cari kab/kota…", onKab);
  const date = new DateRange((dari, sampai) => store.set({ dari, sampai }));
  const reset = h("button", { type: "button", class: "tb-reset", disabled: true,
    onclick: () => store.set({ jenis: new Set(JENIS), dari: null, sampai: null }) }, ico("reset", 15), h("span", {}, "Atur ulang"));
  const count = h("span", { class: "tb-count", hidden: true });
  const more = h("button", { type: "button", class: "tb-more", "aria-expanded": "false", "aria-controls": "tb-extra",
    onclick: () => setOpen(more.getAttribute("aria-expanded") !== "true") }, ico("sliders", 16), h("span", {}, "Filter"), count);

  const gJenis = h("div", { class: "tb-group tb-jenis", role: "group", "aria-label": "Jenis bencana" }, semua, ...chips);
  const gKab = h("div", { class: "tb-group tb-kab" }, combo.el);
  const gDate = h("div", { class: "tb-group tb-date" }, date.el);
  const extra = h("div", { class: "tb-extra", id: "tb-extra" }, gJenis, h("span", { class: "tb-sep", "aria-hidden": "true" }), gDate,
    h("span", { class: "tb-sep", "aria-hidden": "true" }), reset);
  const el = h("div", { class: "toolbar float-card", role: "region", "aria-label": "Filter data" },
    h("div", { class: "tb-main" }, gKab, more), extra);

  function setOpen(open: boolean): void {
    more.setAttribute("aria-expanded", String(open));
    el.classList.toggle("is-open", open);
    el.dispatchEvent(new CustomEvent("toolbar-resize", { bubbles: true }));
  }

  function sync(): void {
    const s = store.state;
    for (const c of chips) c.setAttribute("aria-pressed", String(s.jenis.has(c.dataset.jenis as Jenis)));
    const all = s.jenis.size === JENIS.length, none = s.jenis.size === 0;
    semua.setAttribute("aria-pressed", String(all));
    semua.classList.toggle("is-partial", !all && !none);
    gJenis.classList.toggle("is-all", all);
    const n = (s.jenis.size < JENIS.length ? 1 : 0) + (s.dari || s.sampai ? 1 : 0);
    reset.disabled = isDefaultFilter(s);
    reset.setAttribute("aria-label", n ? `Atur ulang filter (${n} aktif)` : "Atur ulang filter");
    count.hidden = n === 0;
    count.textContent = String(n);
    combo.setValue(s.kab);
    date.setRange(s.dari, s.sampai);
  }
  return { el, sync, date, setWilayah: (w: Wilayah) => combo.setOptions(w.kab), closePopovers: () => date.close(false), isPopoverOpen: () => date.isOpen };
}
